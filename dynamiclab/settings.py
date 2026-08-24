"""
Django settings for Dynamic LabSystems.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Set DJANGO_SECRET_KEY in the environment for production deployments.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-me-before-deploying",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Dynamic LabSystems apps
    "accounts",
    "catalog",
    "samples",
    "labtests",
    "dashboard",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dynamiclab.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "dynamiclab.wsgi.application"


# Database
# Defaults to local SQLite for zero-setup dev/demo use. Set DATABASE_URL
# (e.g. postgres://user:pass@host:5432/dbname) for production/Postgres.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"

# Default deployment timezone. Override with DJANGO_TIME_ZONE if the lab is
# elsewhere; individual users' displayed times follow this setting.
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Bangkok")

USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "login"

# Branding
SITE_NAME = "Dynamic LabSystems"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Email
# Sends a notification whenever a new sample is registered (see samples.emails).
# Set EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD to enable real delivery via
# SMTP; until those are set, mail is only written to the app logs (safe default —
# nothing is silently lost, but nothing is actually emailed either).
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
    EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
    # Cap how long Django will wait to connect/talk to the SMTP server. Without
    # this, a wrong host/port can hang the connection attempt indefinitely,
    # which eventually gets the whole request worker killed by the app server
    # (a hard kill Python can't catch) instead of raising an error that
    # samples.emails can catch and swallow. Keeping this well under the app
    # server's request timeout is what makes a bad mail config fail safely.
    EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Dynamic LabSystems <no-reply@dynamiclabsystems.local>")

# Every newly registered sample is emailed here. Override with SAMPLE_NOTIFICATION_EMAIL
# if this should go somewhere else, or set it to an empty string to turn the
# notification off entirely.
SAMPLE_NOTIFICATION_EMAIL = os.environ.get("SAMPLE_NOTIFICATION_EMAIL", "info@dynamicapac.com")
