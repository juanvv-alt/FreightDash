"""Composable registration of extra Django admin URLs.

Several apps add bespoke admin pages (index uploads, indices config, menu
builder, database tools). Each used to monkey-patch ``admin.site.get_urls``
independently, which duplicated the fragile global-state dance and made the
result depend on app import order.

``register_admin_urls`` centralises that into one reviewed helper. Each caller
passes a zero-arg factory returning its ``path(...)`` list; the helper captures
the *current* ``get_urls`` (which may already be wrapped by an earlier caller)
and prepends the new URLs, so calls compose correctly in any order.
"""

from django.contrib import admin


def register_admin_urls(url_factory):
    """Prepend the URLs from ``url_factory()`` to ``admin.site.get_urls``.

    ``url_factory`` is called lazily at URL-resolution time, so views it
    references may be imported inside the factory to avoid circular imports.
    """
    previous_get_urls = admin.site.get_urls

    def get_urls():
        return list(url_factory()) + previous_get_urls()

    admin.site.get_urls = get_urls
