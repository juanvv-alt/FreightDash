from django.db import migrations


def align_menu_structure(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    vessel_parent = MenuItem.objects.filter(title__iexact='Vessel', parent__isnull=True).first()
    if not vessel_parent:
        vessel_parent = MenuItem.objects.create(
            title='Vessel',
            url='/#',
            icon='fas fa-circle-dot',
            order=40,
            is_active=True,
            parent=None,
        )

    voyage_item = MenuItem.objects.filter(title__iexact='Voyage').first()
    if not voyage_item:
        voyage_item = MenuItem.objects.create(
            title='Voyage',
            url='/freight-matrix/',
            icon='far fa-circle',
            order=1,
            is_active=True,
            parent=vessel_parent,
        )
    else:
        voyage_item.url = '/freight-matrix/'
        voyage_item.parent = vessel_parent
        voyage_item.is_active = True
        voyage_item.save(update_fields=['url', 'parent', 'is_active', 'updated_at'])

    spot_item = MenuItem.objects.filter(title__iexact='Spot Rate').first()
    if not spot_item:
        MenuItem.objects.create(
            title='Spot Rate',
            url='/#',
            icon='far fa-circle',
            order=2,
            is_active=True,
            parent=vessel_parent,
        )
    elif spot_item.parent_id != vessel_parent.id:
        spot_item.parent = vessel_parent
        spot_item.save(update_fields=['parent', 'updated_at'])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_menuitem_options'),
        ('voyage', '0007_seed_freight_matrix_dummy_data'),
    ]

    operations = [
        migrations.RunPython(align_menu_structure, noop_reverse),
    ]
