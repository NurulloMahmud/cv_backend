"""
Django settings for TezCV.uz backend (MongoDB/mongoengine edition).
"""

from pathlib import Path

import mongoengine
from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-tezcv-dev-key-change-this-in-production-abc123xyz'
)

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ---------------------------------------------------------------------------
# Installed apps  — NO admin, NO auth, NO contenttypes, NO sessions, NO messages
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'apps.accounts',
    'apps.cv',
    'apps.pdf_export',
]

# ---------------------------------------------------------------------------
# Middleware  — stripped of all SQL-backed middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ---------------------------------------------------------------------------
# Templates  — only the pdf_export dir; no auth context processors
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'apps' / 'pdf_export' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------------
# Database  — NOT used; mongoengine handles persistence
# ---------------------------------------------------------------------------
DATABASES = {}

# ---------------------------------------------------------------------------
# MongoDB via mongoengine
# ---------------------------------------------------------------------------
MONGODB_URI = config('MONGODB_URI', default='mongodb://localhost:27017/tezcv_dev')

try:
    mongoengine.connect(host=MONGODB_URI, alias='default')
except Exception as _mongo_exc:
    import sys
    print(
        f'\n[FATAL] Could not connect to MongoDB.\n'
        f'  URI: {MONGODB_URI[:60]}...\n'
        f'  Error: {_mongo_exc}\n'
        f'  Fix: set the MONGODB_URI environment variable to your real Atlas connection string.\n',
        file=sys.stderr,
    )
    raise SystemExit(1) from _mongo_exc

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------------------------
# JWT (PyJWT — no simplejwt)
# ---------------------------------------------------------------------------
JWT_SECRET_KEY = config('JWT_SECRET_KEY', default=SECRET_KEY)
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = config(
    'JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int
)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = config(
    'JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int
)
JWT_ALGORITHM = 'HS256'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.auth_utils.MongoJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # django.contrib.auth is not installed (no SQL), so AnonymousUser is unavailable.
    # Setting to None means unauthenticated requests have request.user = None.
    'UNAUTHENTICATED_USER': None,
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)
CORS_ALLOW_CREDENTIALS = True
# In production set CORS_ALLOW_ALL_ORIGINS=False and provide CORS_ALLOWED_ORIGINS
# as a comma-separated list, e.g.: https://tezcv.uz,https://www.tezcv.uz
_cors_origins = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOWED_ORIGINS = list(_cors_origins) if _cors_origins else [
    'http://localhost:3000',
    'http://localhost:5173',
    'http://localhost:8080',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:8080',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-session-key',
]
CORS_EXPOSE_HEADERS = [
    'x-session-key',
]

# ---------------------------------------------------------------------------
# DRF Spectacular (Swagger / OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'TezCV.uz API',
    'DESCRIPTION': 'CV Builder Platform — REST API Documentation',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'SECURITY': [{'BearerAuth': []}],
}
