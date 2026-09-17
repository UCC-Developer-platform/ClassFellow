"""
ClassFellow Web - Django 5 Project Settings (Phase 5 Web Architecture)
Configured for PostgreSQL 16 production operations with environment variable overrides
and automated test execution compatibility.
"""

import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure apps and classfellow_web are on sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Security settings
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-classfellow-phase5-web-architecture-super-secret-key-2026",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if host.strip()
]

# Application definition
INSTALLED_APPS = [
    # Core Django contrib
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Modular Domain Apps (Phase 5)
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.students.apps.StudentsConfig",
    "apps.fees.apps.FeesConfig",
    "apps.attendance.apps.AttendanceConfig",
    "apps.examinations.apps.ExaminationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Custom User Model (enforcing multi-role authentication)
AUTH_USER_MODEL = "accounts.User"

# Database Configuration: PostgreSQL 16 with environment-based overrides and SQLite fallback
DB_ENGINE = os.environ.get("DJANGO_DB_ENGINE", "postgresql").lower()

if DB_ENGINE == "sqlite":
    data_dir = BASE_DIR.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": data_dir / "classfellow_web.db",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", os.environ.get("POSTGRES_DB", "classfellow_db")),
            "USER": os.environ.get("DB_USER", os.environ.get("POSTGRES_USER", "postgres")),
            "PASSWORD": os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "postgres")),
            "HOST": os.environ.get("DB_HOST", os.environ.get("POSTGRES_HOST", "localhost")),
            "PORT": os.environ.get("DB_PORT", os.environ.get("POSTGRES_PORT", "5432")),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

