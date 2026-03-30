from django.db import migrations


def seed_default_menu_items(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    MenuItem.objects.get_or_create(
        url='/',
        defaults={
            'title': 'TCE Calculator',
            'icon': 'fas fa-calculator',
            'order': 10,
            'is_active': True,
        },
    )

    MenuItem.objects.get_or_create(
        url='/admin/',
        defaults={
            'title': 'Admin Panel',
            'icon': 'fas fa-cog',
            'order': 20,
            'is_active': True,
        },
    )


def unseed_default_menu_items(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url__in=['/', '/admin/']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_menu_items, unseed_default_menu_items),
    ]
