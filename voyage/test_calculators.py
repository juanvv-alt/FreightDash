"""
Characterization tests for voyage.calculators.

These pin the CURRENT numeric behaviour of the pure calculation functions so the
Phase 3 refactor (splitting views.py, extracting a service layer) can be proven
behaviour-preserving. If a value here changes, that is a deliberate maths change
and must be reviewed — not an incidental refactor side effect.

Reference values were captured by running the functions as they stand today.
"""
import unittest

from voyage.calculators import (calculate_freight_from_tce,
                                calculate_fuel_and_days, calculate_tce,
                                calculate_vessel_comparison)

# A single representative voyage reused across the fuel/TCE/freight tests.
COMMON_INPUTS = dict(
    ballast_distance=2000,
    laden_distance=3000,
    intake=70000,
    load_rate=20000,
    discharge_rate=25000,
    turntime_hours=24,
    port_exp_load_port=50000,
    port_exp_discharge_port=60000,
    freight_commission_pct=3.75,
    sea_margin_pct=5,
    ballast_speed=12,
    laden_speed=12.5,
    ballast_consumption=30,
    laden_consumption=35,
    port_consumption=5,
)


class CalculateFuelAndDaysTests(unittest.TestCase):
    def setUp(self):
        self.result = calculate_fuel_and_days(**COMMON_INPUTS)

    def test_voyage_days(self):
        self.assertAlmostEqual(self.result["voyage_days"], 25.091666666666665, places=9)

    def test_total_fuel_consumed(self):
        self.assertAlmostEqual(self.result["total_fuel_consumed"], 622.75, places=6)

    def test_total_port_expenses(self):
        self.assertEqual(self.result["total_port_expenses"], 110000)

    def test_freight_commission_is_decimalised(self):
        self.assertAlmostEqual(self.result["freight_commission"], 0.0375, places=9)


class CalculateTceTests(unittest.TestCase):
    def test_tce_from_freight_rate(self):
        common = calculate_fuel_and_days(**COMMON_INPUTS)
        tce = calculate_tce(25.0, 600.0, 70000, common)
        self.assertAlmostEqual(tce, 47853.53703088675, places=4)


class CalculateFreightFromTceTests(unittest.TestCase):
    def test_freight_from_target_tce(self):
        common = calculate_fuel_and_days(**COMMON_INPUTS)
        freight = calculate_freight_from_tce(15000.0, 600.0, 70000, common)
        self.assertAlmostEqual(freight, 12.764749536178108, places=9)

    def test_zero_intake_returns_zero(self):
        common = calculate_fuel_and_days(**COMMON_INPUTS)
        self.assertEqual(calculate_freight_from_tce(15000.0, 600.0, 0, common), 0)


class CalculateVesselComparisonTests(unittest.TestCase):
    def setUp(self):
        self.global_inputs = {
            "hire": 15000,
            "ifo_price": 600,
            "mgo_price": 800,
            "weather_factor": 1.07,
        }
        self.voyages = [
            {
                "name": "V1",
                "ballast_dist": 2000,
                "laden_dist": 3000,
                "load_rate": 20000,
                "dis_rate": 25000,
                "load_factor": 1.0,
                "dis_factor": 1.0,
                "turntimes_hours": 24,
                "port_exp": 50000,
                "various_exp": 10000,
            }
        ]
        self.vessels = [
            {
                "name": "BKI",
                "intakes": [70000],
                "laden_speed": 12.5,
                "ballast_speed": 12,
                "laden_cons": 35,
                "ballast_cons": 30,
                "port_cons": 5,
            },
            {
                "name": "MyShip",
                "intakes": [72000],
                "laden_speed": 13,
                "ballast_speed": 12.5,
                "laden_cons": 32,
                "ballast_cons": 28,
                "port_cons": 4,
            },
        ]
        self.result = calculate_vessel_comparison(
            self.global_inputs, self.voyages, self.vessels
        )

    def test_bki_breakeven_freight(self):
        self.assertAlmostEqual(
            self.result["voyage_results"][0]["bki_freight"],
            11.564829861111113,
            places=9,
        )

    def test_bki_tce_equals_hire_after_commission(self):
        # BKI is solved to breakeven, so its TCE pins to hire * commission_factor.
        self.assertAlmostEqual(
            self.result["voyage_results"][0]["bki_tce"], 14437.5, places=4
        )

    def test_competitor_pct_vs_bki(self):
        pct = self.result["voyage_results"][0]["vessels"][1]["pct_vs_bki"]
        self.assertAlmostEqual(pct, 1.2109077447397207, places=9)

    def test_weighted_averages(self):
        self.assertAlmostEqual(self.result["weighted_avgs"][0], 1.0, places=9)
        self.assertAlmostEqual(
            self.result["weighted_avgs"][1], 1.2109077447397207, places=9
        )


if __name__ == "__main__":
    unittest.main()
