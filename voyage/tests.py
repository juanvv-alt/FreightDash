from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import RouteParameters
from .calculators import calculate_fuel_and_days, calculate_tce, calculate_freight_from_tce


class TCECalculatorTestCase(TestCase):
    def setUp(self):
        # Pages are gated by core.middleware.LoginRequiredMiddleware.
        user = get_user_model().objects.create_user('tester', password='x')
        self.client.force_login(user)
        self.route = RouteParameters.objects.create(
            route='Test Route',
            ballast_distance=2800,
            laden_distance=3100,
            intake=180000,
        )
    
    def test_route_creation(self):
        self.assertEqual(self.route.route, 'Test Route')
        self.assertEqual(self.route.ballast_distance, 2800)
    
    def test_fuel_and_days_calculation(self):
        result = calculate_fuel_and_days(
            ballast_distance=3496,
            laden_distance=3494,
            intake=173500,
            load_rate=90000,
            discharge_rate=30000,
            turntime_hours=30,
            port_exp_load_port=145000,
            port_exp_discharge_port=120000,
            freight_commission_pct=5,
            sea_margin_pct=7,
            ballast_speed=13,
            laden_speed=12,
            ballast_consumption=43,
            laden_consumption=43,
            port_consumption=7.5
        )
        
        self.assertIn('voyage_days', result)
        self.assertIn('total_fuel_consumed', result)
        self.assertIn('total_port_expenses', result)
        self.assertGreater(result['voyage_days'], 0)

    def test_route_selection_prefills_database_values(self):
        response = self.client.post(reverse('voyage:tce_calculator'), {
            'route': str(self.route.id),
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form['ballast_distance'].value(), 2800.0)
        self.assertEqual(form['laden_distance'].value(), 3100.0)

    def test_calculation_uses_posted_route_values(self):
        response = self.client.post(reverse('voyage:tce_calculator'), {
            'route': str(self.route.id),
            'ballast_distance': '2800',
            'laden_distance': '3100',
            'intake': '180000',
            'load_rate': '90000',
            'discharge_rate': '30000',
            'turntime_hours': '30',
            'port_exp_load_port': '145000',
            'port_exp_discharge_port': '120000',
            'freight_commission_pct': '5',
            'sea_margin_pct': '7',
            'ballast_speed': '13',
            'laden_speed': '12',
            'ballast_consumption': '43',
            'laden_consumption': '43',
            'port_consumption': '7.5',
            'freight_rate': '10',
            'fuel_price': '495',
            'tce_field': '0',
            'calc_tce': 'Calculate TCE',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['calculated_tce'])
