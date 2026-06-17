# OB Forecast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `ob_forecast` Django app to FreightDash that stores Oceanbolt Panamax zone tonnage counts and generates bullish/bearish/neutral supply signals per Pacific zone.

**Architecture:** New self-contained app alongside `supply` — models store daily zone counts uploaded via CSV or quick-entry form, analytics adapts the existing supply z-score/regression pipeline per zone, views serve a dashboard with signal cards + Chart.js charts. Does not modify the `supply` app.

**Tech Stack:** Django 4.2, pandas, numpy, Chart.js 4.4, Bootstrap 5.3, PostgreSQL

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `ob_forecast/__init__.py` | Create | App package |
| `ob_forecast/apps.py` | Create | AppConfig |
| `ob_forecast/models.py` | Create | 3 models: OBTonnageSnapshot, OBForecastSignal, OBUploadLog |
| `ob_forecast/migrations/__init__.py` | Create | Migrations package |
| `ob_forecast/admin.py` | Create | Django admin registrations |
| `ob_forecast/analytics.py` | Create | Signal generation logic |
| `ob_forecast/views.py` | Create | 5 view functions |
| `ob_forecast/urls.py` | Create | 5 URL patterns |
| `ob_forecast/tests.py` | Create | Tests for analytics + views |
| `ob_forecast/templates/ob_forecast/ob_forecast.html` | Create | Main dashboard template |
| `config/settings.py` | Modify | Add `ob_forecast` to INSTALLED_APPS |
| `config/urls.py` | Modify | Include `ob_forecast.urls` |

---

## Task 1: App Skeleton

**Files:**
- Create: `ob_forecast/__init__.py`
- Create: `ob_forecast/apps.py`
- Create: `ob_forecast/migrations/__init__.py`

- [ ] **Step 1: Create the app directory and empty files**

```bash
cd C:/Users/juan.vanvyve/.vscode/FreightDash
mkdir -p ob_forecast/migrations
mkdir -p ob_forecast/templates/ob_forecast
```

- [ ] **Step 2: Write `ob_forecast/__init__.py`**

```python
# ob_forecast/__init__.py
```
(empty file)

- [ ] **Step 3: Write `ob_forecast/apps.py`**

```python
from django.apps import AppConfig


class ObForecastConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ob_forecast"
    verbose_name = "OB Forecast"
```

- [ ] **Step 4: Write `ob_forecast/migrations/__init__.py`**

```python
# ob_forecast/migrations/__init__.py
```
(empty file)

- [ ] **Step 5: Commit**

```bash
git add ob_forecast/
git commit -m "feat(ob_forecast): add app skeleton"
```

---

## Task 2: Models + Migration

**Files:**
- Create: `ob_forecast/models.py`
- Modify: `config/settings.py` (line 63 — end of INSTALLED_APPS list)

- [ ] **Step 1: Write `ob_forecast/models.py`**

```python
from django.db import models

ZONE_CHOICES = [
    ("NE_ASIA", "NE Asia"),
    ("SE_ASIA", "SE Asia"),
    ("AUSTRALIA", "Australia"),
    ("EAST_PACIFIC", "East Pacific"),
]

SERIES_CHOICES = [
    ("BALLAST_AT_SEA", "Ballast at Sea"),
    ("IN_PORT", "In Port"),
    ("TOTAL", "Total"),
]


class OBTonnageSnapshot(models.Model):
    """Daily Oceanbolt vessel count for one zone + series combination."""

    date = models.DateField(db_index=True)
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    series = models.CharField(max_length=20, choices=SERIES_CHOICES)
    vessel_count = models.IntegerField()
    vessel_dwt = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("date", "zone", "series")]
        ordering = ["-date", "zone", "series"]

    def __str__(self):
        return f"{self.date} {self.zone} {self.series}: {self.vessel_count}"


class OBForecastSignal(models.Model):
    """Computed daily directional signal per zone; persisted for history."""

    DIRECTION_CHOICES = [
        ("bullish", "Bullish"),
        ("bearish", "Bearish"),
        ("neutral", "Neutral"),
    ]
    METHOD_CHOICES = [
        ("regression", "Regression"),
        ("zscore", "Z-score heuristic"),
        ("snapshot", "Snapshot ratio (cold start)"),
        ("insufficient", "Insufficient data"),
    ]

    date = models.DateField(db_index=True)
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    score = models.FloatField(help_text="Signed magnitude, roughly -3..+3")
    confidence = models.FloatField(help_text="0..1")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    drivers = models.JSONField(default=list, blank=True)
    data_days = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("date", "zone")]
        ordering = ["-date", "zone"]

    def __str__(self):
        return f"{self.date} {self.zone}: {self.direction} ({self.method})"


class OBUploadLog(models.Model):
    """Audit trail for CSV uploads."""

    uploaded_at = models.DateTimeField(auto_now_add=True)
    zone = models.CharField(max_length=20)
    series = models.CharField(max_length=20)
    filename = models.CharField(max_length=255)
    rows_added = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.uploaded_at:%Y-%m-%d %H:%M} {self.zone}/{self.series} +{self.rows_added}"
```

- [ ] **Step 2: Register app in `config/settings.py`**

Find the INSTALLED_APPS list (ends at line 63). Add `ob_forecast` after `supply`:

```python
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'nested_admin',
    'core',
    'voyage',
    'supply',
    'ob_forecast',           # ← add this line
]
```

- [ ] **Step 3: Create migration**

```bash
cd C:/Users/juan.vanvyve/.vscode/FreightDash
.venv/Scripts/python manage.py makemigrations ob_forecast
```

Expected output:
```
Migrations for 'ob_forecast':
  ob_forecast/migrations/0001_initial.py
    - Create model OBForecastSignal
    - Create model OBTonnageSnapshot
    - Create model OBUploadLog
```

- [ ] **Step 4: Apply migration**

```bash
.venv/Scripts/python manage.py migrate ob_forecast
```

Expected output:
```
Running migrations:
  Applying ob_forecast.0001_initial... OK
```

- [ ] **Step 5: Commit**

```bash
git add ob_forecast/models.py ob_forecast/migrations/ config/settings.py
git commit -m "feat(ob_forecast): add models and initial migration"
```

---

## Task 3: Admin

**Files:**
- Create: `ob_forecast/admin.py`

- [ ] **Step 1: Write `ob_forecast/admin.py`**

```python
from django.contrib import admin

from .models import OBForecastSignal, OBTonnageSnapshot, OBUploadLog


@admin.register(OBTonnageSnapshot)
class OBTonnageSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "zone", "series", "vessel_count", "vessel_dwt")
    list_filter = ("zone", "series")
    date_hierarchy = "date"
    search_fields = ("zone",)


@admin.register(OBForecastSignal)
class OBForecastSignalAdmin(admin.ModelAdmin):
    list_display = ("date", "zone", "direction", "score", "confidence", "method", "data_days")
    list_filter = ("zone", "direction", "method")
    date_hierarchy = "date"


@admin.register(OBUploadLog)
class OBUploadLogAdmin(admin.ModelAdmin):
    list_display = ("uploaded_at", "zone", "series", "filename", "rows_added", "rows_skipped")
    list_filter = ("zone", "series")
    readonly_fields = ("uploaded_at",)
```

- [ ] **Step 2: Commit**

```bash
git add ob_forecast/admin.py
git commit -m "feat(ob_forecast): register models in admin"
```

---

## Task 4: Analytics (TDD)

**Files:**
- Create: `ob_forecast/analytics.py`
- Create: `ob_forecast/tests.py` (analytics section)

- [ ] **Step 1: Write the failing analytics tests in `ob_forecast/tests.py`**

```python
import io
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from voyage.models import AvailableIndex, DailyIndexValue

from .analytics import (
    OBSignalResult,
    generate_ob_signal,
    load_zone_frame,
    persist_ob_signal,
)
from .models import OBForecastSignal, OBTonnageSnapshot


class OBLoadZoneFrameTestCase(TestCase):
    def test_empty_returns_empty_dataframe(self):
        df = load_zone_frame("NE_ASIA")
        self.assertTrue(df.empty)

    def test_pivots_series_to_columns(self):
        today = date.today()
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="BALLAST_AT_SEA", vessel_count=52)
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="IN_PORT", vessel_count=27)
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="TOTAL", vessel_count=64)
        df = load_zone_frame("NE_ASIA")
        self.assertEqual(len(df), 1)
        self.assertIn("BALLAST_AT_SEA", df.columns)
        self.assertIn("IN_PORT", df.columns)
        self.assertIn("TOTAL", df.columns)
        self.assertEqual(df["BALLAST_AT_SEA"].iloc[0], 52)

    def test_only_loads_requested_zone(self):
        today = date.today()
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="TOTAL", vessel_count=64)
        OBTonnageSnapshot.objects.create(date=today, zone="SE_ASIA", series="TOTAL", vessel_count=221)
        df = load_zone_frame("NE_ASIA")
        self.assertEqual(len(df), 1)
        self.assertEqual(df["TOTAL"].iloc[0], 64)


class OBSignalAnalyticsTestCase(TestCase):
    def setUp(self):
        self.index, _ = AvailableIndex.objects.get_or_create(
            name="P3A_82",
            defaults={"vessel_size": "panamax"},
        )

    def _seed_zone(self, zone, days, ballast_base=50, port_base=20, total_base=80):
        """Seed `days` daily rows with a slight downward trend in ballast."""
        start = date.today() - timedelta(days=days - 1)
        for i in range(days):
            d = start + timedelta(days=i)
            OBTonnageSnapshot.objects.create(
                date=d, zone=zone, series="BALLAST_AT_SEA",
                vessel_count=max(1, ballast_base - i // 3),
            )
            OBTonnageSnapshot.objects.create(
                date=d, zone=zone, series="IN_PORT",
                vessel_count=port_base + i // 5,
            )
            OBTonnageSnapshot.objects.create(
                date=d, zone=zone, series="TOTAL",
                vessel_count=total_base,
            )
            DailyIndexValue.objects.create(index=self.index, date=d, value=9000 + i * 20)

    def test_no_data_returns_insufficient(self):
        result = generate_ob_signal("NE_ASIA")
        self.assertIsInstance(result, OBSignalResult)
        self.assertEqual(result.method, "insufficient")
        self.assertEqual(result.direction, "neutral")
        self.assertEqual(result.data_days, 0)

    def test_sparse_data_returns_snapshot(self):
        self._seed_zone("NE_ASIA", days=7)
        result = generate_ob_signal("NE_ASIA")
        self.assertEqual(result.method, "snapshot")
        self.assertLessEqual(result.confidence, 0.25)
        self.assertIn(result.direction, ("bullish", "bearish", "neutral"))

    def test_14_days_produces_zscore(self):
        self._seed_zone("NE_ASIA", days=20)
        result = generate_ob_signal("NE_ASIA")
        self.assertEqual(result.method, "zscore")
        self.assertLessEqual(result.confidence, 0.6)

    def test_persist_upserts_signal(self):
        self._seed_zone("NE_ASIA", days=20)
        today = date.today()
        result = generate_ob_signal("NE_ASIA", as_of=today)
        persist_ob_signal(result, today)
        self.assertEqual(OBForecastSignal.objects.count(), 1)
        sig = OBForecastSignal.objects.get(zone="NE_ASIA", date=today)
        self.assertEqual(sig.method, result.method)
        # Second call should upsert, not duplicate.
        persist_ob_signal(result, today)
        self.assertEqual(OBForecastSignal.objects.count(), 1)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/juan.vanvyve/.vscode/FreightDash
.venv/Scripts/python manage.py test ob_forecast.tests.OBLoadZoneFrameTestCase ob_forecast.tests.OBSignalAnalyticsTestCase --verbosity=2
```

Expected: `ImportError: cannot import name 'generate_ob_signal' from 'ob_forecast.analytics'`

- [ ] **Step 3: Write `ob_forecast/analytics.py`**

```python
"""OB Forecast analytics: turn OBTonnageSnapshot history into a transparent
directional signal per Pacific zone.

Sign convention (more supply → bearish for rates):
    BALLAST_AT_SEA, TOTAL  rising = -1 (bearish contribution)
    IN_PORT                rising = +1 (bullish — supply absorbed)

Three regimes (same thresholds as supply.analytics):
    < 14 days    → 'insufficient' or 'snapshot'
    14–56 days   → 'zscore' heuristic
    >= 56 days   → blended OLS regression + z-score
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .models import OBForecastSignal, OBTonnageSnapshot

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
    from voyage.models import DailyIndexValue

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
    total = max(1.0, sum(float(latest.get(s, 0) or 0) for s in series_list))
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
        col = df[s].dropna()
        if col.empty:
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
    frame = pd.DataFrame(metric_changes)
    frame["__y"] = i_chg.shift(-1)
    latest_x = frame[series_list].iloc[-1:].copy()
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
```

- [ ] **Step 4: Run analytics tests — expect them to pass**

```bash
.venv/Scripts/python manage.py test ob_forecast.tests.OBLoadZoneFrameTestCase ob_forecast.tests.OBSignalAnalyticsTestCase --verbosity=2
```

Expected:
```
test_14_days_produces_zscore ... ok
test_no_data_returns_insufficient ... ok
test_only_loads_requested_zone ... ok
test_persist_upserts_signal ... ok
test_pivots_series_to_columns ... ok
test_sparse_data_returns_snapshot ... ok
...
Ran 7 tests in X.XXXs
OK
```

- [ ] **Step 5: Commit**

```bash
git add ob_forecast/analytics.py ob_forecast/tests.py
git commit -m "feat(ob_forecast): add analytics with z-score/regression signal generation"
```

---

## Task 5: Views (TDD)

**Files:**
- Create: `ob_forecast/views.py`
- Modify: `ob_forecast/tests.py` (add view tests)

- [ ] **Step 1: Append view tests to `ob_forecast/tests.py`**

Add these classes at the bottom of the existing file (`import io` is already at the top from Task 4):

```python
import io


class OBForecastViewTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_superuser("admin", "a@b.com", "pw")
        self.client.force_login(self.user)

    def test_page_renders(self):
        resp = self.client.get("/ob-forecast/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "OB Forecast")

    def test_chart_data_endpoint_empty(self):
        resp = self.client.get("/ob-forecast/chart-data/NE_ASIA/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertIn("series", data)
        self.assertEqual(data["labels"], [])

    def test_chart_data_unknown_zone(self):
        resp = self.client.get("/ob-forecast/chart-data/FAKE_ZONE/")
        self.assertEqual(resp.status_code, 404)

    def test_chart_data_returns_series(self):
        today = date.today()
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="BALLAST_AT_SEA", vessel_count=52)
        OBTonnageSnapshot.objects.create(date=today, zone="NE_ASIA", series="IN_PORT", vessel_count=27)
        resp = self.client.get("/ob-forecast/chart-data/NE_ASIA/")
        data = resp.json()
        self.assertIn(today.isoformat(), data["labels"])
        self.assertEqual(data["series"]["BALLAST_AT_SEA"][0], 52)

    def test_csv_upload_parses_oceanbolt_format(self):
        csv_content = (
            "Date,Vessel Count,Vessel DWT\r\n"
            "2026-01-01T00:00:00Z,52,3200000\r\n"
            "2026-01-02T00:00:00Z,50,3100000\r\n"
        )
        f = io.BytesIO(csv_content.encode("utf-8"))
        f.name = "test.csv"
        resp = self.client.post(
            "/ob-forecast/upload/",
            {"zone": "NE_ASIA", "series": "BALLAST_AT_SEA", "csv_file": f},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(OBTonnageSnapshot.objects.filter(zone="NE_ASIA").count(), 2)
        snap = OBTonnageSnapshot.objects.get(zone="NE_ASIA", date=date(2026, 1, 1))
        self.assertEqual(snap.vessel_count, 52)

    def test_daily_entry_saves_values(self):
        today = date.today()
        resp = self.client.post(
            "/ob-forecast/daily-entry/",
            {
                "entry_date": today.isoformat(),
                "NE_ASIA_BALLAST_AT_SEA": "52",
                "NE_ASIA_IN_PORT": "27",
                "NE_ASIA_TOTAL": "64",
                "SE_ASIA_BALLAST_AT_SEA": "170",
                "SE_ASIA_IN_PORT": "51",
                "SE_ASIA_TOTAL": "221",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            OBTonnageSnapshot.objects.filter(date=today, zone="NE_ASIA").count(), 3
        )
        snap = OBTonnageSnapshot.objects.get(date=today, zone="NE_ASIA", series="BALLAST_AT_SEA")
        self.assertEqual(snap.vessel_count, 52)

    def test_aggregate_creates_signals(self):
        today = date.today()
        # Seed enough rows for at least a snapshot signal
        for i in range(5):
            d = today - timedelta(days=i)
            OBTonnageSnapshot.objects.create(date=d, zone="NE_ASIA", series="TOTAL", vessel_count=60)
        resp = self.client.post("/ob-forecast/aggregate/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OBForecastSignal.objects.filter(date=today, zone="NE_ASIA").exists())
```

- [ ] **Step 2: Run view tests — expect ImportError or 404 (views don't exist yet)**

```bash
.venv/Scripts/python manage.py test ob_forecast.tests.OBForecastViewTestCase --verbosity=2
```

Expected: tests fail (no views or URLs yet).

- [ ] **Step 3: Write `ob_forecast/views.py`**

```python
import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .analytics import generate_ob_signal, persist_ob_signal
from .models import (
    SERIES_CHOICES,
    ZONE_CHOICES,
    OBForecastSignal,
    OBTonnageSnapshot,
    OBUploadLog,
)

ZONE_LABELS = dict(ZONE_CHOICES)
SERIES_LABELS = dict(SERIES_CHOICES)
ZONES = [z[0] for z in ZONE_CHOICES]


def _latest_ob_signal(zone, today):
    signal = OBForecastSignal.objects.filter(zone=zone).order_by("-date").first()
    if signal is not None:
        return {
            "direction": signal.direction,
            "score": signal.score,
            "confidence": signal.confidence,
            "method": signal.method,
            "drivers": signal.drivers,
            "data_days": signal.data_days,
            "date": signal.date,
        }
    result = generate_ob_signal(zone, as_of=today)
    return {
        "direction": result.direction,
        "score": result.score,
        "confidence": result.confidence,
        "method": result.method,
        "drivers": result.drivers,
        "data_days": result.data_days,
        "date": today,
    }


def ob_forecast_view(request):
    today = timezone.localdate()
    cards = []
    for zone_key, zone_label in ZONE_CHOICES:
        signal = _latest_ob_signal(zone_key, today)
        cards.append(
            {
                "zone": zone_key,
                "label": zone_label,
                "signal": signal,
                "confidence_pct": round(signal["confidence"] * 100),
            }
        )

    upload_log = [
        {
            "uploaded_at": log.uploaded_at,
            "zone_label": ZONE_LABELS.get(log.zone, log.zone),
            "series_label": SERIES_LABELS.get(log.series, log.series),
            "rows_added": log.rows_added,
            "rows_skipped": log.rows_skipped,
        }
        for log in OBUploadLog.objects.order_by("-uploaded_at")[:10]
    ]

    context = {
        "cards": cards,
        "zones": ZONE_CHOICES,
        "series_choices": SERIES_CHOICES,
        "upload_log": upload_log,
        "today": today,
    }
    return render(request, "ob_forecast/ob_forecast.html", context)


def ob_chart_data(request, zone):
    if zone not in ZONES:
        return JsonResponse({"error": "Unknown zone"}, status=404)

    today = timezone.localdate()
    start = today - timedelta(days=180)

    rows = (
        OBTonnageSnapshot.objects.filter(zone=zone, date__gte=start)
        .order_by("date", "series")
        .values("date", "series", "vessel_count")
    )

    by_date = defaultdict(dict)
    for row in rows:
        d = row["date"].isoformat()
        by_date[d][row["series"]] = row["vessel_count"]

    labels = sorted(by_date.keys())
    series_out = {
        "BALLAST_AT_SEA": [by_date[d].get("BALLAST_AT_SEA") for d in labels],
        "IN_PORT": [by_date[d].get("IN_PORT") for d in labels],
        "TOTAL": [by_date[d].get("TOTAL") for d in labels],
    }

    from voyage.models import DailyIndexValue

    idx_qs = (
        DailyIndexValue.objects.filter(index__name="P3A_82", date__gte=start)
        .order_by("date")
        .values_list("date", "value")
    )
    index_points = [
        {"x": d.isoformat(), "y": float(v) if v is not None else None}
        for d, v in idx_qs
    ]

    return JsonResponse(
        {
            "labels": labels,
            "series": series_out,
            "index_name": "P3A_82",
            "index": index_points,
        }
    )


def ob_upload(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    zone = request.POST.get("zone", "").strip()
    series = request.POST.get("series", "").strip()
    uploaded_file = request.FILES.get("csv_file")

    if not zone or not series or not uploaded_file:
        return redirect("ob_forecast:ob_forecast")

    text = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows_added = 0
    rows_skipped = 0

    for row in reader:
        try:
            raw_date = row.get("Date", "").strip()
            parsed_date = date.fromisoformat(raw_date[:10])
            vessel_count = int(float(row.get("Vessel Count", 0)))
            vessel_dwt = int(float(row.get("Vessel DWT", 0)))
        except (ValueError, KeyError):
            rows_skipped += 1
            continue

        _, created = OBTonnageSnapshot.objects.update_or_create(
            date=parsed_date,
            zone=zone,
            series=series,
            defaults={"vessel_count": vessel_count, "vessel_dwt": vessel_dwt},
        )
        if created:
            rows_added += 1
        else:
            rows_skipped += 1

    OBUploadLog.objects.create(
        zone=zone,
        series=series,
        filename=uploaded_file.name,
        rows_added=rows_added,
        rows_skipped=rows_skipped,
    )
    return redirect("ob_forecast:ob_forecast")


def ob_daily_entry(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    raw_date = request.POST.get("entry_date", "").strip()
    try:
        entry_date = date.fromisoformat(raw_date)
    except ValueError:
        return redirect("ob_forecast:ob_forecast")

    for zone_key, _ in ZONE_CHOICES:
        for series_key, _ in SERIES_CHOICES:
            field_name = f"{zone_key}_{series_key}"
            raw_val = request.POST.get(field_name, "").strip()
            if not raw_val:
                continue
            try:
                vessel_count = int(float(raw_val))
            except ValueError:
                continue
            OBTonnageSnapshot.objects.update_or_create(
                date=entry_date,
                zone=zone_key,
                series=series_key,
                defaults={"vessel_count": vessel_count, "vessel_dwt": 0},
            )

    return redirect("ob_forecast:ob_forecast")


def ob_aggregate(request):
    if request.method != "POST":
        return redirect("ob_forecast:ob_forecast")

    today = timezone.localdate()
    for zone_key, _ in ZONE_CHOICES:
        result = generate_ob_signal(zone_key, as_of=today)
        persist_ob_signal(result, today)

    return redirect("ob_forecast:ob_forecast")
```

- [ ] **Step 4: Commit views (before tests pass — URLs still needed)**

```bash
git add ob_forecast/views.py ob_forecast/tests.py
git commit -m "feat(ob_forecast): add views for dashboard, chart data, upload, daily entry, aggregate"
```

---

## Task 6: URLs + Wire into Config

**Files:**
- Create: `ob_forecast/urls.py`
- Modify: `config/urls.py`

- [ ] **Step 1: Write `ob_forecast/urls.py`**

```python
from django.urls import path

from . import views

app_name = "ob_forecast"

urlpatterns = [
    path("ob-forecast/", views.ob_forecast_view, name="ob_forecast"),
    path(
        "ob-forecast/chart-data/<slug:zone>/",
        views.ob_chart_data,
        name="ob_chart_data",
    ),
    path("ob-forecast/upload/", views.ob_upload, name="ob_upload"),
    path("ob-forecast/daily-entry/", views.ob_daily_entry, name="ob_daily_entry"),
    path("ob-forecast/aggregate/", views.ob_aggregate, name="ob_aggregate"),
]
```

- [ ] **Step 2: Add include in `config/urls.py`**

Add one line after the `supply.urls` include:

```python
urlpatterns = [
    path('', include('supply.urls')),
    path('', include('ob_forecast.urls')),   # ← add this line
    path('', include('voyage.urls')),
    path('admin/', admin.site.urls),
    path('health/', views.health_check, name='health_check'),
    path('ready/', views.readiness_check, name='readiness_check'),
    path('live/', views.liveness_check, name='liveness_check'),
]
```

- [ ] **Step 3: Run view tests — expect all to pass**

```bash
.venv/Scripts/python manage.py test ob_forecast --verbosity=2
```

Expected:
```
test_14_days_produces_zscore ... ok
test_aggregate_creates_signals ... ok
test_chart_data_endpoint_empty ... ok
test_chart_data_returns_series ... ok
test_chart_data_unknown_zone ... ok
test_csv_upload_parses_oceanbolt_format ... ok
test_daily_entry_saves_values ... ok
test_no_data_returns_insufficient ... ok
...
Ran N tests in X.XXXs
OK
```

- [ ] **Step 4: Commit**

```bash
git add ob_forecast/urls.py config/urls.py
git commit -m "feat(ob_forecast): add URL routes and wire into config"
```

---

## Task 7: Template

**Files:**
- Create: `ob_forecast/templates/ob_forecast/ob_forecast.html`

- [ ] **Step 1: Create the template directory (if not already done)**

```bash
mkdir -p ob_forecast/templates/ob_forecast
```

- [ ] **Step 2: Write `ob_forecast/templates/ob_forecast/ob_forecast.html`**

```html
{% extends "base.html" %}

{% block title %}OB Forecast - FreightDash{% endblock %}

{% block extra_css %}
<style>
    .signal-card { border: none; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); height: 100%; }
    .signal-card .card-header { border-radius: 12px 12px 0 0; font-weight: 600; }
    .badge-bullish { background-color: var(--success-color); }
    .badge-bearish { background-color: var(--danger-color); }
    .badge-neutral { background-color: var(--secondary-color); }
    .driver-list { font-size: 0.85rem; padding-left: 1.1rem; margin-bottom: 0; }
    .driver-list li { margin-bottom: 0.35rem; }
    .confidence-bar { height: 6px; border-radius: 3px; background: #e9ecef; overflow: hidden; }
    .confidence-fill { height: 100%; background: var(--primary-color); }
    .zone-tab { cursor: pointer; }
    .entry-section { border: none; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
</style>
{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">
        <i class="fas fa-chart-area me-2"></i>OB Forecast
        <small class="text-muted fs-6 fw-normal ms-2">Panamax &middot; Pacific Zones</small>
    </h2>
    <form method="post" action="{% url 'ob_forecast:ob_aggregate' %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary">
            <i class="fas fa-bolt me-1"></i>Run Forecast
        </button>
    </form>
</div>

{# Signal cards #}
<div class="row g-3 mb-4">
    {% for card in cards %}
    <div class="col-md-6 col-xl-3">
        <div class="card signal-card">
            <div class="card-header d-flex justify-content-between align-items-center bg-white">
                <span>{{ card.label }}</span>
                <span class="badge badge-{{ card.signal.direction }} text-uppercase">{{ card.signal.direction }}</span>
            </div>
            <div class="card-body">
                <div class="d-flex justify-content-between mb-1">
                    <small class="text-muted">Score</small>
                    <strong>{{ card.signal.score|floatformat:2 }}</strong>
                </div>
                <div class="d-flex justify-content-between mb-1">
                    <small class="text-muted">Confidence</small>
                    <strong>{{ card.confidence_pct }}%</strong>
                </div>
                <div class="confidence-bar mb-2">
                    <div class="confidence-fill" style="width: {{ card.confidence_pct }}%"></div>
                </div>
                <div class="text-muted mb-2" style="font-size:0.75rem;">
                    Method: {{ card.signal.method }} &middot; {{ card.signal.data_days }}d data &middot; P3A_82
                </div>
                <hr class="my-2">
                <ul class="driver-list">
                    {% for driver in card.signal.drivers %}
                    <li>{{ driver }}</li>
                    {% empty %}
                    <li class="text-muted">No notable drivers.</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

{# Chart #}
<div class="card mb-4" style="border:none; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div class="card-body">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h5 class="mb-0">Tonnage history vs P3A_82</h5>
            <ul class="nav nav-pills" id="zoneTabs">
                {% for zone_key, zone_label in zones %}
                <li class="nav-item">
                    <a class="nav-link zone-tab {% if forloop.first %}active{% endif %}"
                       data-zone="{{ zone_key }}">{{ zone_label }}</a>
                </li>
                {% endfor %}
            </ul>
        </div>
        <canvas id="obChart" height="100"></canvas>
    </div>
</div>

{# Data entry #}
<div class="row g-3 mb-4">
    <div class="col-md-6">
        <div class="card entry-section">
            <div class="card-body">
                <h5 class="mb-3"><i class="fas fa-keyboard me-2"></i>Quick Daily Entry</h5>
                <form method="post" action="{% url 'ob_forecast:ob_daily_entry' %}">
                    {% csrf_token %}
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Date</label>
                        <input type="date" name="entry_date" class="form-control"
                               value="{{ today|date:'Y-m-d' }}" required>
                    </div>
                    {% for zone_key, zone_label in zones %}
                    <div class="mb-3">
                        <div class="fw-semibold text-primary mb-2" style="font-size:0.85rem;">{{ zone_label }}</div>
                        <div class="row g-2">
                            {% for series_key, series_label in series_choices %}
                            <div class="col-4">
                                <label class="form-label" style="font-size:0.75rem;">{{ series_label }}</label>
                                <input type="number"
                                       name="{{ zone_key }}_{{ series_key }}"
                                       class="form-control form-control-sm"
                                       placeholder="—"
                                       min="0">
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                    <button type="submit" class="btn btn-success w-100">
                        <i class="fas fa-save me-1"></i>Save Today's Data
                    </button>
                </form>
            </div>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card entry-section mb-3">
            <div class="card-body">
                <h5 class="mb-3"><i class="fas fa-file-csv me-2"></i>CSV Upload (Bulk / Catch-up)</h5>
                <form method="post" action="{% url 'ob_forecast:ob_upload' %}" enctype="multipart/form-data">
                    {% csrf_token %}
                    <div class="mb-2">
                        <label class="form-label fw-semibold">Zone</label>
                        <select name="zone" class="form-select" required>
                            <option value="">— select zone —</option>
                            {% for zone_key, zone_label in zones %}
                            <option value="{{ zone_key }}">{{ zone_label }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-2">
                        <label class="form-label fw-semibold">Series</label>
                        <select name="series" class="form-select" required>
                            <option value="">— select series —</option>
                            {% for series_key, series_label in series_choices %}
                            <option value="{{ series_key }}">{{ series_label }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Oceanbolt CSV</label>
                        <input type="file" name="csv_file" class="form-control" accept=".csv" required>
                        <div class="form-text">Expects columns: Date, Vessel Count, Vessel DWT</div>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">
                        <i class="fas fa-upload me-1"></i>Upload
                    </button>
                </form>
            </div>
        </div>

        {% if upload_log %}
        <div class="card entry-section">
            <div class="card-body">
                <h6 class="mb-2">Recent uploads</h6>
                <div class="table-responsive">
                    <table class="table table-sm mb-0">
                        <thead>
                            <tr>
                                <th>Time</th><th>Zone</th><th>Series</th>
                                <th>Added</th><th>Skipped</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for log in upload_log %}
                            <tr>
                                <td>{{ log.uploaded_at|date:"m-d H:i" }}</td>
                                <td>{{ log.zone_label }}</td>
                                <td>{{ log.series_label }}</td>
                                <td class="text-success">+{{ log.rows_added }}</td>
                                <td class="text-muted">{{ log.rows_skipped }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('obChart').getContext('2d');
    let chart = null;

    const OB_SERIES = [
        { key: 'BALLAST_AT_SEA', label: 'Ballast at Sea', color: '#dc3545' },
        { key: 'IN_PORT',        label: 'In Port',         color: '#fd7e14' },
        { key: 'TOTAL',          label: 'Total',           color: '#6610f2' },
    ];

    function render(data) {
        const datasets = OB_SERIES.map(function (s) {
            return {
                label: s.label,
                data: (data.series[s.key] || []).map(function (y, i) {
                    return { x: data.labels[i], y: y };
                }),
                borderColor: s.color,
                backgroundColor: s.color,
                yAxisID: 'ySupply',
                tension: 0.2,
                pointRadius: 0,
            };
        });
        if (data.index && data.index.length) {
            datasets.push({
                label: data.index_name || 'P3A_82',
                data: data.index,
                borderColor: '#1e3c72',
                borderWidth: 2,
                borderDash: [6, 3],
                yAxisID: 'yIndex',
                tension: 0.2,
                pointRadius: 0,
            });
        }
        if (chart) { chart.destroy(); }
        chart = new Chart(ctx, {
            type: 'line',
            data: { labels: data.labels, datasets: datasets },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: { type: 'category' },
                    ySupply: {
                        type: 'linear', position: 'left',
                        title: { display: true, text: 'Vessel count' }
                    },
                    yIndex: {
                        type: 'linear', position: 'right',
                        title: { display: true, text: 'P3A_82' },
                        grid: { drawOnChartArea: false }
                    },
                },
            },
        });
    }

    function load(zone) {
        fetch('/ob-forecast/chart-data/' + zone + '/')
            .then(function (r) { return r.json(); })
            .then(render)
            .catch(function (e) { console.error('Chart load failed', e); });
    }

    document.querySelectorAll('.zone-tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.zone-tab').forEach(function (t) {
                t.classList.remove('active');
            });
            tab.classList.add('active');
            load(tab.getAttribute('data-zone'));
        });
    });

    const first = document.querySelector('.zone-tab');
    if (first) { load(first.getAttribute('data-zone')); }
});
</script>
{% endblock %}
```

- [ ] **Step 3: Run all tests to confirm nothing broke**

```bash
.venv/Scripts/python manage.py test ob_forecast --verbosity=2
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add ob_forecast/templates/
git commit -m "feat(ob_forecast): add dashboard template with signal cards, chart, and data entry"
```

---

## Task 8: End-to-End Verification + MenuItem

**Files:** None (verification + Django admin action)

- [ ] **Step 1: Start the dev server**

```bash
.venv/Scripts/python manage.py runserver
```

Open http://127.0.0.1:8000/ob-forecast/ — expect the page to load with 4 grey "insufficient" signal cards, an empty chart, the quick entry form, and the CSV upload form.

- [ ] **Step 2: Upload the sample CSV**

In the CSV Upload section:
- Zone: **NE Asia**
- Series: **Total**
- File: `C:\Users\juan.vanvyve\Downloads\2026-06-16T08_24_23Z.csv`
- Click Upload

Expected: page reloads; "Recent uploads" table shows 1 row with rows_added = 167 (or the number of rows in the file).

- [ ] **Step 3: Verify data in DB**

```bash
.venv/Scripts/python manage.py shell -c "
from ob_forecast.models import OBTonnageSnapshot
print('Rows:', OBTonnageSnapshot.objects.count())
print('First:', OBTonnageSnapshot.objects.order_by('date').first())
print('Last:', OBTonnageSnapshot.objects.order_by('-date').first())
"
```

Expected: ~167 rows, first date 2026-01-01, last date 2026-06-16.

- [ ] **Step 4: Enter today's quick-entry data**

Fill in the Quick Daily Entry form with any test values (e.g., NE Asia Ballast=52, In Port=27, Total=64) and click Save. Expected: page reloads, no error.

- [ ] **Step 5: Run the forecast**

Click the "Run Forecast" button. Page reloads.

Expected: NE Asia signal card now shows method = `zscore` (enough data from step 2) with a direction and score. Other zones show `insufficient` (no data yet).

- [ ] **Step 6: Verify the chart**

Click the NE Asia tab in the chart area. Expected: a purple "Total" line appears across the 180-day range. The dashed blue P3A_82 overlay appears if P3A_82 data is in the DB.

- [ ] **Step 7: Add MenuItem via Django admin**

Go to http://127.0.0.1:8000/admin/core/menuitem/add/

Fill in:
- Title: `OB Forecast`
- URL: `/ob-forecast/`
- Icon: `fas fa-chart-area`
- Order: (set to a number higher than the existing Supply Forecast item)
- is_active: ✓

Save. Reload any FreightDash page. Expected: "OB Forecast" appears in the sidebar navigation.

- [ ] **Step 8: Run the full test suite**

```bash
.venv/Scripts/python manage.py test --verbosity=2
```

Expected: all existing supply + voyage tests still pass; new ob_forecast tests pass.

- [ ] **Step 9: Final commit**

```bash
git add .
git commit -m "feat(ob_forecast): complete OB Forecast module — zones, analytics, upload, dashboard"
```
