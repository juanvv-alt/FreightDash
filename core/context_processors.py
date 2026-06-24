from django.db import DatabaseError
from django.db.utils import OperationalError, ProgrammingError

from .models import MenuItem


# Canonical navigation structure, grouped by function. This is both the
# fallback used when the MenuItem table is empty AND the source the
# `seed_menu` management command materialises into editable MenuItem rows,
# so the two can never drift. Group headers use url '#': the sidebar renders
# any item with children as a collapsing header button rather than a link.
DEFAULT_MENU_ITEMS = [
    {
        'title': 'Calculators',
        'url': '#calculators',
        'icon': 'fas fa-calculator',
        'children': [
            {'title': 'TCE Calculator', 'url': '/', 'icon': 'fas fa-calculator'},
            {'title': 'Vessel Compare', 'url': '/vessel-compare/', 'icon': 'fas fa-scale-balanced'},
            {'title': 'Freight Matrix', 'url': '/freight-matrix/', 'icon': 'fas fa-table-cells'},
            {'title': 'FFA Valuation', 'url': '/ffa-valuation/', 'icon': 'fas fa-chart-line'},
        ],
    },
    {
        'title': 'Market Data',
        'url': '#market-data',
        'icon': 'fas fa-list-ol',
        'children': [
            {'title': 'Capesize', 'url': '/indices/capesize/', 'icon': 'far fa-circle'},
            {'title': 'Panamax', 'url': '/indices/panamax/', 'icon': 'far fa-circle'},
            {'title': 'Supramax', 'url': '/indices/supramax/', 'icon': 'far fa-circle'},
            {'title': 'Handysize', 'url': '/indices/handysize/', 'icon': 'far fa-circle'},
            {'title': 'Custom', 'url': '/indices/custom/', 'icon': 'far fa-circle'},
        ],
    },
    {
        'title': 'Supply & Tracking',
        'url': '#supply-tracking',
        'icon': 'fas fa-satellite-dish',
        'children': [
            {'title': 'Supply Forecast', 'url': '/supply-forecast/', 'icon': 'fas fa-satellite-dish'},
            {'title': 'OB Forecast', 'url': '/ob-forecast/', 'icon': 'fas fa-water'},
            {'title': 'Vessel Fleet', 'url': '/supply-forecast/fleet/', 'icon': 'fas fa-ship'},
            {'title': 'AIS Status', 'url': '/supply-forecast/status/', 'icon': 'fas fa-tower-broadcast'},
        ],
    },
    {
        'title': 'Admin',
        'url': '/admin/',
        'icon': 'fas fa-cog',
        'children': [],
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