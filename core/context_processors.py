from .models import MenuItem


def menu_items(request):
    """Context processor to provide menu items to all templates."""
    items = MenuItem.objects.filter(is_active=True).order_by('order', 'title')
    return {'menu_items': items}