from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create a default admin user if it does not exist'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            self.stdout.write(
                self.style.SUCCESS(
                    'Admin user already exists'
                )
            )
        else:
            User.objects.create_superuser(
                username='admin',
                email='admin@freightdash.local',
                password='admin'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    'Successfully created admin user with username: admin, password: admin'
                )
            )
