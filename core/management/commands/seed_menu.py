"""Rebuild the sidebar navigation from the canonical structure.

This is the single source of truth for materialising editable ``MenuItem`` rows.
It wipes the existing menu and recreates it from ``DEFAULT_MENU_ITEMS`` in
``core.context_processors``, so the database menu and the fallback used when the
table is empty can never drift. Idempotent — running it twice yields the same
rows.

    python manage.py seed_menu

Supersedes the older per-group ``seed_ais_menu`` repair command.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.context_processors import DEFAULT_MENU_ITEMS
from core.models import MenuItem


class Command(BaseCommand):
    help = "Reset and reseed the main sidebar navigation from DEFAULT_MENU_ITEMS."

    @transaction.atomic
    def handle(self, *args, **options):
        deleted, _ = MenuItem.objects.all().delete()
        self.stdout.write(f"  Cleared {deleted} existing menu row(s).")

        created = 0
        for top_order, group in enumerate(DEFAULT_MENU_ITEMS):
            parent = MenuItem.objects.create(
                title=group["title"],
                url=group["url"],
                icon=group["icon"],
                order=top_order,
                is_active=True,
                parent=None,
            )
            created += 1
            for child_order, child in enumerate(group.get("children", [])):
                MenuItem.objects.create(
                    title=child["title"],
                    url=child["url"],
                    icon=child["icon"],
                    order=child_order,
                    is_active=True,
                    parent=parent,
                )
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  Seeded {created} menu row(s). Reload any FreightDash page to see the new nav."
            )
        )
