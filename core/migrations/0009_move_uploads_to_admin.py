"""
Remove the front-end 'Admin' nav group (Upload Indices + Upload Batch Data)
and update those items to point at the Django admin URLs instead.
"""
from django.db import migrations


def move_to_admin(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    # Delete the old 'Admin' parent group and its children from the main nav.
    # The uploads are now accessible from the Django admin panel directly.
    MenuItem.objects.filter(url='/upload-excel-indices/').delete()
    MenuItem.objects.filter(url='/upload-batch-indices/').delete()
    MenuItem.objects.filter(title='Admin', url='#').delete()


def reverse_move(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    admin_group, _ = MenuItem.objects.get_or_create(
        title='Admin',
        defaults={'url': '#', 'icon': 'fas fa-cog', 'order': 90, 'is_active': True},
    )
    MenuItem.objects.get_or_create(
        url='/upload-excel-indices/',
        defaults={
            'title': 'Upload Indices',
            'icon': 'fas fa-file-excel',
            'order': 10,
            'is_active': True,
            'parent': admin_group,
        },
    )
    MenuItem.objects.get_or_create(
        url='/upload-batch-indices/',
        defaults={
            'title': 'Upload Batch Data',
            'icon': 'fas fa-layer-group',
            'order': 20,
            'is_active': True,
            'parent': admin_group,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_admin_menu_group'),
    ]

    operations = [
        migrations.RunPython(move_to_admin, reverse_move),
    ]
