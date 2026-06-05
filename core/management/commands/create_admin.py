from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create the default superuser (Juan/enter) if it does not already exist'

    def handle(self, *args, **options):
        # Remove legacy admin/admin account if it was created by an older version
        if User.objects.filter(username='admin').exists():
            User.objects.filter(username='admin').delete()
            self.stdout.write(self.style.WARNING('Removed legacy admin/admin account'))

        if User.objects.filter(username='Juan').exists():
            self.stdout.write(self.style.SUCCESS('Default user Juan already exists'))
        else:
            User.objects.create_superuser(
                username='Juan',
                email='juan@freightdash.local',
                password='enter',
            )
            self.stdout.write(self.style.SUCCESS('Created superuser Juan (password: enter)'))
