from django.contrib import admin

from .models import OBForecastSignal, OBTonnageSnapshot, OBUploadLog


@admin.register(OBTonnageSnapshot)
class OBTonnageSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "zone", "series", "vessel_count", "vessel_dwt")
    list_filter = ("zone", "series")
    date_hierarchy = "date"
    search_fields = ("zone",)


@admin.register(OBForecastSignal)
class OBForecastSignalAdmin(admin.ModelAdmin):
    list_display = ("date", "zone", "direction", "score", "confidence", "method", "data_days")
    list_filter = ("zone", "direction", "method")
    date_hierarchy = "date"


@admin.register(OBUploadLog)
class OBUploadLogAdmin(admin.ModelAdmin):
    list_display = ("uploaded_at", "zone", "series", "filename", "rows_added", "rows_skipped")
    list_filter = ("zone", "series")
    readonly_fields = ("uploaded_at",)
