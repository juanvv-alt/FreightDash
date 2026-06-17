from django.db import migrations


def add_ob_forecast_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.get_or_create(
        url='/ob-forecast/',
        defaults={
            'title': 'OB Forecast',
            'icon': 'fas fa-chart-area',
            'order': 20,
            'is_active': True,
            'parent_id': None,
        },
    )


def remove_ob_forecast_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/ob-forecast/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_ais_forecast_menu'),
    ]

    operations = [
        migrations.RunPython(add_ob_forecast_menu, remove_ob_forecast_menu),
    ]
