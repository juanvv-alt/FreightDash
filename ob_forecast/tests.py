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
