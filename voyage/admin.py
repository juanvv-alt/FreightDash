import nested_admin
from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html
from django.shortcuts import redirect, render
from django.urls import path, reverse

from .models import (
    AvailableIndex,
    CustomIndexPreset,
    DailyIndexValue,
    FreightVoyage,
    RouteParameters,
    VesselFuelConsumption,
    VesselFuelProfile,
    VesselProfile,
    VesselSpeedProfile,
    VoyageFuelSplit,
)


VESSEL_SIZE_CHOICES = [
    ('capesize', 'Capesize'),
    ('panamax', 'Panamax'),
    ('supramax', 'Supramax'),
    ('handysize', 'Handysize'),
    ('bunker', 'Bunker'),
]


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
        ('Port Consumption', {
            'fields': ('port_consumption',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomIndexPreset)
class CustomIndexPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AvailableIndex)
class AvailableIndexAdmin(admin.ModelAdmin):
    list_display = ('name', 'vessel_size', 'order', 'is_active', 'updated_at', 'remove_link')
    list_editable = ('order', 'is_active')
    list_filter = ('vessel_size', 'is_active')
    search_fields = ('name',)
    ordering = ('vessel_size', 'order', 'name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ('remove_selected_indices',)

    @admin.action(description='Remove selected indices')
    def remove_selected_indices(self, request, queryset):
        removed = queryset.count()
        queryset.delete()
        self.message_user(request, f'Removed {removed} index record(s).', level=messages.SUCCESS)

    def remove_link(self, obj):
        url = reverse('admin:voyage_availableindex_delete', args=[obj.pk])
        return format_html('<a class="deletelink" href="{}">Remove</a>', url)

    remove_link.short_description = 'Remove'


@admin.register(DailyIndexValue)
class DailyIndexValueAdmin(admin.ModelAdmin):
    list_display = ('date', 'index', 'value', 'updated_at')
    list_filter = ('index__vessel_size', 'index', 'date')
    search_fields = ('index__name',)
    ordering = ('-date', 'index__name')
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# Vessel profile — all speed + fuel data on a single page via nested inlines
# ---------------------------------------------------------------------------

class VesselSpeedProfileInline(nested_admin.NestedTabularInline):
    model = VesselSpeedProfile
    extra = 1
    fields = ('name', 'ballast_speed', 'laden_speed', 'is_default')
    verbose_name = 'Speed Profile'
    verbose_name_plural = 'Speed Profiles  (e.g. CP, ECO, SUPER ECO)'


class VesselFuelConsumptionNestedInline(nested_admin.NestedTabularInline):
    model = VesselFuelConsumption
    extra = 1
    fields = ('fuel_type', 'sea_consumption', 'port_consumption')
    verbose_name = 'Fuel line'
    verbose_name_plural = 'Fuel lines  (MT/day)'


class VesselFuelProfileInline(nested_admin.NestedStackedInline):
    model = VesselFuelProfile
    extra = 1
    fields = ('name', 'is_default')
    inlines = [VesselFuelConsumptionNestedInline]
    verbose_name = 'Consumption Profile'
    verbose_name_plural = 'Consumption Profiles  (e.g. CP CONS, ECO CONS)'
    show_change_link = False


@admin.register(VesselProfile)
class VesselProfileAdmin(nested_admin.NestedModelAdmin):
    list_display = ('name', 'vessel_size', 'dwt', 'draft', 'grain_capacity', 'is_active')
    list_filter = ('vessel_size', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [VesselSpeedProfileInline, VesselFuelProfileInline]
    fieldsets = (
        ('Vessel', {
            'fields': (('name', 'vessel_size', 'is_active'), ('dwt', 'draft', 'grain_capacity'), 'npc', 'default_port_consumption'),
        }),
    )


# Keep a minimal standalone VesselFuelProfile admin for direct lookup / bulk edits
class VesselFuelConsumptionInlineStandalone(admin.TabularInline):
    model = VesselFuelConsumption
    extra = 1
    fields = ('fuel_type', 'sea_consumption', 'port_consumption')


@admin.register(VesselFuelProfile)
class VesselFuelProfileAdmin(admin.ModelAdmin):
    list_display = ('vessel', 'name', 'is_default')
    list_filter = ('is_default', 'vessel__vessel_size')
    search_fields = ('name', 'vessel__name')
    inlines = (VesselFuelConsumptionInlineStandalone,)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('vessel__name', 'name')


# ---------------------------------------------------------------------------
# Freight voyage — 3 clear sections instead of 8
# ---------------------------------------------------------------------------

class VoyageFuelSplitInline(admin.TabularInline):
    model = VoyageFuelSplit
    extra = 1
    fields = ('fuel_index', 'weight_pct')
    verbose_name = 'Fuel price index'
    verbose_name_plural = 'Fuel price split  (index + weight %)'


@admin.register(FreightVoyage)
class FreightVoyageAdmin(admin.ModelAdmin):
    list_display = ('name', 'vessel', 'is_active', 'ballast_distance', 'laden_distance', 'load_rate', 'discharge_rate', 'daily_hire_index')
    list_filter = ('is_active', 'vessel__vessel_size', 'intake_mode')
    list_editable = ('is_active',)
    search_fields = ('name', 'commodity', 'ballast_port')
    inlines = (VoyageFuelSplitInline,)
    readonly_fields = ('created_at', 'updated_at')
    save_on_top = True

    fieldsets = (
        ('Route & Cargo', {
            'description': 'Distances, ports, loading/discharging rates and cargo intake.',
            'fields': (
                ('name', 'commodity', 'is_active'),
                ('ballast_distance', 'laden_distance'),
                ('ballast_port',),
                ('load_ports', 'discharge_ports'),
                ('load_rate', 'turntime_load_hours'),
                ('discharge_rate', 'turntime_discharge_hours'),
                ('intake_mode', 'intake_manual'),
                ('draft_limit', 'stowage_factor'),
            ),
        }),
        ('Vessel & Speed / Fuel Profiles', {
            'description': 'Select the vessel and which speed/fuel variant to use for this voyage.',
            'fields': (
                ('vessel', 'speed_profile', 'fuel_profile'),
            ),
        }),
        ('Financials', {
            'description': 'Port costs, sea margin, commissions and the daily hire index that drives the freight matrix.',
            'fields': (
                ('port_exp_load_port', 'port_exp_discharge_port', 'misc_expenses'),
                ('apply_same_sea_margin', 'sea_margin_ballast_pct', 'sea_margin_laden_pct'),
                ('address_commission_pct', 'brokerage_commission_pct'),
                ('daily_hire_index',),
            ),
        }),
    )


def indices_config_view(request):
    valid_vessels = {key for key, _ in VESSEL_SIZE_CHOICES}
    selected_vessel = request.GET.get('vessel') or request.POST.get('vessel') or 'capesize'
    if selected_vessel not in valid_vessels:
        selected_vessel = 'capesize'

    if request.method == 'POST':
        selected_indices_raw = request.POST.getlist('indices')
        selected_indices = []
        seen = set()
        for index_name in selected_indices_raw:
            cleaned = (index_name or '').strip()
            if not cleaned or len(cleaned) > 120 or cleaned in seen:
                continue
            seen.add(cleaned)
            selected_indices.append(cleaned)

        with transaction.atomic():
            # Any index not present in the token list is hidden for this vessel tab.
            AvailableIndex.objects.filter(vessel_size=selected_vessel).update(is_active=False)

            for order, index_name in enumerate(selected_indices, start=1):
                index_obj, _ = AvailableIndex.objects.get_or_create(
                    name=index_name,
                    defaults={
                        'vessel_size': selected_vessel,
                        'order': order,
                        'is_active': True,
                    },
                )
                changed = False
                if index_obj.vessel_size != selected_vessel:
                    index_obj.vessel_size = selected_vessel
                    changed = True
                if index_obj.order != order:
                    index_obj.order = order
                    changed = True
                if not index_obj.is_active:
                    index_obj.is_active = True
                    changed = True
                if changed:
                    index_obj.save(update_fields=['vessel_size', 'order', 'is_active', 'updated_at'])

        messages.success(request, 'Indices display configuration updated.')
        return redirect(f"{reverse('admin:indices-config')}?vessel={selected_vessel}")

    active_indices = list(
        AvailableIndex.objects.filter(vessel_size=selected_vessel, is_active=True)
        .order_by('order', 'name')
        .values_list('name', flat=True)
    )
    suggestions = list(AvailableIndex.objects.order_by('name').values_list('name', flat=True))

    context = {
        **admin.site.each_context(request),
        'title': 'Indices Display Config',
        'selected_vessel': selected_vessel,
        'vessel_choices': VESSEL_SIZE_CHOICES,
        'active_indices': active_indices,
        'all_index_suggestions': suggestions,
    }
    return render(request, 'admin/indices_config.html', context)


_voyage_original_get_urls = admin.site.get_urls


def _voyage_admin_urls():
    from .views import upload_excel_indices, upload_batch_indices, review_excel_mappings
    custom_urls = [
        path(
            'upload-excel-indices/',
            admin.site.admin_view(upload_excel_indices),
            name='upload-excel-indices',
        ),
        path(
            'upload-batch-indices/',
            admin.site.admin_view(upload_batch_indices),
            name='upload-batch-indices',
        ),
        path(
            'review-excel-mappings/<str:session_id>/',
            admin.site.admin_view(review_excel_mappings),
            name='review-excel-mappings',
        ),
        path(
            'indices-config/',
            admin.site.admin_view(indices_config_view),
            name='indices-config',
        ),
    ]
    return custom_urls + _voyage_original_get_urls()


admin.site.get_urls = _voyage_admin_urls


from .models import FFACurve, FFACurvePeriod


class FFACurvePeriodInline(admin.TabularInline):
    model = FFACurvePeriod
    extra = 0
    can_delete = False
    readonly_fields = ('label', 'period_type', 'start_date', 'end_date', 'bid', 'offer')


@admin.register(FFACurve)
class FFACurveAdmin(admin.ModelAdmin):
    list_display = ('vessel_class', 'created_at')
    readonly_fields = ('created_at',)
    inlines = [FFACurvePeriodInline]
