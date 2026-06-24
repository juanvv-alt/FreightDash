"""Smoke tests for the custom admin tooling in the core app.

These were previously untested. They confirm the monkey-patched admin pages
(now registered via core.admin_urls.register_admin_urls) render for staff and
that the database-backup download produces a JSON fixture.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
