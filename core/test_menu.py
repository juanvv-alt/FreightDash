"""Tests for the function-grouped navigation menu.

Guards the Phase 2 reorg: every leaf URL in the canonical structure must resolve
to a real view (no dead nav links), and `seed_menu` must materialise the same
structure into MenuItem rows that the context processor reads back unchanged.
"""
from django.core.management import call_command
from django.test import TestCase
from django.urls import Resolver404, resolve

from core.context_processors import DEFAULT_MENU_ITEMS, menu_items
from core.models import MenuItem


def _leaf_urls(groups):
    urls = []
    for group in groups:
        children = group.get("children", [])
        if children:
            urls.extend(child["url"] for child in children)
        elif not group["url"].startswith("#"):
            urls.append(group["url"])
    return urls


class MenuStructureTests(TestCase):
    def test_every_leaf_url_resolves(self):
        for url in _leaf_urls(DEFAULT_MENU_ITEMS):
            with self.subTest(url=url):
                try:
                    resolve(url)
                except Resolver404:
                    self.fail(f"Menu URL does not resolve: {url}")

    def test_group_headers_use_anchor_urls(self):
        # Header-only groups must keep a non-empty url so the context processor's
        # exclude(url='') filter never drops them.
        for group in DEFAULT_MENU_ITEMS:
            if group.get("children"):
                self.assertTrue(group["url"], "group header needs a non-empty url")

    def test_expected_top_level_groups(self):
        titles = [g["title"] for g in DEFAULT_MENU_ITEMS]
        self.assertEqual(
            titles, ["Calculators", "Market Data", "Supply & Tracking", "Admin"]
        )


class SeedMenuCommandTests(TestCase):
    def test_seed_menu_is_idempotent_and_matches_fallback(self):
        call_command("seed_menu")
        first = MenuItem.objects.count()
        call_command("seed_menu")
        self.assertEqual(MenuItem.objects.count(), first)

        rendered = menu_items(None)["menu_items"]
        self.assertEqual(
            [g["title"] for g in rendered],
            [g["title"] for g in DEFAULT_MENU_ITEMS],
        )
        # Children round-trip too.
        calculators = next(g for g in rendered if g["title"] == "Calculators")
        self.assertEqual(
            [c["title"] for c in calculators["children"]],
            ["TCE Calculator", "Vessel Compare", "Freight Matrix", "FFA Valuation"],
        )
