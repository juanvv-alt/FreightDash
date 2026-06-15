from django.urls import path

from . import views

app_name = "supply"

urlpatterns = [
    path("supply-forecast/", views.supply_forecast, name="supply_forecast"),
    path(
        "supply-forecast/chart-data/<slug:vessel_class>/",
        views.supply_chart_data,
        name="supply_chart_data",
    ),
    path("supply-forecast/status/", views.ais_status, name="ais_status"),
    path("supply-forecast/trigger-ingest/", views.trigger_ingest, name="trigger_ingest"),
    path("supply-forecast/trigger-aggregate/", views.trigger_aggregate, name="trigger_aggregate"),
]
