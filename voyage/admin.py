from django.contrib import admin
from .models import CustomIndexPreset, RouteParameters


@admin.register(RouteParameters)
class RouteParametersAdmin(admin.ModelAdmin):
    list_display = ('route', 'intake', 'ballast_distance', 'laden_distance', 'updated_at')
    search_fields = ('route',)
    fieldsets = (
        ('Route Information', {
            'fields': ('route',)
        }),
        ('Distance Parameters', {
            'fields': ('ballast_distance', 'laden_distance'),
        }),
        ('Cargo Parameters', {
            'fields': ('intake', 'load_rate', 'discharge_rate', 'turntime_hours'),
        }),
        ('Port Expenses', {
            'fields': ('port_exp_load_port', 'port_exp_discharge_port'),
        }),
        ('Commission & Margins', {
            'fields': ('freight_commission_pct', 'sea_margin_pct'),
        }),
        ('Speed Parameters', {
            'fields': ('ballast_speed', 'laden_speed'),
        }),
        ('Consumption Parameters', {
            'fields': ('ballast_consumption', 'laden_consumption', 'port_consumption'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomIndexPreset)
class CustomIndexPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
