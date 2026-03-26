from django.urls import path
from . import views

app_name = 'voyage'

urlpatterns = [
    path('', views.tce_calculator, name='tce_calculator'),
]
