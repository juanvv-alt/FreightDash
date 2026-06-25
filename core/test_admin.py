"""Smoke tests for the custom admin tooling in the core app.

These were previously untested. They confirm the monkey-patched admin pages
(now registered via core.admin_urls.register_admin_urls) render for staff and
that the database-backup download produces a JSON fixture.
"""
import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from core.admin import _fast_restore
from voyage.models import ComparisonVessel


class CoreAdminToolsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            "boss", "boss@example.com", "x"
        )
        self.client.force_login(self.admin)

    def test_menu_builder_renders(self):
        response = self.client.get(reverse("admin:menu-builder"))
        self.assertEqual(response.status_code, 200)

    def test_database_tools_renders(self):
        response = self.client.get(reverse("admin:database-tools"))
        self.assertEqual(response.status_code, 200)

    def test_database_backup_download_returns_json(self):
        response = self.client.post(
            reverse("admin:database-tools"), {"action": "download"}
        )
        self.assertEqual(response.status_code, 200)
        # Body must be valid JSON (a dumpdata fixture).
        payload = json.loads(response.content.decode("utf-8"))
        self.assertIsInstance(payload, list)

    def test_tools_require_staff(self):
        self.client.logout()
        response = self.client.get(reverse("admin:database-tools"))
        # Anonymous users are bounced to the admin login, never served the tool.
        self.assertIn(response.status_code, (301, 302))
        self.assertNotIn("download", response.content.decode("utf-8", "ignore").lower())


class RestoreSequenceTests(TestCase):
    """Guards the Postgres-sequence fix for the backup/restore tool.

    SQLite (used here) has no sequences, so it cannot reproduce the duplicate-key
    failure itself; these tests confirm the restore + sequence-reset code path
    runs cleanly and that an insert after a restore still works.
    """

    def _backup_json(self):
        out = StringIO()
        call_command("dumpdata", "core", "voyage", format="json", stdout=out)
        return out.getvalue()

    def test_restore_then_create_succeeds(self):
        ComparisonVessel.objects.create(name="Alpha", order=0)
        ComparisonVessel.objects.create(name="Beta", order=1)
        backup = self._backup_json()
        count_before = ComparisonVessel.objects.count()

        _fast_restore(backup, replace_existing=True)

        # Restore round-tripped every row (delete-all then reload)...
        self.assertEqual(ComparisonVessel.objects.count(), count_before)
        self.assertTrue(ComparisonVessel.objects.filter(name="Alpha").exists())
        # ...and a fresh insert (the action that 500s on a stale Postgres
        # sequence) goes through without a duplicate-key error.
        created = ComparisonVessel.objects.create(name="Gamma", order=99)
        self.assertIsNotNone(created.pk)
        self.assertEqual(ComparisonVessel.objects.count(), count_before + 1)

    def test_reset_id_sequences_command_runs(self):
        out = StringIO()
        call_command("reset_id_sequences", stdout=out)
        # Either it reset sequences (Postgres) or reported a no-op (SQLite);
        # the point is it completes without raising.
        self.assertTrue(out.getvalue().strip())

    def test_reset_id_sequences_rejects_unknown_app(self):
        with self.assertRaises(CommandError):
            call_command("reset_id_sequences", "not_an_app")
