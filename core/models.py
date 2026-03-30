from django.db import models


class MenuItem(models.Model):
    """Model for managing navigation menu items."""
    
    title = models.CharField(max_length=100, help_text="Display text for the menu item")
    url = models.CharField(max_length=200, help_text="URL path for the menu item (e.g., /tce-calculator/)")
    icon = models.CharField(
        max_length=50, 
        default="fas fa-circle",
        help_text="Font Awesome icon class (e.g., 'fas fa-ship', 'fas fa-home')"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text='Optional parent item to create nested menu groups.',
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower numbers appear first)")
    is_active = models.BooleanField(default=True, help_text="Show this item in the menu")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Menu Item'
        verbose_name_plural = 'Menu Builder'
    
    def __str__(self):
        return self.title


# Create your models here.