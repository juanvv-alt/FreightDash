from django.db import DatabaseError
from django.db.utils import OperationalError, ProgrammingError

from .models import MenuItem


DEFAULT_MENU_ITEMS = [
    {
        'title': 'TCE Calculator',
        'url': '/',
        'icon': 'fas fa-calculator',
    },
    {
        'title': 'Admin Panel',
        'url': '/admin/',
        'icon': 'fas fa-cog',
    },
]


def menu_items(request):
    """Context processor to provide menu items to all templates."""
    try:
        items = list(
            MenuItem.objects.filter(is_active=True)
            .exclude(title='')
            .exclude(url='')
            .order_by('order', 'title')
        )
    except (DatabaseError, ProgrammingError, OperationalError):
        items = []

    if not items:
        items = DEFAULT_MENU_ITEMS

    return {'menu_items': items}