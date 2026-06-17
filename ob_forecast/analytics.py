from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .models import OBForecastSignal, OBTonnageSnapshot
from voyage.models import DailyIndexValue

INDEX_NAME = "P3A_82"

SERIES_METRIC_SIGN = {
    "BALLAST_AT_SEA": -1,
    "IN_PORT": +1,
    "TOTAL": -1,
}

SERIES_LABEL = {
    "BALLAST_AT_SEA": "ballast vessels at sea",
    "IN_PORT": "vessels in port",
    "TOTAL": "total fleet count",
}

MIN_DATA_DAYS = 14
MIN_REGRESSION_WEEKS = 8


@dataclass
class OBSignalResult:
    zone: str
    direction: str = "neutral"
    score: float = 0.0
    confidence: float = 0.0
    method: str = "insufficient"
    drivers: list = field(default_factory=list)
    data_days: int = 0


def load_zone_frame(zone, as_of=None):
    """OBTonnageSnapshot rows for a zone → wide DataFrame (date index × series columns)."""
    qs = OBTonnageSnapshot.objects.filter(zone=zone)
    if as_of is not None:
        qs = qs.filter(date__lte=as_of)
    rows = list(qs.order_by("date").values("date", "series", "vessel_count"))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot(index="date", columns="series", values="vessel_count")
    wide.columns.name = None
    return wide.sort_index()


def load_panamax_index(as_of=None):
    """P3A_82 daily closes → date-indexed Series."""
    qs = DailyIndexValue.objects.filter(index__name=INDEX_NAME)
    if as_of is not None:
        qs = qs.filter(date__lte=as_of)
    rows = list(qs.order_by("date").values_list("date", "value"))
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([r[1] for r in rows], index=idx).sort_index()


def _rolling_zscore(series, window=28):
    min_periods = max(7, window // 3)
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std()
    z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def _weekly_changes(series):
    return series.resample("W-FRI").last().diff()


def _direction_from_score(score):
    if score > 0.5:
        return "bullish"
    if score < -0.5:
        return "bearish"
    return "neutral"


def _available_series(df):
    return [s for s in ("BALLAST_AT_SEA", "IN_PORT", "TOTAL") if s in df.columns]


def _snapshot_signal(df):
    series_list = _available_series(df)
    if not series_list:
        return 0.0, ["No series data available."]
    latest = df.iloc[-1]
    # Normalize by fleet total so each series is a fraction of total fleet.
    # If TOTAL series is available, use it as the normalizer directly since
    # BALLAST_AT_SEA and IN_PORT are sub-components — summing them with TOTAL
    # would double-count and compress all scores.
    fleet_size = float(latest.get("TOTAL", 0) or 0) if "TOTAL" in series_list else 0.0
    total = max(1.0, fleet_size or sum(float(latest.get(s, 0) or 0) for s in series_list))
    score = 0.0
    drivers = []
    for s in series_list:
        val = float(latest.get(s, 0) or 0)
        sign = SERIES_METRIC_SIGN[s]
        score += sign * (val / total) * 3
        drivers.append(
            f"{int(val)} {SERIES_LABEL[s]}"
            + (" → bearish pressure" if sign < 0 else " → bullish pressure")
        )
    score = float(np.clip(score / len(series_list), -3, 3))
    drivers.append("Signal from snapshot only — accuracy improves as history accumulates.")
    return score, drivers


def _zscore_signal(df):
    contributions = []
    drivers = []
    for s in _available_series(df):
        if df[s].dropna().empty:
            continue
        z = _rolling_zscore(df[s])
        if z.dropna().empty:
            continue
        z_val = float(z.dropna().iloc[-1])
        sign = SERIES_METRIC_SIGN[s]
        signed = sign * float(np.clip(z_val, -3, 3))
        contributions.append(signed)
        if abs(z_val) >= 1.0:
            tone = "bearish" if signed < 0 else "bullish"
            updown = "above" if z_val > 0 else "below"
            drivers.append(
                f"{SERIES_LABEL[s].capitalize()} is {abs(z_val):.1f}σ "
                f"{updown} its 4-week norm → {tone} pressure"
            )
    score = sum(contributions) / len(contributions) if contributions else 0.0
    return score, drivers


def _fit_regression(df, index_series):
    series_list = _available_series(df)
    if not series_list or index_series.empty:
        return None
    i_chg = _weekly_changes(index_series)
    metric_changes = {s: _weekly_changes(df[s]) for s in series_list}
    raw_metrics = pd.DataFrame(metric_changes)
    latest_x = raw_metrics.iloc[-1:].copy()   # capture before target column is joined
    frame = raw_metrics.copy()
    frame["__y"] = i_chg.shift(-1)
    frame = frame.dropna()
    if len(frame) < MIN_REGRESSION_WEEKS:
        return None
    X = frame[series_list].to_numpy(dtype=float)
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
    return {"r2": r2, "n_weeks": len(frame), "predicted_next_change": predicted}


def generate_ob_signal(zone, as_of=None):
    """Compute the directional supply signal for one Pacific zone."""
    result = OBSignalResult(zone=zone)
    df = load_zone_frame(zone, as_of=as_of)
    result.data_days = int(len(df))

    if result.data_days == 0:
        result.drivers = ["No Oceanbolt data uploaded for this zone yet."]
        return result

    if result.data_days < MIN_DATA_DAYS:
        snap_score, snap_drivers = _snapshot_signal(df)
        result.method = "snapshot"
        result.score = snap_score
        result.direction = _direction_from_score(snap_score)
        result.confidence = min(0.25, 0.05 + result.data_days / 80.0)
        result.drivers = snap_drivers
        return result

    z_score, z_drivers = _zscore_signal(df)
    index_series = load_panamax_index(as_of=as_of)
    regression = _fit_regression(df, index_series)

    if regression is None or regression.get("predicted_next_change") is None:
        result.method = "zscore"
        result.score = z_score
        result.confidence = min(0.6, 0.2 + result.data_days / 180.0)
        result.drivers = z_drivers or ["Supply metrics near their 4-week norms."]
    else:
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
            f"Model points to {trend} P3A_82 next week "
            f'(R²={r2:.2f}, {regression["n_weeks"]} wks).'
        ] + z_drivers[:2]

    result.direction = _direction_from_score(result.score)
    return result


def persist_ob_signal(result, target_date):
    """Upsert an OBForecastSignal row from an OBSignalResult."""
    OBForecastSignal.objects.update_or_create(
        date=target_date,
        zone=result.zone,
        defaults={
            "direction": result.direction,
            "score": result.score,
            "confidence": result.confidence,
            "method": result.method,
            "drivers": result.drivers,
            "data_days": result.data_days,
        },
    )
