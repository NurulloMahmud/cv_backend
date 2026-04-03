"""
URL patterns for the cv app.
Mounted at /api/cv/ in config/urls.py.
"""

from django.urls import path

from .views import CVDetailView, CVListCreateView

urlpatterns = [
    path('', CVListCreateView.as_view(), name='cv-list-create'),
    path('<str:pk>/', CVDetailView.as_view(), name='cv-detail'),
]
