from django.db import migrations


def add_menu_item(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')
    MenuItem.objects.get_or_create(
        url='/upload-excel-indices/',
        defaults={
            'title': 'Upload Indices',
            'icon': 'fas fa-file-excel',
            'order': 40,
            'is_active': True,
        },
    )


def remove_menu_item(apps, schema_editor):
    apps.get_model('core', 'MenuItem').objects.filter(url='/upload-excel-indices/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_fix_vessel_compare_menu_url'),
    ]

    operations = [
        migrations.RunPython(add_menu_item, remove_menu_item),
    ]
