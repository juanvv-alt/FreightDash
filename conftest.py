import os

import django
from django.conf import settings


def pytest_configure(config):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DATABASE_ENGINE", "django.db.backends.sqlite3")
