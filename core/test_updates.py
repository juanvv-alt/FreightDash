"""Tests for the Software Updates version check and admin page.

Network is always mocked — these never hit GitHub.
"""
import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core import updates

LATEST_SHA = "b" * 40
RUNNING_SHA = "a" * 40

# One payload satisfies both the commits endpoint (sha/commit/html_url) and the
# compare endpoint (ahead_by), so a single fake response covers both calls.
LATEST_PAYLOAD = {
    "sha": LATEST_SHA,
    "commit": {
        "message": "Add a thing\n\nlonger body ignored",
        "committer": {"date": "2026-06-25T00:00:00Z"},
    },
    "html_url": "https://github.com/x/y/commit/bbb",
    "ahead_by": 3,
}


def _fake_response(payload, status=200):
    resp = MagicMock()
    resp.json.return_value = payload
    if status >= 400:
        from requests import HTTPError

        resp.raise_for_status.side_effect = HTTPError("boom")
    else:
        resp.raise_for_status.return_value = None
    return resp


@override_settings(GITHUB_REPO="x/y", GITHUB_TOKEN="")
class UpdateStatusTests(TestCase):
    def setUp(self):
        cache.clear()  # get_latest_version caches; isolate each test

    @override_settings(APP_GIT_SHA=LATEST_SHA, APP_BUILD_TIME="2026-06-25")
    @patch("core.updates.requests.get")
    def test_up_to_date(self, mock_get):
        mock_get.return_value = _fake_response(LATEST_PAYLOAD)
        status = updates.get_update_status()
        self.assertEqual(status["state"], "up_to_date")
        self.assertEqual(status["behind_count"], 0)
        self.assertEqual(status["running"]["short_sha"], LATEST_SHA[:7])

    @override_settings(APP_GIT_SHA=RUNNING_SHA)
    @patch("core.updates.requests.get")
    def test_update_available(self, mock_get):
        mock_get.return_value = _fake_response(LATEST_PAYLOAD)
        status = updates.get_update_status()
        self.assertEqual(status["state"], "update_available")
        self.assertEqual(status["behind_count"], 3)
        # Only the first line of the commit message is kept.
        self.assertEqual(status["latest"]["message"], "Add a thing")

    @override_settings(APP_GIT_SHA="")
    @patch("core.updates.requests.get")
    def test_unknown_when_running_not_stamped(self, mock_get):
        mock_get.return_value = _fake_response(LATEST_PAYLOAD)
        status = updates.get_update_status()
        self.assertEqual(status["state"], "unknown")
        self.assertIsNone(status["running"])
        self.assertIsNotNone(status["latest"])

    @override_settings(APP_GIT_SHA=RUNNING_SHA)
    @patch("core.updates.requests.get")
    def test_error_when_github_unreachable(self, mock_get):
        from requests import ConnectionError as ReqConnError

        mock_get.side_effect = ReqConnError("no network")
        status = updates.get_update_status()
        self.assertEqual(status["state"], "error")
        self.assertIsNone(status["latest"])
        self.assertTrue(status["error"])

    @override_settings(APP_GIT_SHA=RUNNING_SHA)
    @patch("core.updates.requests.get")
    def test_latest_is_cached(self, mock_get):
        mock_get.return_value = _fake_response(LATEST_PAYLOAD)
        updates.get_latest_version()
        updates.get_latest_version()
        # Second call served from cache → only one HTTP GET for the commits call.
        self.assertEqual(mock_get.call_count, 1)


class SoftwareUpdatesViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_superuser(
            "boss", "boss@example.com", "x"
        )

    def _status(self, **overrides):
        base = {
            "state": "unknown",
            "running": None,
            "latest": {
                "short_sha": "bbbbbbb",
                "message": "Add a thing",
                "date": "2026-06-25T00:00:00Z",
                "html_url": "https://github.com/x/y/commit/bbb",
            },
            "behind_count": None,
            "checked_at": datetime.datetime(2026, 6, 25, 12, 0, 0),
            "error": None,
        }
        base.update(overrides)
        return base

    @patch("core.admin.get_update_status")
    def test_renders_for_staff(self, mock_status):
        mock_status.return_value = self._status()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:software-updates"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Software Updates")

    def test_anonymous_redirected(self):
        response = self.client.get(reverse("admin:software-updates"))
        self.assertIn(response.status_code, (301, 302))

    @patch("core.admin.get_update_status")
    def test_recheck_forces_refresh_and_redirects(self, mock_status):
        mock_status.return_value = self._status(state="up_to_date")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:software-updates"), {"action": "recheck"}
        )
        self.assertIn(response.status_code, (301, 302))
        mock_status.assert_called_once_with(force_refresh=True)
