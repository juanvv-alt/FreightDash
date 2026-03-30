from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_menuitem_parent'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='menuitem',
            options={
                'ordering': ['order', 'title'],
                'verbose_name': 'Menu Item',
                'verbose_name_plural': 'Menu Builder',
            },
        ),
    ]
