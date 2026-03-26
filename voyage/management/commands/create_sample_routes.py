from django.core.management.base import BaseCommand
from voyage.models import RouteParameters


class Command(BaseCommand):
    help = 'Create sample shipping routes for TCE calculator'

    def handle(self, *args, **options):
        routes = [
            {
                'route': 'c5 route',
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
