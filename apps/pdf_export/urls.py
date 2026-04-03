"""
URL patterns for the pdf_export app.
Mounted at /api/pdf/ in config/urls.py.
"""

from django.urls import path

from .views import CVExportPDFView, CVPreviewHTMLView

urlpatterns = [
    path('<str:pk>/export-pdf/', CVExportPDFView.as_view(), name='cv-export-pdf'),
    path('<str:pk>/preview/', CVPreviewHTMLView.as_view(), name='cv-preview-html'),
]
