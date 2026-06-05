from django.db import migrations


def fix_vessel_compare_url(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/voyage/vessel-compare/').update(url='/vessel-compare/')
    # Also ensure it exists with the correct URL in case 0005 didn't run
    MenuItem.objects.get_or_create(
        url='/vessel-compare/',
        defaults={
            'title': 'Vessel Compare',
            'icon': 'fas fa-ship',
            'order': 15,
            'is_active': True,
        },
    )


def reverse_fix(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/vessel-compare/').update(url='/voyage/vessel-compare/')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_vessel_compare_menu'),
    ]

    operations = [
        migrations.RunPython(fix_vessel_compare_url, reverse_fix),
    ]
