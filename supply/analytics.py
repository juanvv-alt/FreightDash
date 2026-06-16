"""Supply-signal analytics: turn DailySupplySnapshot history + market data into a
transparent directional signal per vessel class.

The layer is deliberately explainable (rolling z-scores, lagged correlations, a
small OLS) rather than a black-box model, and it degrades gracefully with thin
history -- which matters because we accumulate AIS data from scratch:

    < 14 days        -> 'insufficient' (neutral, very low confidence)
    14d .. ~8 weeks  -> z-score heuristic (capped confidence)
    >= ~8 weeks      -> blended regression + z-score

Sign convention (more available tonnage => bearish):
    ballast_at_sea_count, expected_open_7d, in_port_discharge_count  rising = -1
    laden_at_sea_count, in_port_load_count                           rising = +1
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .models import DailySupplySnapshot, SupplySignal

# Pacific-route index per class — used for signal regression/correlation.
# Panamax uses P3A_82 (Japan/Korea ↔ Pacific) rather than global BPI 82TC
# because our supply universe is Pacific basin only.
CLASS_INDEX_MAP = {
    "capesize": "BCI 5TC",
    "panamax": "P3A_82",
    "supramax": "BSI 58TC",
    "handysize": "BHSI 38TC",
}

# Broad market reference shown alongside the signal (informational only).
CLASS_MARKET_INDEX_MAP = {
    "capesize": "BCI 5TC",
    "panamax": "BPI 82TC",
    "supramax": "BSI 58TC",
    "handysize": "BHSI 38TC",
}

# FFACurve.vessel_class is stored title-cased (see voyage/ffa_utils.py).
FFA_CLASS_MAP = {
    "capesize": "Capesize",
    "panamax": "Panamax",
    "supramax": "Supramax",
    "handysize": "Handysize",
}

SUPPLY_METRICS = [
    "ballast_at_sea_count",
    "laden_at_sea_count",
    "in_port_load_count",
    "in_port_discharge_count",
    "expected_open_7d",
]

METRIC_SIGN = {
    "ballast_at_sea_count": -1,
    "expected_open_7d": -1,
    "in_port_discharge_count": -1,
    "laden_at_sea_count": +1,
    "in_port_load_count": +1,
}

METRIC_LABEL = {
    "ballast_at_sea_count": "ballast tonnage at sea",
    "laden_at_sea_count": "laden tonnage at sea",
    "in_port_load_count": "vessels at load ports",
    "in_port_discharge_count": "vessels at discharge ports",
    "expected_open_7d": "tonnage expected open within 7 days",
}

MIN_DATA_DAYS = 14
MIN_REGRESSION_WEEKS = 8


@dataclass
class SignalResult:
    vessel_class: str
    direction: str = "neutral"
    score: float = 0.0
    confidence: float = 0.0
    method: str = "insufficient"
    drivers: list = field(default_factory=list)
    data_days: int = 0
    index_name: Optional[str] = None
    spot_value: Optional[float] = None
    ffa_slope: Optional[float] = None
    ffa_stance: Optional[str] = None


# ----- data loading ---------------------------------------------------------


def load_supply_frame(vessel_class, basin="pacific", as_of=None):
    """DailySupplySnapshot rows -> DataFrame indexed by date, SUPPLY_METRICS cols."""
    qs = DailySupplySnapshot.objects.filter(vessel_class=vessel_class, basin=basin)
    if as_of is not None:
        qs = qs.filter(date__lte=as_of)
    rows = list(qs.order_by("date").values("date", *SUPPLY_METRICS))
    if not rows:
        return pd.DataFrame(columns=SUPPLY_METRICS)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_index_series(index_name, as_of=None):
    """DailyIndexValue for an AvailableIndex name -> date-indexed Series."""
    from voyage.models import DailyIndexValue

    qs = DailyIndexValue.objects.filter(index__name=index_name)
    if as_of is not None:
        qs = qs.filter(date__lte=as_of)
    rows = list(qs.order_by("date").values_list("date", "value"))
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([r[1] for r in rows], index=idx).sort_index()


# ----- statistics -----------------------------------------------------------


def rolling_zscore(series, window, min_periods=None):
    """(x - rolling mean) / rolling std. Degrades with short history."""
    if min_periods is None:
        min_periods = max(7, window // 3)
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std()
    z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def _weekly_changes(series):
    """Resample a daily series to weekly (Fri) and return week-over-week diffs."""
    weekly = series.resample("W-FRI").last()
    return weekly.diff()


def lagged_correlations(supply, index, lags_weeks=(1, 2, 3, 4), method="pearson"):
    """Correlation of this week's supply change with the index change `lag` weeks
    later. Negative correlation at some lag means rising supply precedes a softer
    market. Returns {lag: correlation or nan}.

    Pearson by default: it is computed natively by pandas, whereas 'spearman'
    would pull in scipy. Pearson is adequate here -- we read the sign and rough
    magnitude of the lead/lag relationship, not a rank-exact coefficient.
    """
    s_chg = _weekly_changes(supply)
    i_chg = _weekly_changes(index)
    out = {}
    for lag in lags_weeks:
        joined = pd.concat([s_chg, i_chg.shift(-lag)], axis=1, keys=["s", "i"]).dropna()
        if len(joined) < 4:
            out[lag] = float("nan")
        else:
            out[lag] = float(joined["s"].corr(joined["i"], method=method))
    return out


def fit_signal_regression(supply_df, index_series, min_weeks=MIN_REGRESSION_WEEKS):
    """OLS of next-week index change on weekly changes of the supply metrics.

    Returns {'coef', 'r2', 'n_weeks', 'predicted_next_change', 'metrics'} or None
    when there is not enough complete weekly history.
    """
    if supply_df.empty or index_series.empty:
        return None

    i_chg = _weekly_changes(index_series)
    metric_changes = {}
    for m in SUPPLY_METRICS:
        if m in supply_df:
            metric_changes[m] = _weekly_changes(supply_df[m])
    if not metric_changes:
        return None

    frame = pd.DataFrame(metric_changes)
    # Target is the index change one week *after* the supply change.
    frame["__y"] = i_chg.shift(-1)
    latest_x = frame[list(metric_changes.keys())].iloc[-1:].copy()
    frame = frame.dropna()
    if len(frame) < min_weeks:
        return None

    metrics = list(metric_changes.keys())
    X = frame[metrics].to_numpy(dtype=float)
    y = frame["__y"].to_numpy(dtype=float)
    X_design = np.column_stack([np.ones(len(X)), X])

    coef, _, _, _ = np.linalg.lstsq(X_design, y, rcond=None)
    y_hat = X_design @ coef
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    predicted = None
    if not latest_x.isna().any(axis=None):
        x_last = np.concatenate([[1.0], latest_x.to_numpy(dtype=float).ravel()])
        predicted = float(x_last @ coef)

    return {
        "coef": dict(zip(["intercept"] + metrics, coef.tolist())),
        "r2": r2,
        "n_weeks": len(frame),
        "predicted_next_change": predicted,
        "metrics": metrics,
    }


def ffa_curve_stance(vessel_class, spot_value):
    """Compare the front of the latest FFA curve to spot.

    Returns {'slope', 'stance', 'front_mid'} or None. stance is 'contango'
    (forward > spot, market expects firming), 'backwardation', or 'flat'.
    """
    from voyage.models import FFACurve

    ffa_class = FFA_CLASS_MAP.get(vessel_class)
    if not ffa_class or spot_value in (None, 0):
        return None
    curve = (
        FFACurve.objects.filter(vessel_class=ffa_class).order_by("-created_at").first()
    )
    if curve is None:
        return None
    fronts = list(
        curve.periods.filter(period_type="monthly").order_by("start_date")[:2]
    )
    if not fronts:
        return None
    mids = [float(p.bid + p.offer) / 2.0 for p in fronts]
    front_mid = sum(mids) / len(mids)
    slope = (front_mid - spot_value) / spot_value
    if slope > 0.02:
        stance = "contango"
    elif slope < -0.02:
        stance = "backwardation"
    else:
        stance = "flat"
    return {"slope": slope, "stance": stance, "front_mid": front_mid}


# ----- signal synthesis -----------------------------------------------------


def _direction_from_score(score):
    if score > 0.5:
        return "bullish"
    if score < -0.5:
        return "bearish"
    return "neutral"


def _snapshot_signal(supply_df):
    """Ratio-based signal from the latest snapshot row.

    Used when we have 1–13 days of history — not enough for z-scores but enough
    to say something directional. Score is derived from the share of tonnage in
    each state (ballast heavy → bearish; vessels at load ports → bullish).
    Confidence is capped at 0.25 since there's no trend context.
    """
    latest = supply_df.iloc[-1]
    total = max(1.0, sum(float(latest.get(m, 0) or 0) for m in SUPPLY_METRICS))

    score = 0.0
    for m in SUPPLY_METRICS:
        val = float(latest.get(m, 0) or 0)
        score += METRIC_SIGN[m] * (val / total) * 3  # normalise then scale to ±3
    score = float(np.clip(score / len(SUPPLY_METRICS), -3, 3))

    drivers = [
        f"{int(latest.get(m, 0) or 0)} {METRIC_LABEL[m]}"
        + (" → bearish pressure" if METRIC_SIGN[m] < 0 else " → bullish pressure")
        for m in SUPPLY_METRICS
        if (latest.get(m, 0) or 0) > 0
    ]
    drivers.append(
        "Signal from today's snapshot only — accuracy improves as history accumulates."
    )
    return score, drivers


def _zscore_signal(supply_df):
    """Score from latest 28-day z-scores weighted by sign convention.

    Returns (score, drivers, per-metric z dict).
    """
    drivers = []
    contributions = []
    z_latest = {}
    for m in SUPPLY_METRICS:
        if m not in supply_df or supply_df[m].dropna().empty:
            continue
        z = rolling_zscore(supply_df[m], window=28)
        if z.dropna().empty:
            continue
        z_val = float(z.dropna().iloc[-1])
        z_latest[m] = z_val
        signed = METRIC_SIGN[m] * float(np.clip(z_val, -3, 3))
        contributions.append(signed)
        if abs(z_val) >= 1.0:
            tone = "bearish" if signed < 0 else "bullish"
            updown = "above" if z_val > 0 else "below"
            drivers.append(
                f"{METRIC_LABEL[m].capitalize()} is {abs(z_val):.1f}σ "
                f"{updown} its 4-week norm → {tone} pressure"
            )
    score = sum(contributions) / len(contributions) if contributions else 0.0
    return score, drivers, z_latest


def generate_signal(vessel_class, as_of=None, basin="pacific"):
    """Compute the directional supply signal for one vessel class."""
    result = SignalResult(vessel_class=vessel_class)
    result.index_name = CLASS_INDEX_MAP.get(vessel_class)

    supply_df = load_supply_frame(vessel_class, basin=basin, as_of=as_of)
    result.data_days = int(len(supply_df))

    index_series = (
        load_index_series(result.index_name, as_of=as_of)
        if result.index_name
        else pd.Series(dtype=float)
    )
    if not index_series.empty:
        result.spot_value = float(index_series.iloc[-1])

    # FFA stance is informational regardless of supply-history depth.
    ffa = ffa_curve_stance(vessel_class, result.spot_value)
    if ffa is not None:
        result.ffa_slope = ffa["slope"]
        result.ffa_stance = ffa["stance"]

    if result.data_days < MIN_DATA_DAYS:
        if result.data_days == 0:
            result.method = "insufficient"
            result.direction = "neutral"
            result.confidence = 0.0
            result.drivers = [
                "No AIS supply history yet — run ingest then trigger daily aggregation."
            ]
            _append_ffa_driver(result, ffa)
            return result

        # 1–13 days: snapshot ratio heuristic, very low confidence.
        snap_score, snap_drivers = _snapshot_signal(supply_df)
        result.method = "snapshot"
        result.score = snap_score
        result.direction = _direction_from_score(snap_score)
        result.confidence = min(0.25, 0.05 + result.data_days / 80.0)
        result.drivers = snap_drivers
        _append_ffa_driver(result, ffa)
        return result

    z_score, z_drivers, _ = _zscore_signal(supply_df)

    regression = None
    if not index_series.empty:
        regression = fit_signal_regression(supply_df, index_series)

    if regression is None or regression.get("predicted_next_change") is None:
        # Z-score heuristic regime.
        result.method = "zscore"
        result.score = z_score
        result.confidence = min(0.6, 0.2 + result.data_days / 180.0)
        result.drivers = z_drivers or ["Supply metrics near their 4-week norms."]
    else:
        # Blended regression + z-score regime.
        weekly_idx_chg = _weekly_changes(index_series).dropna()
        idx_std = float(weekly_idx_chg.std()) if len(weekly_idx_chg) > 1 else 0.0
        pred = regression["predicted_next_change"]
        reg_score = float(np.clip(pred / idx_std, -3, 3)) if idx_std > 0 else 0.0
        result.method = "regression"
        result.score = 0.6 * reg_score + 0.4 * z_score
        r2 = max(regression["r2"], 0.0)
        result.confidence = min(0.9, 0.3 + 0.4 * r2 + regression["n_weeks"] / 100.0)
        trend = "higher" if reg_score > 0 else "lower"
        result.drivers = [
            f"Supply-driven model points to a {trend} {result.index_name} next "
            f'week (R²={r2:.2f}, {regression["n_weeks"]} wks).'
        ] + z_drivers[:2]

    result.direction = _direction_from_score(result.score)

    # FFA agreement nudges confidence.
    _append_ffa_driver(result, ffa)
    if ffa is not None:
        ffa_dir = (
            1
            if ffa["stance"] == "contango"
            else (-1 if ffa["stance"] == "backwardation" else 0)
        )
        if ffa_dir != 0 and result.score != 0:
            agree = (ffa_dir > 0) == (result.score > 0)
            result.confidence = float(
                np.clip(result.confidence + (0.05 if agree else -0.05), 0.0, 1.0)
            )

    return result


def _append_ffa_driver(result, ffa):
    if ffa is None:
        return
    if ffa["stance"] == "contango":
        result.drivers.append(
            f'FFA front months in contango ({ffa["slope"] * 100:+.1f}% vs spot) '
            f"— paper market pricing firming."
        )
    elif ffa["stance"] == "backwardation":
        result.drivers.append(
            f'FFA front months in backwardation ({ffa["slope"] * 100:+.1f}% vs '
            f"spot) — paper market pricing softening."
        )


def persist_signal(result, target_date):
    """Upsert a SupplySignal row from a SignalResult."""
    SupplySignal.objects.update_or_create(
        date=target_date,
        vessel_class=result.vessel_class,
        defaults={
            "direction": result.direction,
            "score": result.score,
            "confidence": result.confidence,
            "method": result.method,
            "drivers": result.drivers,
            "data_days": result.data_days,
        },
    )
