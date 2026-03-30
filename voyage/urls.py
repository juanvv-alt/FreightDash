from django.urls import path
from . import views

app_name = 'voyage'

urlpatterns = [
    path('', views.tce_calculator, name='tce_calculator'),
    path('indices/', views.indices_redirect, name='indices'),
    path('indices/custom/', views.indices_custom, name='indices_custom'),
    path('indices/<slug:vessel>/', views.indices_dashboard, name='indices_by_vessel'),
]
