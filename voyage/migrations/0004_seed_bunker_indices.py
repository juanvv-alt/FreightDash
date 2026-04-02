from django.db import migrations

BUNKER_INDICES = [
    'Singapore IFO 380',
    'Singapore MGO',
    'Singapore VLSFO',
    'Hong Kong IFO 380',
    'Hong Kong MGO',
    'Hong Kong VLSFO',
    'Rotterdam IFO 380',
    'Rotterdam MGO',
    'Rotterdam VLSFO',
    'Brent',
    'WTI',
]


def seed_bunker_indices(apps, schema_editor):
    AvailableIndex = apps.get_model('voyage', 'AvailableIndex')
    for order, name in enumerate(BUNKER_INDICES, start=1):
        AvailableIndex.objects.get_or_create(
            name=name,
            defaults={
                'vessel_size': 'bunker',
                'order': order,
                'is_active': True,
            },
        )


def seed_bunker_menu_item(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    parent = MenuItem.objects.filter(title__iexact='indices', parent__isnull=True).first()
    if parent:
        MenuItem.objects.get_or_create(
            title='Bunker',
            defaults={
                'url': '/indices/bunker/',
                'icon': 'fas fa-oil-can',
                'order': 6,
                'is_active': True,
                'parent': parent,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('voyage', '0003_availableindex_dailyindexvalue'),
        ('core', '0004_alter_menuitem_options'),
    ]

    operations = [
        migrations.RunPython(seed_bunker_indices, migrations.RunPython.noop),
        migrations.RunPython(seed_bunker_menu_item, migrations.RunPython.noop),
    ]
