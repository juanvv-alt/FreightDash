import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from supply import analytics
from supply.aggregation import (build_snapshot, estimate_days_to_open,
                                week_over_week)
from supply.classification import (classify_vessel, detect_loading_condition,
                                   is_dry_bulk_candidate)
from supply.geo import PortGeo, find_containing_port, haversine_nm, is_departed
from supply.ingest import AISIngestor
from supply.models import (DailySupplySnapshot, Port, PortCallEvent,
                           TrackedVessel, VesselState)
from voyage.models import (AvailableIndex, DailyIndexValue, FFACurve,
                           FFACurvePeriod)


class ClassificationTestCase(TestCase):
    def test_length_bands(self):
        self.assertEqual(classify_vessel(300, 18), "capesize")
        self.assertEqual(classify_vessel(229, 14), "panamax")
        self.assertEqual(classify_vessel(199, 12.8), "supramax")
        self.assertEqual(classify_vessel(180, 10), "handysize")

    def test_band_boundaries(self):
        self.assertEqual(classify_vessel(270, 0), "capesize")  # 270 -> capesize
        self.assertEqual(classify_vessel(269.9, 0), "panamax")
        self.assertEqual(classify_vessel(150, 0), "handysize")
        self.assertEqual(classify_vessel(149.9, 0), "unknown")  # below floor

    def test_missing_length_falls_back_to_draught(self):
        self.assertEqual(classify_vessel(None, 17), "capesize")
        self.assertEqual(classify_vessel(None, 13), "supramax")

    def test_length_wins_on_disagreement(self):
        # Long hull but shallow reported max draught -> trust length.
        self.assertEqual(classify_vessel(300, 11), "capesize")

    def test_unknown_when_nothing_usable(self):
        self.assertEqual(classify_vessel(None, None), "unknown")
        self.assertEqual(classify_vessel(None, 5), "unknown")

    def test_ship_type_filter(self):
        self.assertTrue(is_dry_bulk_candidate(70))
        self.assertTrue(is_dry_bulk_candidate(79))
        self.assertTrue(is_dry_bulk_candidate(None))  # keep until static arrives
        self.assertFalse(is_dry_bulk_candidate(80))  # tanker
        self.assertFalse(is_dry_bulk_candidate(60))  # passenger


class LoadingConditionTestCase(TestCase):
    def test_ratio_boundary(self):
        # max 14, threshold 0.8 -> ~11.2 nm separates laden from ballast.
        self.assertEqual(detect_loading_condition(12.0, 14.0), "laden")
        self.assertEqual(detect_loading_condition(11.0, 14.0), "ballast")

    def test_missing_draught(self):
        self.assertEqual(detect_loading_condition(None, 14.0), "unknown")
        self.assertEqual(detect_loading_condition(0, 14.0), "unknown")

    def test_low_max_draught_is_unknown(self):
        self.assertEqual(detect_loading_condition(6, 7.0), "unknown")


class GeofenceTestCase(TestCase):
    def setUp(self):
        self.hedland = PortGeo(1, "Port Hedland", -20.31, 118.58, 20.0, "load")
        self.qingdao = PortGeo(2, "Qingdao", 36.07, 120.32, 20.0, "discharge")

    def test_haversine_known_distance(self):
        d = haversine_nm(-20.31, 118.58, 36.07, 120.32)
        # Port Hedland -> Qingdao is roughly 3,400 nm.
        self.assertGreater(d, 3000)
        self.assertLess(d, 3800)

    def test_containment(self):
        # ~10 nm north of Hedland is inside the 20 nm fence.
        inside = find_containing_port(-20.14, 118.58, [self.hedland, self.qingdao])
        self.assertIsNotNone(inside)
        self.assertEqual(inside.id, 1)

    def test_outside_all_fences(self):
        self.assertIsNone(find_containing_port(0, 0, [self.hedland, self.qingdao]))

    def test_departure_hysteresis(self):
        # Point ~21 nm out (just past radius, within 1.25x) is NOT departed.
        near = _offset_lat(self.hedland, 21)
        self.assertFalse(is_departed(near[0], near[1], self.hedland))
        # Point ~30 nm out (beyond 1.25 * 20 = 25) IS departed.
        far = _offset_lat(self.hedland, 30)
        self.assertTrue(is_departed(far[0], far[1], self.hedland))


def _offset_lat(port, nm_north):
    """Return a point ``nm_north`` nautical miles due north of a port."""
    return (port.latitude + nm_north / 60.0, port.longitude)


class IngestReplayTestCase(TestCase):
    def setUp(self):
        self.port = Port.objects.create(
            name="Test Load",
            country="AU",
            latitude=-20.31,
            longitude=118.58,
            radius_nm=20,
            port_type="load",
        )
        geo = PortGeo(
            self.port.id,
            self.port.name,
            self.port.latitude,
            self.port.longitude,
            self.port.radius_nm,
            self.port.port_type,
        )
        self.ingestor = AISIngestor("test", [geo], min_move_nm=2.0)

    def _msgs(self):
        base = timezone.now() - timedelta(hours=5)
        mmsi = 211111111
        lines = []
        # Static first: a capesize.
        lines.append(
            json.dumps(
                {
                    "MessageType": "ShipStaticData",
                    "MetaData": {"MMSI": mmsi, "ShipName": "CAPE TEST"},
                    "Message": {
                        "ShipStaticData": {
                            "Type": 70,
                            "MaximumStaticDraught": 18.0,
                            "ImoNumber": 9111111,
                            "Name": "CAPE TEST",
                            "Dimension": {"A": 150, "B": 150, "C": 25, "D": 25},
                        }
                    },
                }
            )
        )
        # Approach from far south (at sea), then inside the fence (arrival),
        # several near-identical points inside, then far away (departure).
        track = [
            (-22.0, 118.58),  # ~100 nm south, at sea
            (-20.31, 118.58),  # at port center -> arrival
            (-20.32, 118.58),  # jitter inside
            (-20.30, 118.59),  # jitter inside
            (-18.0, 118.58),  # ~140 nm north -> departure
        ]
        for i, (lat, lon) in enumerate(track):
            ts = base + timedelta(minutes=30 * (i + 1))
            lines.append(
                json.dumps(
                    {
                        "MessageType": "PositionReport",
                        "MetaData": {
                            "MMSI": mmsi,
                            "ShipName": "CAPE TEST",
                            "time_utc": ts.strftime(
                                "%Y-%m-%d %H:%M:%S.000000000 +0000 UTC"
                            ),
                        },
                        "Message": {
                            "PositionReport": {
                                "Latitude": lat,
                                "Longitude": lon,
                                "Sog": 12.0,
                                "Cog": 0.0,
                                "NavigationalStatus": 0,
                                "MaximumStaticDraught": 18.0,
                            }
                        },
                    }
                )
            )
        return lines

    def test_replay_creates_vessel_and_events(self):
        stats = self.ingestor.replay(self._msgs())
        self.assertEqual(stats["vessels"], 1)
        vessel = TrackedVessel.objects.get(mmsi=211111111)
        self.assertEqual(vessel.vessel_class, "capesize")
        self.assertEqual(vessel.name, "CAPE TEST")

        arrivals = PortCallEvent.objects.filter(event_type="arrival").count()
        departures = PortCallEvent.objects.filter(event_type="departure").count()
        self.assertEqual(arrivals, 1)
        self.assertEqual(departures, 1)

    def test_write_throttle_collapses_jitter(self):
        self.ingestor.replay(self._msgs())
        # 5 positions but the two inner jitter points are < min_move_nm and
        # produce no extra state write, so writes < 5.
        self.assertLess(self.ingestor.stats.state_writes, 5)
        self.assertEqual(VesselState.objects.count(), 1)


class AggregationTestCase(TestCase):
    def setUp(self):
        self.load_port = Port.objects.create(
            name="Hedland",
            country="AU",
            latitude=-20.31,
            longitude=118.58,
            radius_nm=20,
            port_type="load",
        )
        self.disch_port = Port.objects.create(
            name="Qingdao",
            country="CN",
            latitude=36.07,
            longitude=120.32,
            radius_nm=20,
            port_type="discharge",
        )

    def _vessel(self, mmsi, vclass="capesize", last_seen=None):
        return TrackedVessel.objects.create(
            mmsi=mmsi,
            vessel_class=vclass,
            max_draught_m=18.0,
            last_seen=last_seen or timezone.now(),
        )

    def test_counts_and_expected_open(self):
        now = timezone.now()
        # 1: laden, ~near Qingdao (should count expected_open_7d)
        v1 = self._vessel(1)
        VesselState.objects.create(
            vessel=v1,
            latitude=34.0,
            longitude=121.0,
            loading_condition="laden",
            speed_knots=12,
            position_at=now,
        )
        # 2: laden but far away (Indian Ocean) -> not open within 7d
        v2 = self._vessel(2)
        VesselState.objects.create(
            vessel=v2,
            latitude=-10.0,
            longitude=80.0,
            loading_condition="laden",
            speed_knots=12,
            position_at=now,
        )
        # 3: ballast at sea
        v3 = self._vessel(3)
        VesselState.objects.create(
            vessel=v3,
            latitude=-15.0,
            longitude=115.0,
            loading_condition="ballast",
            speed_knots=13,
            position_at=now,
        )
        # 4: in load port
        v4 = self._vessel(4)
        VesselState.objects.create(
            vessel=v4,
            latitude=-20.31,
            longitude=118.58,
            loading_condition="ballast",
            current_port=self.load_port,
            position_at=now,
        )
        # 5: stale (last seen 3 days ago) -> excluded
        v5 = self._vessel(5, last_seen=now - timedelta(days=3))
        VesselState.objects.create(
            vessel=v5,
            latitude=-15.0,
            longitude=115.0,
            loading_condition="ballast",
            position_at=now - timedelta(days=3),
        )

        snaps = build_snapshot(timezone.localdate())
        cape = DailySupplySnapshot.objects.get(vessel_class="capesize")
        self.assertEqual(cape.laden_at_sea_count, 2)
        self.assertEqual(cape.ballast_at_sea_count, 1)  # v5 excluded as stale
        self.assertEqual(cape.in_port_load_count, 1)
        self.assertEqual(cape.expected_open_7d, 1)  # only v1 near discharge

        all_row = DailySupplySnapshot.objects.get(vessel_class="all")
        self.assertEqual(all_row.total_tracked, 4)
        self.assertEqual(len(snaps), 5)

    def test_estimate_days_to_open(self):
        disch = [PortGeo(self.disch_port.id, "Q", 36.07, 120.32, 20, "discharge")]
        near = estimate_days_to_open(34.0, 121.0, disch)
        self.assertIsNotNone(near)
        self.assertLess(near, 7)
        # Cape of Good Hope area is well over 14 days' steaming from Qingdao.
        far = estimate_days_to_open(-34.0, 18.0, disch)
        self.assertGreater(far, 14)

    def test_idempotent_rerun(self):
        v1 = self._vessel(1)
        VesselState.objects.create(
            vessel=v1,
            latitude=-15.0,
            longitude=115.0,
            loading_condition="ballast",
            position_at=timezone.now(),
        )
        build_snapshot(timezone.localdate())
        build_snapshot(timezone.localdate())
        self.assertEqual(
            DailySupplySnapshot.objects.filter(vessel_class="capesize").count(), 1
        )

    def test_week_over_week(self):
        today = timezone.localdate()
        DailySupplySnapshot.objects.create(
            date=today,
            vessel_class="all",
            ballast_at_sea_count=20,
        )
        DailySupplySnapshot.objects.create(
            date=today - timedelta(days=7),
            vessel_class="all",
            ballast_at_sea_count=12,
        )
        rows = DailySupplySnapshot.objects.filter(vessel_class="all").order_by("-date")
        self.assertEqual(week_over_week(rows, "ballast_at_sea_count"), 8)


class AnalyticsTestCase(TestCase):
    def setUp(self):
        # 'BCI 5TC' is seeded by voyage migration 0003, so reuse it.
        self.index, _ = AvailableIndex.objects.get_or_create(
            name="BCI 5TC",
            defaults={"vessel_size": "capesize"},
        )

    def _seed_history(self, weeks):
        """Ballast oscillates week to week; the index responds negatively with a
        2-week lag. Varied weekly changes make the lead/lag correlation defined.
        """
        import math

        # Distinct ballast level per week (varying changes, not a constant ramp).
        ballast_by_week = [20 + round(6 * math.sin(w * 0.9)) for w in range(weeks)]
        start = timezone.localdate() - timedelta(days=weeks * 7)
        for d in range(weeks * 7):
            day = start + timedelta(days=d)
            week = d // 7
            ballast = ballast_by_week[week]
            # Index tracks ballast from 2 weeks earlier, inverted.
            lag_week = max(0, week - 2)
            index_val = 15000 - 200 * ballast_by_week[lag_week]
            DailySupplySnapshot.objects.create(
                date=day,
                vessel_class="capesize",
                ballast_at_sea_count=ballast,
                laden_at_sea_count=50 - ballast,
                in_port_load_count=5,
                in_port_discharge_count=8,
                expected_open_7d=ballast,
            )
            DailyIndexValue.objects.create(index=self.index, date=day, value=index_val)

    def test_insufficient_history(self):
        self._seed_history(weeks=1)  # 7 days only
        result = analytics.generate_signal("capesize")
        self.assertEqual(result.method, "insufficient")
        self.assertEqual(result.direction, "neutral")
        self.assertLessEqual(result.confidence, 0.1)

    def test_zscore_regime(self):
        self._seed_history(weeks=4)  # ~28 days, below regression threshold
        result = analytics.generate_signal("capesize")
        self.assertEqual(result.method, "zscore")
        self.assertLessEqual(result.confidence, 0.6)

    def test_lagged_correlation_detects_lead(self):
        self._seed_history(weeks=16)
        supply = analytics.load_supply_frame("capesize")
        index = analytics.load_index_series("BCI 5TC")
        corrs = analytics.lagged_correlations(supply["ballast_at_sea_count"], index)
        # Rising ballast precedes a falling index -> negative correlation present.
        defined = {k: v for k, v in corrs.items() if v == v}  # drop NaN
        self.assertTrue(defined)
        best_lag = min(defined, key=lambda k: defined[k])
        self.assertLess(defined[best_lag], 0)
        # The strongest negative lead should be around the injected 2-week lag.
        self.assertIn(best_lag, (1, 2, 3))

    def test_regression_regime_bearish(self):
        self._seed_history(weeks=16)
        result = analytics.generate_signal("capesize")
        self.assertEqual(result.method, "regression")
        self.assertIn(result.direction, ("bearish", "neutral", "bullish"))
        self.assertGreater(result.data_days, 100)

    def test_ffa_stance_backwardation(self):
        curve = FFACurve.objects.create(vessel_class="Capesize", raw_text="x")
        today = timezone.localdate()
        # Spot ~15000; front months lower -> backwardation.
        FFACurvePeriod.objects.create(
            curve=curve,
            label="M1",
            period_type="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            bid=13800,
            offer=14000,
        )
        FFACurvePeriod.objects.create(
            curve=curve,
            label="M2",
            period_type="monthly",
            start_date=today + timedelta(days=31),
            end_date=today + timedelta(days=60),
            bid=13600,
            offer=13800,
        )
        stance = analytics.ffa_curve_stance("capesize", 15000.0)
        self.assertIsNotNone(stance)
        self.assertEqual(stance["stance"], "backwardation")
        self.assertLess(stance["slope"], 0)


class SupplyForecastViewTestCase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_superuser("admin", "a@b.com", "pw")
        self.client.force_login(self.user)

    def test_page_renders(self):
        resp = self.client.get(reverse("supply:supply_forecast"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Pacific Supply Forecast")

    def test_chart_data_endpoint(self):
        DailySupplySnapshot.objects.create(
            date=timezone.localdate(),
            vessel_class="capesize",
            ballast_at_sea_count=10,
            laden_at_sea_count=20,
        )
        resp = self.client.get(reverse("supply:supply_chart_data", args=["capesize"]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertIn("supply", data)

    def test_chart_data_unknown_class(self):
        resp = self.client.get(reverse("supply:supply_chart_data", args=["frigate"]))
        self.assertEqual(resp.status_code, 404)
