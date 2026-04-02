from django.db import migrations


def seed_freight_matrix_data(apps, schema_editor):
    AvailableIndex = apps.get_model('voyage', 'AvailableIndex')
    VesselProfile = apps.get_model('voyage', 'VesselProfile')
    VesselSpeedProfile = apps.get_model('voyage', 'VesselSpeedProfile')
    VesselFuelProfile = apps.get_model('voyage', 'VesselFuelProfile')
    VesselFuelConsumption = apps.get_model('voyage', 'VesselFuelConsumption')
    FreightVoyage = apps.get_model('voyage', 'FreightVoyage')
    VoyageFuelSplit = apps.get_model('voyage', 'VoyageFuelSplit')
    MenuItem = apps.get_model('core', 'MenuItem')

    hire_index, _ = AvailableIndex.objects.get_or_create(
        name='BPI 82TC',
        defaults={'vessel_size': 'panamax', 'order': 10, 'is_active': True},
    )
    vlsfo_index, _ = AvailableIndex.objects.get_or_create(
        name='Singapore VLSFO',
        defaults={'vessel_size': 'bunker', 'order': 3, 'is_active': True},
    )
    mgo_index, _ = AvailableIndex.objects.get_or_create(
        name='Singapore MGO',
        defaults={'vessel_size': 'bunker', 'order': 2, 'is_active': True},
    )

    vessel, _ = VesselProfile.objects.get_or_create(
        name='Standard PMX',
        defaults={
            'vessel_size': 'panamax',
            'dwt': 82000,
            'draft': 14.3,
            'npc': 0,
            'grain_capacity': 98000,
            'default_port_consumption': 3,
            'is_active': True,
        },
    )

    speed_profile, _ = VesselSpeedProfile.objects.get_or_create(
        vessel=vessel,
        name='CP',
        defaults={
            'ballast_speed': 13.5,
            'laden_speed': 12.5,
            'is_default': True,
        },
    )

    fuel_profile, _ = VesselFuelProfile.objects.get_or_create(
        vessel=vessel,
        name='CP CONS',
        defaults={'is_default': True},
    )

    VesselFuelConsumption.objects.get_or_create(
        fuel_profile=fuel_profile,
        fuel_type='VLSFO',
        defaults={'sea_consumption': 24, 'port_consumption': 2.5},
    )
    VesselFuelConsumption.objects.get_or_create(
        fuel_profile=fuel_profile,
        fuel_type='MGO',
        defaults={'sea_consumption': 0.1, 'port_consumption': 0.1},
    )

    voyage, _ = FreightVoyage.objects.get_or_create(
        name='Coal Newcastle-Qingdao PMX',
        defaults={
            'commodity': 'Coal',
            'load_ports': ['Newcastle'],
            'discharge_ports': ['Qingdao'],
            'ballast_port': 'Singapore',
            'load_rate': 20000,
            'discharge_rate': 15000,
            'turntime_load_hours': 12,
            'turntime_discharge_hours': 12,
            'port_exp_load_port': 220000,
            'port_exp_discharge_port': 240000,
            'misc_expenses': 30000,
            'vessel': vessel,
            'speed_profile': speed_profile,
            'fuel_profile': fuel_profile,
            'intake_mode': 'manual',
            'intake_manual': 75000,
            'apply_same_sea_margin': True,
            'sea_margin_ballast_pct': 7,
            'sea_margin_laden_pct': 7,
            'ballast_distance': 5200,
            'laden_distance': 4500,
            'address_commission_pct': 1.25,
            'brokerage_commission_pct': 1.25,
            'daily_hire_index': hire_index,
            'is_active': True,
        },
    )

    VoyageFuelSplit.objects.get_or_create(
        voyage=voyage,
        fuel_index=vlsfo_index,
        defaults={'weight_pct': 95},
    )
    VoyageFuelSplit.objects.get_or_create(
        voyage=voyage,
        fuel_index=mgo_index,
        defaults={'weight_pct': 5},
    )

    vessel_parent = MenuItem.objects.filter(title__iexact='vessel', parent__isnull=True).first()
    voyage_menu = MenuItem.objects.filter(title__iexact='voyage').first()

    if voyage_menu:
        voyage_menu.url = '/freight-matrix/'
        voyage_menu.is_active = True
        if vessel_parent and voyage_menu.parent_id is None:
            voyage_menu.parent = vessel_parent
        voyage_menu.save(update_fields=['url', 'is_active', 'parent', 'updated_at'])
    else:
        MenuItem.objects.get_or_create(
            url='/freight-matrix/',
            defaults={
                'title': 'Voyage',
                'icon': 'far fa-circle',
                'order': 1,
                'is_active': True,
                'parent': vessel_parent,
            },
        )


def unseed_freight_matrix_data(apps, schema_editor):
    FreightVoyage = apps.get_model('voyage', 'FreightVoyage')
    VesselProfile = apps.get_model('voyage', 'VesselProfile')

    FreightVoyage.objects.filter(name='Coal Newcastle-Qingdao PMX').delete()
    VesselProfile.objects.filter(name='Standard PMX').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_menuitem_options'),
        ('voyage', '0006_vesselprofile_vesselspeedprofile_vesselfuelprofile_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_freight_matrix_data, unseed_freight_matrix_data),
    ]
