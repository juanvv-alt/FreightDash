from datetime import date, timedelta

from django.test import TestCase
import pandas as pd

from voyage.models import AvailableIndex, DailyIndexValue

from .analytics import (
    OBSignalResult,
    _nearest_price,
    generate_ob_signal,
    load_panamax_index,
    load_zone_frame,
    persist_ob_signal,
    SERIES_WEIGHTS,
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

    def test_56_days_produces_regression_or_zscore(self):
        self._seed_zone("NE_ASIA", days=60)
        result = generate_ob_signal("NE_ASIA")
        # With 60 days of data, regression may or may not fire depending on
        # weekly resampling boundary; both are valid — assert it's one of them
        self.assertIn(result.method, ("regression", "zscore"))
        # In regression case, blended score is 0.6*reg + 0.4*z
        if result.method == "regression":
            self.assertLessEqual(result.confidence, 0.90)
            self.assertTrue(len(result.drivers) >= 1)

    def test_in_port_weight_amplifies_bullish(self):
        """IN_PORT at 2× weight should dominate a bullish signal over equal BALLAST/TOTAL bearish."""
        self.assertEqual(SERIES_WEIGHTS["IN_PORT"], 2.0)
        today = date.today()
        # Create 20 days of data: IN_PORT strongly elevated, BALLAST mildly elevated
        for i in range(20):
            d = today - timedelta(days=19 - i)
            # baseline low, then spike on last day
            in_port = 30 + (20 if i == 19 else 0)  # spike last day
            ballast = 40 + (5 if i == 19 else 0)   # mild ballast rise (bearish)
            OBTonnageSnapshot.objects.create(date=d, zone="NE_ASIA", series="IN_PORT", vessel_count=in_port)
            OBTonnageSnapshot.objects.create(date=d, zone="NE_ASIA", series="BALLAST_AT_SEA", vessel_count=ballast)
        result = generate_ob_signal("NE_ASIA")
        # IN_PORT is bullish (2× weight), BALLAST is bearish (1× weight); 2× should tip result bullish
        self.assertEqual(result.direction, "bullish",
                         f"Expected bullish with dominant IN_PORT (2× weight), got {result.direction}")


class OBLoadPanamaxIndexTestCase(TestCase):
    def setUp(self):
        self.index, _ = AvailableIndex.objects.get_or_create(
            name="P3A_82",
            defaults={"vessel_size": "panamax"},
        )

    def test_empty_returns_empty_series(self):
        s = load_panamax_index()
        self.assertTrue(s.empty)

    def test_returns_date_indexed_series(self):
        today = date.today()
        DailyIndexValue.objects.create(index=self.index, date=today, value=9250)
        s = load_panamax_index()
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(float(s.iloc[0]), 9250.0)

    def test_as_of_filters_future_dates(self):
        today = date.today()
        DailyIndexValue.objects.create(index=self.index, date=today, value=9250)
        DailyIndexValue.objects.create(index=self.index, date=today + timedelta(days=1), value=9300)
        s = load_panamax_index(as_of=today)
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(float(s.iloc[0]), 9250.0)


class OBNearestPriceTestCase(TestCase):
    def test_nearest_price_exact_match(self):
        today = date.today()
        s = pd.Series([100.0, 101.0], index=pd.to_datetime([today - timedelta(days=1), today]))
        result = _nearest_price(s, today)
        self.assertAlmostEqual(result, 101.0)

    def test_nearest_price_forward_fill_gap(self):
        today = date.today()
        # Series has Friday data but not Saturday
        friday = today - timedelta(days=today.weekday() + 3)  # some past Friday
        saturday = friday + timedelta(days=1)
        s = pd.Series([99.0], index=pd.to_datetime([friday]))
        result = _nearest_price(s, saturday)
        self.assertAlmostEqual(result, 99.0)

    def test_nearest_price_exceeds_gap(self):
        today = date.today()
        old_date = today - timedelta(days=10)
        s = pd.Series([99.0], index=pd.to_datetime([old_date]))
        result = _nearest_price(s, today)
        self.assertIsNone(result)

    def test_nearest_price_empty_series(self):
        s = pd.Series(dtype=float)
        self.assertIsNone(_nearest_price(s, date.today()))


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
        self.assertEqual(data["index"], [])

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
        import io as _io
        csv_content = (
            "Date,Vessel Count,Vessel DWT\r\n"
            "2026-01-01T00:00:00Z,52,3200000\r\n"
            "2026-01-02T00:00:00Z,50,3100000\r\n"
        )
        f = _io.BytesIO(csv_content.encode("utf-8"))
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
        for i in range(5):
            d = today - timedelta(days=i)
            OBTonnageSnapshot.objects.create(date=d, zone="NE_ASIA", series="TOTAL", vessel_count=60)
        resp = self.client.post("/ob-forecast/aggregate/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OBForecastSignal.objects.filter(date=today, zone="NE_ASIA").exists())

    def test_delete_series_shows_confirmation(self):
        today = date.today()
        OBTonnageSnapshot.objects.create(
            date=today, zone="NE_ASIA", series="BALLAST_AT_SEA", vessel_count=52
        )
        resp = self.client.post(
            "/ob-forecast/delete-series/",
            {"zone": "NE_ASIA", "series": "BALLAST_AT_SEA"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "NE Asia")
        self.assertContains(resp, "Ballast at Sea")

    def test_delete_series_confirmed_removes_rows_and_signals(self):
        today = date.today()
        OBTonnageSnapshot.objects.create(
            date=today, zone="NE_ASIA", series="BALLAST_AT_SEA", vessel_count=52
        )
        OBForecastSignal.objects.create(
            date=today, zone="NE_ASIA", direction="bullish",
            score=1.0, confidence=0.5, method="zscore", data_days=20,
        )
        resp = self.client.post(
            "/ob-forecast/delete-series/",
            {"zone": "NE_ASIA", "series": "BALLAST_AT_SEA", "confirmed": "1"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            OBTonnageSnapshot.objects.filter(zone="NE_ASIA", series="BALLAST_AT_SEA").count(), 0
        )
        self.assertEqual(OBForecastSignal.objects.filter(zone="NE_ASIA").count(), 0)

    def test_delete_series_rejects_invalid_zone(self):
        resp = self.client.post(
            "/ob-forecast/delete-series/",
            {"zone": "FAKE", "series": "BALLAST_AT_SEA"},
        )
        self.assertEqual(resp.status_code, 302)

    def test_delete_series_get_redirects(self):
        resp = self.client.get("/ob-forecast/delete-series/")
        self.assertEqual(resp.status_code, 302)

    def test_backtest_page_empty(self):
        resp = self.client.get("/ob-forecast/backtest/NE_ASIA/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "NE Asia")

    def test_backtest_page_unknown_zone_redirects(self):
        resp = self.client.get("/ob-forecast/backtest/FAKE/")
        self.assertEqual(resp.status_code, 302)

    def test_run_backtest_computes_signals(self):
        today = date.today()
        for i in range(20):
            d = today - timedelta(days=i)
            OBTonnageSnapshot.objects.create(
                date=d, zone="NE_ASIA", series="TOTAL", vessel_count=60
            )
        resp = self.client.post("/ob-forecast/run-backtest/NE_ASIA/")
        self.assertEqual(resp.status_code, 302)
        self.assertGreater(OBForecastSignal.objects.filter(zone="NE_ASIA").count(), 0)

    def test_backtest_data_endpoint(self):
        today = date.today()
        OBForecastSignal.objects.create(
            date=today, zone="NE_ASIA", direction="bullish",
            score=1.2, confidence=0.5, method="zscore", data_days=20,
        )
        resp = self.client.get("/ob-forecast/backtest-data/NE_ASIA/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertIn("signal_score", data)
        self.assertIn("accuracy_pct", data)

    def test_backtest_data_lag_sweep(self):
        today = date.today()
        OBForecastSignal.objects.create(
            date=today - timedelta(days=30), zone="NE_ASIA", direction="bullish",
            score=1.2, confidence=0.5, method="zscore", data_days=20,
        )
        resp = self.client.get("/ob-forecast/backtest-data/NE_ASIA/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("lag_sweep", data)
        self.assertEqual(len(data["lag_sweep"]), 3)
        lags = [row["lag"] for row in data["lag_sweep"]]
        self.assertEqual(lags, [7, 14, 21])
