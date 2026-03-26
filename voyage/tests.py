from django.test import TestCase
from .models import RouteParameters
from .calculators import calculate_fuel_and_days, calculate_tce, calculate_freight_from_tce


class TCECalculatorTestCase(TestCase):
    def setUp(self):
        self.route = RouteParameters.objects.create(
            route='Test Route'
        )
    
    def test_route_creation(self):
        self.assertEqual(self.route.route, 'Test Route')
        self.assertEqual(self.route.ballast_distance, 3496)
    
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
