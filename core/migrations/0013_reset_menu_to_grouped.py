"""Reset the menu to the new function-grouped structure.

Migrations 0002–0012 each appended/rearranged menu rows imperatively, so the
table accumulated a tangled history (standalone items, an AIS group, an OB group,
etc.). This clears those rows; the app then renders the canonical grouped nav
from DEFAULT_MENU_ITEMS (the fallback used when the table is empty). Run
``manage.py seed_menu`` afterwards to materialise editable rows for the Menu
Builder. Going forward, ``seed_menu`` is the single seeding path — not migrations.
"""

from django.db import migrations


def clear_menu(apps, schema_editor):
    MenuItem = apps.get_model("core", "MenuItem")
    MenuItem.objects.all().delete()


def noop_reverse(apps, schema_editor):
    # Forward-only data reset; nothing meaningful to restore.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_ob_forecast_menu"),
    ]

    operations = [
        migrations.RunPython(clear_menu, noop_reverse),
    ]
