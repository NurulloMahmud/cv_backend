"""
TezCV.uz — Main URL Configuration
"""

from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/auth/', include('apps.accounts.urls')),
    path('api/cv/', include('apps.cv.urls')),
    path('api/pdf/', include('apps.pdf_export.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
