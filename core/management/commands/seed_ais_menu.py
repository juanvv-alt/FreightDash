"""One-shot command to ensure the AIS Forecast menu group is in the sidebar.

Run this if migration 0011 already applied but items aren't showing in the nav,
or if items were manually added in a broken state via the Django admin.

    python manage.py seed_ais_menu
"""

from django.core.management.base import BaseCommand

from core.models import MenuItem


class Command(BaseCommand):
    help = "Seed / repair the AIS Forecast navigation group in the main sidebar."

    def handle(self, *args, **options):
        # Deactivate old standalone Supply Forecast item.
        deactivated = MenuItem.objects.filter(
            url='/supply-forecast/', parent__isnull=True
        ).update(is_active=False)
        if deactivated:
            self.stdout.write(f"  Deactivated {deactivated} old standalone Supply Forecast item(s).")

        # Create / fix the parent group.
        parent, created = MenuItem.objects.get_or_create(
            url='#ais-forecast',
            defaults={
                'title': 'AIS Forecast',
                'icon': 'fas fa-satellite-dish',
                'order': 15,
                'is_active': True,
                'parent': None,
            },
        )
        if not created and (not parent.is_active or parent.title != 'AIS Forecast'):
            parent.is_active = True
            parent.title = 'AIS Forecast'
            parent.save()
        self.stdout.write(
            self.style.SUCCESS(f"  {'Created' if created else 'Found'} AIS Forecast parent (pk={parent.pk}).")
        )

        children = [
            {'title': 'Supply Signals',       'url': '/supply-forecast/',        'icon': 'fas fa-chart-line', 'order': 1},
            {'title': 'Vessel Fleet',          'url': '/supply-forecast/fleet/',  'icon': 'fas fa-ship',       'order': 2},
            {'title': 'AIS Status & Controls', 'url': '/supply-forecast/status/', 'icon': 'fas fa-tools',      'order': 3},
        ]
        for child in children:
            obj, created = MenuItem.objects.get_or_create(
                url=child['url'],
                defaults={
                    'title': child['title'],
                    'icon': child['icon'],
                    'order': child['order'],
                    'is_active': True,
                    'parent': parent,
                },
            )
            if not created:
                obj.parent = parent
                obj.is_active = True
                obj.title = child['title']
                obj.icon = child['icon']
                obj.order = child['order']
                obj.save()
            verb = 'Created' if created else 'Updated'
            self.stdout.write(f"  {verb}: {child['title']} → {child['url']}")

        self.stdout.write(self.style.SUCCESS("\nDone — reload any FreightDash page to see the AIS Forecast group in the sidebar."))
