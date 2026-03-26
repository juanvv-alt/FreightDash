from django.core.management.base import BaseCommand
from voyage.models import RouteParameters


class Command(BaseCommand):
    help = 'Create sample shipping routes for TCE calculator'

    def handle(self, *args, **options):
        routes = [
            {
                'route': 'China-Australia',
                'ballast_distance': 2800,
                'laden_distance': 2800,
                'intake': 180000,
                'load_rate': 95000,
                'discharge_rate': 32000,
                'turntime_hours': 28,
                'port_exp_load_port': 150000,
                'port_exp_discharge_port': 125000,
                'freight_commission_pct': 4.75,
                'sea_margin_pct': 5,
                'ballast_speed': 13.5,
                'laden_speed': 12.0,
                'ballast_consumption': 45,
                'laden_consumption': 42,
                'port_consumption': 8,
            },
            {
                'route': 'Brazil-China',
                'ballast_distance': 6200,
                'laden_distance': 6200,
                'intake': 160000,
                'load_rate': 80000,
                'discharge_rate': 28000,
                'turntime_hours': 35,
                'port_exp_load_port': 160000,
                'port_exp_discharge_port': 140000,
                'freight_commission_pct': 5,
                'sea_margin_pct': 7,
                'ballast_speed': 13,
                'laden_speed': 12,
                'ballast_consumption': 43,
                'laden_consumption': 43,
                'port_consumption': 7.5,
            },
            {
                'route': 'South Africa-India',
                'ballast_distance': 4100,
                'laden_distance': 4100,
                'intake': 170000,
                'load_rate': 88000,
                'discharge_rate': 30000,
                'turntime_hours': 30,
                'port_exp_load_port': 140000,
                'port_exp_discharge_port': 120000,
                'freight_commission_pct': 5,
                'sea_margin_pct': 7,
                'ballast_speed': 13.2,
                'laden_speed': 12.0,
                'ballast_consumption': 44,
                'laden_consumption': 43,
                'port_consumption': 7.5,
            },
            {
                'route': 'Indonesia-Pacific',
                'ballast_distance': 2200,
                'laden_distance': 2200,
                'intake': 175000,
                'load_rate': 92000,
                'discharge_rate': 31000,
                'turntime_hours': 26,
                'port_exp_load_port': 130000,
                'port_exp_discharge_port': 115000,
                'freight_commission_pct': 4.5,
                'sea_margin_pct': 6,
                'ballast_speed': 13.8,
                'laden_speed': 12.2,
                'ballast_consumption': 46,
                'laden_consumption': 44,
                'port_consumption': 7.5,
            },
            {
                'route': 'West Africa-China',
                'ballast_distance': 5800,
                'laden_distance': 5800,
                'intake': 165000,
                'load_rate': 85000,
                'discharge_rate': 29000,
                'turntime_hours': 32,
                'port_exp_load_port': 155000,
                'port_exp_discharge_port': 135000,
                'freight_commission_pct': 5.25,
                'sea_margin_pct': 7,
                'ballast_speed': 13,
                'laden_speed': 11.8,
                'ballast_consumption': 43,
                'laden_consumption': 42.5,
                'port_consumption': 7.5,
            },
        ]

        for route_data in routes:
            route_name = route_data['route']
            obj, created = RouteParameters.objects.get_or_create(
                route=route_name,
                defaults=route_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created route: {route_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Route already exists: {route_name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Sample routes created successfully!')
        )
