"""
Smoke tests for the main voyage pages.

These assert each page renders (HTTP 200) on an essentially empty database, so the
Phase 3 split of voyage/views.py into a package can be proven not to break routing,
imports, or template rendering. They are deliberately shallow — the numeric
guarantees live in test_calculators.py.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class VoyagePageSmokeTests(TestCase):
    def setUp(self):
        # All app pages sit behind core.middleware.LoginRequiredMiddleware,
        # so smoke tests run as an authenticated user.
        user = get_user_model().objects.create_user("smoke", password="x")
        self.client.force_login(user)

    def test_tce_calculator_renders(self):
        response = self.client.get(reverse("voyage:tce_calculator"))
        self.assertEqual(response.status_code, 200)

    def test_freight_matrix_renders(self):
        response = self.client.get(reverse("voyage:freight_matrix"))
        self.assertEqual(response.status_code, 200)

    def test_vessel_compare_renders(self):
        response = self.client.get(reverse("voyage:vessel_compare"))
        self.assertEqual(response.status_code, 200)

    def test_ffa_valuation_renders(self):
        response = self.client.get(reverse("voyage:ffa-valuation"))
        self.assertEqual(response.status_code, 200)

    def test_indices_redirect(self):
        # /indices/ redirects to the default vessel tab.
        response = self.client.get(reverse("voyage:indices"))
        self.assertIn(response.status_code, (301, 302))


class TceCalculationResponseTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("smoke", password="x")
        self.client.force_login(user)

    def test_calculate_tce_populates_context(self):
        response = self.client.post(
            reverse("voyage:tce_calculator"),
            {
                "ballast_distance": "2000",
                "laden_distance": "3000",
                "intake": "70000",
                "load_rate": "20000",
                "discharge_rate": "25000",
                "turntime_hours": "24",
                "port_exp_load_port": "50000",
                "port_exp_discharge_port": "60000",
                "freight_commission_pct": "3.75",
                "sea_margin_pct": "5",
                "ballast_speed": "12",
                "laden_speed": "12.5",
                "ballast_consumption": "30",
                "laden_consumption": "35",
                "port_consumption": "5",
                "freight_rate": "25",
                "fuel_price": "600",
                "tce_field": "0",
                "calc_tce": "Calculate TCE",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["calculated_tce"])
