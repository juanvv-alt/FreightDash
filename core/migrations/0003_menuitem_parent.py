from django.db import migrations, models
import django.db.models.deletion


def seed_indices_menu(apps, schema_editor):
    MenuItem = apps.get_model('core', 'MenuItem')

    indices_parent, _ = MenuItem.objects.get_or_create(
        url='/indices/',
        defaults={
            'title': 'Indices',
            'icon': 'fas fa-circle-dot',
            'order': 30,
            'is_active': True,
            'parent': None,
        },
    )

    child_defs = [
        ('Capesize', '/indices/capesize/'),
        ('Panamax', '/indices/panamax/'),
        ('Supramax', '/indices/supramax/'),
        ('Handysize', '/indices/handysize/'),
        ('Custom', '/indices/custom/'),
    ]

    for idx, (title, url) in enumerate(child_defs, start=1):
        MenuItem.objects.get_or_create(
            url=url,
            defaults={
                'title': title,
                'icon': 'far fa-circle',
                'order': idx,
                'is_active': True,
                'parent': indices_parent,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_seed_default_menu_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='menuitem',
            name='parent',
            field=models.ForeignKey(blank=True, help_text='Optional parent item to create nested menu groups.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.menuitem'),
        ),
        migrations.RunPython(seed_indices_menu, migrations.RunPython.noop),
    ]
