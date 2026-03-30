from django.urls import path
from . import views

app_name = 'voyage'

urlpatterns = [
    path('', views.tce_calculator, name='tce_calculator'),
    path('indices/', views.indices_redirect, name='indices'),
    path('indices/<slug:vessel>/', views.indices_dashboard, name='indices_by_vessel'),
]
