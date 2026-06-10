from django.db import migrations


def add_ffa_valuation_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.get_or_create(
        url='/ffa-valuation/',
        defaults={
            'title': 'FFA Valuation',
            'icon': 'fas fa-chart-line',
            'order': 20,
            'is_active': True,
        },
    )


def remove_ffa_valuation_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/ffa-valuation/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_move_uploads_to_admin'),
    ]

    operations = [
        migrations.RunPython(add_ffa_valuation_menu, remove_ffa_valuation_menu),
    ]
