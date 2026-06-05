"""
Create an 'Admin' menu group and nest both upload pages under it.
"""
from django.db import migrations


def add_admin_group(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    # Create the Admin parent group (no URL, just a header)
    admin_group, _ = MenuItem.objects.get_or_create(
        title='Admin',
        defaults={
            'url': '#',
            'icon': 'fas fa-cog',
            'order': 90,
            'is_active': True,
            'parent': None,
        },
    )

    # Move existing Upload Indices item under Admin
    MenuItem.objects.filter(url='/upload-excel-indices/').update(
        parent=admin_group,
        order=10,
    )

    # Add Upload Batch Data under Admin
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


def reverse_admin_group(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.filter(url='/upload-batch-indices/').delete()
    MenuItem.objects.filter(url='/upload-excel-indices/').update(parent=None, order=40)
    MenuItem.objects.filter(title='Admin', url='#').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_upload_excel_menu'),
    ]

    operations = [
        migrations.RunPython(add_admin_group, reverse_admin_group),
    ]
