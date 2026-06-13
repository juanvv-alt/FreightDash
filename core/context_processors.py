from django.db import DatabaseError
from django.db.utils import OperationalError, ProgrammingError

from .models import MenuItem


DEFAULT_MENU_ITEMS = [
    {
        'title': 'TCE Calculator',
        'url': '/',
        'icon': 'fas fa-calculator',
        'children': [],
    },
    {
        'title': 'FFA Valuation',
        'url': '/ffa-valuation/',
        'icon': 'fas fa-chart-line',
        'children': [],
    },
    {
        'title': 'Supply Forecast',
        'url': '/supply-forecast/',
        'icon': 'fas fa-satellite-dish',
        'children': [],
    },
    {
        'title': 'Admin Panel',
        'url': '/admin/',
        'icon': 'fas fa-cog',
        'children': [],
    },
    {
        'title': 'Indices',
        'url': '/indices/',
        'icon': 'fas fa-circle-dot',
        'children': [
            {'title': 'Capesize', 'url': '/indices/capesize/', 'icon': 'far fa-circle'},
            {'title': 'Panamax', 'url': '/indices/panamax/', 'icon': 'far fa-circle'},
            {'title': 'Supramax', 'url': '/indices/supramax/', 'icon': 'far fa-circle'},
            {'title': 'Handysize', 'url': '/indices/handysize/', 'icon': 'far fa-circle'},
            {'title': 'Custom', 'url': '/indices/custom/', 'icon': 'far fa-circle'},
        ],
    },
]


def menu_items(request):
    """Context processor to provide menu items to all templates."""
    try:
        raw_items = list(
            MenuItem.objects.filter(is_active=True)
            .exclude(title='')
            .exclude(url='')
            .select_related('parent')
            .order_by('order', 'title')
        )
    except (DatabaseError, ProgrammingError, OperationalError):
        raw_items = []

    items = []
    if raw_items:
        nodes = {}
        for item in raw_items:
            nodes[item.id] = {
                'title': item.title,
                'url': item.url,
                'icon': item.icon,
                'order': item.order,
                'children': [],
                'id': item.id,
            }

        for item in raw_items:
            if str(item.url).startswith('/admin/database-tools/'):
                continue
            node = nodes[item.id]
            if item.parent_id and item.parent_id in nodes:
                nodes[item.parent_id]['children'].append(node)
            else:
                items.append(node)

        items.sort(key=lambda x: (x['order'], x['title']))
        for node in items:
            node['children'].sort(key=lambda x: (x['order'], x['title']))

    if not items:
        items = DEFAULT_MENU_ITEMS

    return {'menu_items': items}