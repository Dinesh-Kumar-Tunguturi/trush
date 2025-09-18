from pathlib import Path
import environ
import dj_database_url
import os

# =====================
# Base directory
# =====================
BASE_DIR = Path(__file__).resolve().parent.parent

# =====================
# Load .env file
# =====================
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# =====================
# Core settings
# =====================
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env.bool("DEBUG", default=True)

# Default hosts for safety
default_hosts = [
    "localhost",
    "127.0.0.1",
    ".onrender.com",       # allow all Render subdomains
]

# Merge env hosts with defaults
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[]) + default_hosts

# =====================
# Installed apps
# =====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
]

# =====================
# Middleware
# =====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Full_web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Full_web.wsgi.application'

# =====================
# Database (PostgreSQL)
# =====================
DATABASES = {
    'default': dj_database_url.config(default=env("DATABASE_URL"))
}

# =====================
# Password validators
# =====================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =====================
# Internationalization
# =====================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =====================
# Static files
# =====================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# =====================
# Microsoft Graph (Only)
# Toggle with MS_GRAPH_ENABLED=true in .env
# =====================
MS_GRAPH_ENABLED = env.bool("MS_GRAPH_ENABLED", default=True)
MS_GRAPH_TENANT_ID = env("MS_GRAPH_TENANT_ID", default="")
MS_GRAPH_CLIENT_ID = env("MS_GRAPH_CLIENT_ID", default="")
MS_GRAPH_CLIENT_SECRET = env("MS_GRAPH_CLIENT_SECRET", default="")
MS_GRAPH_SENDER_EMAIL = env("MS_GRAPH_SENDER_EMAIL", default="")

# =====================
# Default primary key field type
# =====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
