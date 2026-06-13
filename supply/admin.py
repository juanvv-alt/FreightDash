from django.contrib import admin

from .models import (DailySupplySnapshot, Port, PortCallEvent, SupplySignal,
                     TrackedVessel, VesselState)


@admin.register(Port)
class PortAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "port_type", "basin", "radius_nm", "is_active")
    list_filter = ("port_type", "country", "basin", "is_active")
    list_editable = ("radius_nm", "is_active")
    search_fields = ("name", "country")


@admin.register(TrackedVessel)
class TrackedVesselAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "mmsi",
        "imo",
        "vessel_class",
        "length_m",
        "max_draught_m",
        "last_seen",
        "is_excluded",
    )
    list_filter = ("vessel_class", "is_excluded")
    list_editable = ("is_excluded",)
    search_fields = ("name", "mmsi", "imo")
    readonly_fields = ("first_seen", "last_seen")


@admin.register(VesselState)
class VesselStateAdmin(admin.ModelAdmin):
    list_display = (
        "vessel",
        "loading_condition",
        "current_port",
        "speed_knots",
        "draught_m",
        "position_at",
    )
    list_filter = ("loading_condition", "current_port")
    search_fields = ("vessel__name", "vessel__mmsi")
    autocomplete_fields = ("vessel", "current_port")
    readonly_fields = ("updated_at",)


@admin.register(PortCallEvent)
class PortCallEventAdmin(admin.ModelAdmin):
    list_display = ("vessel", "event_type", "port", "loading_condition", "timestamp")
    list_filter = ("event_type", "port", "loading_condition")
    search_fields = ("vessel__name", "vessel__mmsi", "port__name")
    date_hierarchy = "timestamp"
    autocomplete_fields = ("vessel", "port")


@admin.register(DailySupplySnapshot)
class DailySupplySnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "vessel_class",
        "basin",
        "ballast_at_sea_count",
        "laden_at_sea_count",
        "in_port_load_count",
        "in_port_discharge_count",
        "expected_open_7d",
        "total_tracked",
    )
    list_filter = ("vessel_class", "basin")
    date_hierarchy = "date"


@admin.register(SupplySignal)
class SupplySignalAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "vessel_class",
        "direction",
        "score",
        "confidence",
        "method",
        "data_days",
    )
    list_filter = ("vessel_class", "direction", "method")
    date_hierarchy = "date"
