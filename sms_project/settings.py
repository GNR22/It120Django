"""
Django settings for the IT 120 SMS Sender project.

All secrets and environment-specific values are read from environment
variables (optionally loaded from a local .env file that is NEVER committed).
See .env.example for the full list.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from .env (if present). Real environment variables win.
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f"{name} must be a whole number.")


# --------------------------------------------------------------------------
# Core security settings
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is not set. Copy .env.example to .env and fill in "
        "the values (see README.md, 'Installation and setup')."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "sms_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF protection for every POST form
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sms_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sms_project.wsgi.application"

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Extra hardening (safe defaults for both development and production)
# --------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    # Only effective when the site is served over HTTPS.
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)

# --------------------------------------------------------------------------
# SMS provider (TextBee) - credentials come ONLY from the environment
# --------------------------------------------------------------------------
TEXTBEE_API_KEY = os.environ.get("TEXTBEE_API_KEY", "")

# --------------------------------------------------------------------------
# Application behaviour
# --------------------------------------------------------------------------
# Country code assumed for numbers typed in local format (63 = Philippines).
SMS_DEFAULT_COUNTRY_CODE = os.environ.get("SMS_DEFAULT_COUNTRY_CODE", "63").lstrip("+")
# Maximum message length accepted by the form.
SMS_MAX_LENGTH = env_int("SMS_MAX_LENGTH", 480)
# Safety limit on successful submissions per calendar day (protects trial credit).
SMS_DAILY_LIMIT = env_int("SMS_DAILY_LIMIT", 20)

# --------------------------------------------------------------------------
# Logging (never log credentials)
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"sms_app": {"handlers": ["console"], "level": "INFO"}},
}
