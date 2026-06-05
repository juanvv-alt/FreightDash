from django.urls import path
from . import views

app_name = 'voyage'

urlpatterns = [
    path('', views.tce_calculator, name='tce_calculator'),
    path('vessel-compare/', views.vessel_compare, name='vessel_compare'),
    path('freight-matrix/', views.freight_matrix, name='freight_matrix'),
    path('indices/', views.indices_redirect, name='indices'),
    path('indices/custom/', views.indices_custom, name='indices_custom'),
    path('indices/<slug:vessel>/', views.indices_dashboard, name='indices_by_vessel'),
    path('upload-excel-indices/', views.upload_excel_indices, name='upload_excel_indices'),
    path('review-excel-mappings/<str:session_id>/', views.review_excel_mappings, name='review_excel_mappings'),
    path('upload-pdf-indices/', views.upload_pdf_indices, name='upload_pdf_indices'),
    path('verify-pdf-indices/<str:session_id>/', views.verify_pdf_indices, name='verify_pdf_indices'),
]
