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
]
