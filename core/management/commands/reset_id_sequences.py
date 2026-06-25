"""Realign PostgreSQL auto-increment ID sequences with existing data.

After a JSON restore (admin → Database Backup & Restore), rows are inserted with
their original primary keys, which on PostgreSQL leaves the table sequences
pointing below the max existing id. The next UI insert then collides with an
existing id and raises a duplicate-key error (seen as a 500 when, e.g., adding a
vessel on Vessel Compare). Run this once to repair an already-restored database:

    python manage.py reset_id_sequences            # core + voyage (the backed-up apps)
    python manage.py reset_id_sequences supply     # specific app(s)

No-op on SQLite, which has no sequences.
"""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection

from core.admin import BACKUP_APP_LABELS


class Command(BaseCommand):
    help = "Reset auto-increment PK sequences to match existing rows (Postgres)."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_labels",
            nargs="*",
            help="Apps to repair (default: the backed-up apps, %s)."
            % ", ".join(BACKUP_APP_LABELS),
        )

    def handle(self, *args, **options):
        app_labels = options["app_labels"] or list(BACKUP_APP_LABELS)

        models = []
        for app_label in app_labels:
            try:
                models.extend(apps.get_app_config(app_label).get_models())
            except LookupError as exc:
                raise CommandError(str(exc))

        reset_sql = connection.ops.sequence_reset_sql(no_style(), models)
        if not reset_sql:
            self.stdout.write(
                "  No sequences to reset on this database backend (e.g. SQLite). Nothing to do."
            )
            return

        with connection.cursor() as cursor:
            for sql in reset_sql:
                cursor.execute(sql)

        self.stdout.write(
            self.style.SUCCESS(
                f"  Reset {len(reset_sql)} sequence(s) across: {', '.join(app_labels)}."
            )
        )
