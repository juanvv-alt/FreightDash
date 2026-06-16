from django.db import migrations


def add_ais_forecast_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    # Deactivate the old standalone Supply Forecast top-level item.
    MenuItem.objects.filter(url='/supply-forecast/').update(is_active=False)

    # Create the AIS Forecast parent group.
    parent, _ = MenuItem.objects.get_or_create(
        url='#ais-forecast',
        defaults={
            'title': 'AIS Forecast',
            'icon': 'fas fa-satellite-dish',
            'order': 15,
            'is_active': True,
            'parent_id': None,
        },
    )
    if not parent.is_active:
        parent.is_active = True
        parent.title = 'AIS Forecast'
        parent.save()

    children = [
        {'title': 'Supply Signals',       'url': '/supply-forecast/',        'icon': 'fas fa-chart-line', 'order': 1},
        {'title': 'Vessel Fleet',          'url': '/supply-forecast/fleet/',  'icon': 'fas fa-ship',       'order': 2},
        {'title': 'AIS Status & Controls', 'url': '/supply-forecast/status/', 'icon': 'fas fa-tools',      'order': 3},
    ]
    for child in children:
        obj, created = MenuItem.objects.get_or_create(
            url=child['url'],
            defaults={
                'title': child['title'],
                'icon': child['icon'],
                'order': child['order'],
                'is_active': True,
                'parent_id': parent.pk,
            },
        )
        if not created:
            # Row existed (e.g. old supply-forecast entry) — reparent and reactivate.
            obj.parent_id = parent.pk
            obj.is_active = True
            obj.title = child['title']
            obj.icon = child['icon']
            obj.order = child['order']
            obj.save()


def remove_ais_forecast_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url__in=[
        '#ais-forecast',
        '/supply-forecast/fleet/',
        '/supply-forecast/status/',
    ]).delete()
    # Restore the standalone Supply Forecast item.
    MenuItem.objects.filter(url='/supply-forecast/').update(
        is_active=True,
        parent_id=None,
        title='Supply Forecast',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_ffa_valuation_menu'),
    ]

    operations = [
        migrations.RunPython(add_ais_forecast_menu, remove_ais_forecast_menu),
    ]
