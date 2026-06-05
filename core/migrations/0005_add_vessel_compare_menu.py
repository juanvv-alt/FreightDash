from django.db import migrations


def add_vessel_compare_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.get_or_create(
        url='/voyage/vessel-compare/',
        defaults={
            'title': 'Vessel Compare',
            'icon': 'fas fa-ship',
            'order': 15,
            'is_active': True,
        },
    )


def remove_vessel_compare_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/voyage/vessel-compare/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_menuitem_options'),
    ]

    operations = [
        migrations.RunPython(add_vessel_compare_menu, remove_vessel_compare_menu),
    ]
