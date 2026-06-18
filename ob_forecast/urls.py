from django.urls import path

from . import views

app_name = "ob_forecast"

urlpatterns = [
    path("ob-forecast/", views.ob_forecast_view, name="ob_forecast"),
    path(
        "ob-forecast/chart-data/<slug:zone>/",
        views.ob_chart_data,
        name="ob_chart_data",
    ),
    path("ob-forecast/upload/", views.ob_upload, name="ob_upload"),
    path("ob-forecast/daily-entry/", views.ob_daily_entry, name="ob_daily_entry"),
    path("ob-forecast/aggregate/", views.ob_aggregate, name="ob_aggregate"),
    path("ob-forecast/delete-series/", views.ob_delete_series, name="ob_delete_series"),
    path("ob-forecast/backtest/<slug:zone>/", views.ob_backtest_view, name="ob_backtest"),
    path("ob-forecast/backtest-data/<slug:zone>/", views.ob_backtest_data, name="ob_backtest_data"),
    path("ob-forecast/run-backtest/<slug:zone>/", views.ob_run_backtest, name="ob_run_backtest"),
]
