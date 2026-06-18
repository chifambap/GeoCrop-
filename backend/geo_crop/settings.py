"""
Django settings for Geo-Crop Collector
PostgreSQL + PostGIS | JWT Auth | MBTiles upload | Device Sync
"""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env natively since we aren't using docker-compose anymore
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ.setdefault(k, v)

# ─── Adaptive capacity (auto-set by deploy.sh via capacity.py) ───────────────
from geo_crop import capacity as _cap

GEOJSON_MAX_FEATURES = int(os.environ.get('GEOJSON_MAX_FEATURES', _cap.GEOJSON_MAX_FEATURES))
EXPORT_MAX_ROWS      = int(os.environ.get('EXPORT_MAX_ROWS',      _cap.EXPORT_MAX_ROWS))
SYNC_PULL_MAX_ROWS   = int(os.environ.get('SYNC_PULL_MAX_ROWS',   _cap.SYNC_PULL_MAX_ROWS))
ITERATOR_CHUNK_SIZE  = int(os.environ.get('ITERATOR_CHUNK_SIZE',  _cap.ITERATOR_CHUNK_SIZE))

# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me-in-production')
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost 127.0.0.1').split()

# ─── Apps ─────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',           # PostGIS support

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',

    # Local
    'apps.accounts',
    'apps.fields',
    'apps.mbtiles',
    'apps.sync',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'geo_crop.middleware.DisableInspectMiddleware',
]

ROOT_URLCONF = 'geo_crop.urls'
WSGI_APPLICATION = 'geo_crop.wsgi.application'
AUTH_USER_MODEL = 'accounts.User'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

# ─── Database (PostGIS) ───────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME':     os.environ.get('DB_NAME',     'geocrop'),
        'USER':     os.environ.get('DB_USER',     'geocrop'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'geocrop'),
        'HOST':         os.environ.get('DB_HOST',     'localhost'),
        'PORT':         os.environ.get('DB_PORT',     '5432'),
        'CONN_MAX_AGE': 60,
    }
}

# ─── DRF + JWT ────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': int(os.environ.get('PAGE_SIZE', _cap.PAGE_SIZE)),
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON', _cap.THROTTLE_ANON),
        'user': os.environ.get('THROTTLE_USER', _cap.THROTTLE_USER),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
# DEBUG=True: allow any origin (local dev). DEBUG=False: never wildcard; set
# CORS_ALLOWED_ORIGINS to a comma-separated list of front-end origins (https://…).
_cors_origins_env = (os.environ.get('CORS_ALLOWED_ORIGINS') or '').strip()
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
elif _cors_origins_env:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True

# ─── Static & Media ───────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

# MBTiles stored inside MEDIA_ROOT/mbtiles/
MBTILES_ROOT = MEDIA_ROOT / 'mbtiles'
MBTILES_MAX_SIZE_MB = int(os.environ.get('MBTILES_MAX_SIZE_MB', _cap.MBTILES_MAX_SIZE_MB))

# ─── i18n ─────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Upload limits ────────────────────────────────────────────────────────────
# Large GeoJSON / GPKG overlays and MBTiles can be arbitrarily big.
# Nginx already enforces client_max_body_size 0; Django must not block first.
DATA_UPLOAD_MAX_MEMORY_SIZE  = None   # no limit on non-file POST data
DATA_UPLOAD_MAX_NUMBER_FILES = None   # no limit on number of file parts
FILE_UPLOAD_MAX_MEMORY_SIZE  = 10 * 1024 * 1024  # 10 MB threshold for temp-file swap

# ─── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Email (SMTP) ────────────────────────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@geos.zingsageocrops.com')
