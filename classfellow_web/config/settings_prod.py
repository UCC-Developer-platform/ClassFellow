"""
ClassFellow Web - Hardened Production Django Settings (Category 17)
Enforces production security flags, HTTPS headers, secure session/CSRF cookies,
WhiteNoise static delivery with manifest safety, and structured logging.
"""

import os
import sys
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F401, F403

# Enforce DEBUG = False
DEBUG = False

# Strict Secret Key Validation
_raw_secret = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if _raw_secret and "insecure" not in _raw_secret:
    SECRET_KEY = _raw_secret
elif os.environ.get("CI") or os.environ.get("TESTING") or any("test" in arg for arg in sys.argv):
    # Allowed during automated test execution and CI/CD pipelines
    SECRET_KEY = "django-prod-test-key-for-automated-ci-matrix-validation-2026"
else:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable must be set to a secure value in production."
    )

# Dynamic ALLOWED_HOSTS configuration
_allowed_hosts_env = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
if _allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "web", "testserver"]

# HTTPS / SSL Security Hardening
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "yes")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HTTP Strict Transport Security (HSTS) - 1 Year duration with subdomains and preload
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Reverse Proxy SSL Header (Nginx SSL termination)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Static Files Configuration & WhiteNoise
STATIC_ROOT = BASE_DIR / "staticfiles"

# Insert WhiteNoiseMiddleware directly after SecurityMiddleware
_mw_list = list(MIDDLEWARE)
if "whitenoise.middleware.WhiteNoiseMiddleware" not in _mw_list:
    if "django.middleware.security.SecurityMiddleware" in _mw_list:
        _sec_idx = _mw_list.index("django.middleware.security.SecurityMiddleware")
        _mw_list.insert(_sec_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
    else:
        _mw_list.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")
    MIDDLEWARE = _mw_list

# WhiteNoise storage with manifest safety
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MANIFEST_STRICT = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Production Logging: Structured stdout/stderr logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} [{name}:{lineno}] {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
