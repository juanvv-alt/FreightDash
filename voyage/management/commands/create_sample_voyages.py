from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from voyage.models import (
    VesselProfile,
    VesselSpeedProfile,
    VesselFuelProfile,
    VesselFuelConsumption,
    FreightVoyage,
    VoyageFuelSplit,
    AvailableIndex,
    DailyIndexValue,
)


class Command(BaseCommand):
    help = 'Create sample freight voyage with all required configurations'

    def handle(self, *args, **options):
        # Create or get vessel
        vessel, vessel_created = VesselProfile.objects.get_or_create(
            name='Sample Capesize',
            defaults={
                'vessel_size': 'capesize',
                'dwt': 180000,
                'draft': 14.5,
                'grain_capacity': 280000,
                'default_port_consumption': 5.0,
                'is_active': True,
            }
        )
        if vessel_created:
            self.stdout.write(f'Created vessel: {vessel.name}')
        else:
            self.stdout.write(f'Vessel already exists: {vessel.name}')

        # Create or get speed profile
        speed_profile, speed_created = VesselSpeedProfile.objects.get_or_create(
            vessel=vessel,
            name='CP',
            defaults={
                'ballast_speed': 13.5,
                'laden_speed': 12.0,
                'is_default': True,
            }
        )
        if speed_created:
            self.stdout.write(f'Created speed profile: {speed_profile.name}')
        else:
            self.stdout.write(f'Speed profile already exists: {speed_profile.name}')

        # Create or get fuel profile
        fuel_profile, fuel_created = VesselFuelProfile.objects.get_or_create(
            vessel=vessel,
            name='CP CONS',
            defaults={
                'is_default': True,
            }
        )
        if fuel_created:
            self.stdout.write(f'Created fuel profile: {fuel_profile.name}')
        else:
            self.stdout.write(f'Fuel profile already exists: {fuel_profile.name}')

        # Create fuel lines if they don't exist
        fuel_types = [
            ('VLSFO', 43.0, 5.0),
            ('MGO', 2.0, 1.0),
        ]
        for fuel_type, sea_cons, port_cons in fuel_types:
            fuel_line, fuel_line_created = VesselFuelConsumption.objects.get_or_create(
                fuel_profile=fuel_profile,
                fuel_type=fuel_type,
                defaults={
                    'sea_consumption': sea_cons,
                    'port_consumption': port_cons,
                }
            )
            if fuel_line_created:
                self.stdout.write(f'Created fuel line: {fuel_line.fuel_type}')

        # Create or get indices for fuel
        fuel_indices = {}
        for index_name in ['Singapore IFO 380', 'Singapore MGO']:
            index, index_created = AvailableIndex.objects.get_or_create(
                name=index_name,
                defaults={
                    'vessel_size': 'bunker',
                    'order': 100,
                    'is_active': True,
                }
            )
            fuel_indices[index_name] = index
            if index_created:
                self.stdout.write(f'Created index: {index.name}')

        # Create sample daily values for fuel indices
        today = timezone.localdate()
        for i in range(30):
            date = today - timedelta(days=i)
            for index_name, base_price in [('Singapore IFO 380', 600), ('Singapore MGO', 700)]:
                index = fuel_indices[index_name]
                price = base_price + (i * 2)  # Slight trend
                DailyIndexValue.objects.get_or_create(
                    index=index,
                    date=date,
                    defaults={'value': price}
                )

        # Create or get hire index (e.g., C2 capesize rate)
        hire_index, hire_created = AvailableIndex.objects.get_or_create(
            name='C2',
            defaults={
                'vessel_size': 'capesize',
                'order': 1,
                'is_active': True,
            }
        )
        if hire_created:
            self.stdout.write(f'Created hire index: {hire_index.name}')

        # Create sample hire values
        for i in range(30):
            date = today - timedelta(days=i)
            tce_value = 25000 + (i * 100)  # Starting at 25k, increasing daily
            DailyIndexValue.objects.get_or_create(
                index=hire_index,
                date=date,
                defaults={'value': tce_value}
            )

        # Create or get freight voyage
        voyage, voyage_created = FreightVoyage.objects.get_or_create(
            name='Sample C5 Voyage',
            defaults={
                'vessel': vessel,
                'speed_profile': speed_profile,
                'fuel_profile': fuel_profile,
                'ballast_distance': 2800,
                'laden_distance': 2800,
                'load_rate': 95000,
                'discharge_rate': 32000,
                'turntime_load_hours': 12,
                'turntime_discharge_hours': 12,
                'port_exp_load_port': 150000,
                'port_exp_discharge_port': 125000,
                'misc_expenses': 0,
                'intake_mode': 'manual',
                'intake_manual': 180000,
                'apply_same_sea_margin': True,
                'sea_margin_ballast_pct': 5,
                'sea_margin_laden_pct': 5,
                'address_commission_pct': 1.25,
                'brokerage_commission_pct': 1.25,
                'daily_hire_index': hire_index,
                'is_active': True,
            }
        )
        if voyage_created:
            self.stdout.write(f'Created voyage: {voyage.name}')
        else:
            self.stdout.write(f'Voyage already exists: {voyage.name}')

        # Create fuel splits for the voyage
        fuel_split_configs = [
            ('Singapore IFO 380', 95.0),
            ('Singapore MGO', 5.0),
        ]
        for index_name, weight in fuel_split_configs:
            split, split_created = VoyageFuelSplit.objects.get_or_create(
                voyage=voyage,
                fuel_index=fuel_indices[index_name],
                defaults={'weight_pct': weight}
            )
            if split_created:
                self.stdout.write(f'Created fuel split: {split.fuel_index.name} ({split.weight_pct}%)')

        self.stdout.write(
            self.style.SUCCESS('Sample voyage and related data created successfully!')
        )
