import base64
import hashlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
SECRET_KEY = os.environ.get("SECRET_KEY", "test-only-secret")
if ENVIRONMENT == "production" and SECRET_KEY == "test-only-secret":
    raise RuntimeError("SECRET_KEY is required in production")

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    host
    for host in os.environ.get("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1").split(",")
    if host
]

INSTALLED_APPS = [
    "django_mongodb_backend",
    "fetchly.apps.MongoAdminConfig",
    "fetchly.apps.MongoAuthConfig",
    "fetchly.apps.MongoContentTypesConfig",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "usage",
    "downloads",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "servestatic.middleware.ServeStaticMiddleware",
    "fetchly.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "fetchly.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

ROOT_URLCONF = "fetchly.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "fetchly.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": os.environ.get("MONGODB_URI", "mongodb://localhost:27017/fetchly_test"),
        "NAME": os.environ.get("MONGODB_NAME", "fetchly_test"),
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DOWNLOAD_ROOT = Path(os.environ.get("DOWNLOAD_ROOT", BASE_DIR / "data" / "downloads"))
DOWNLOAD_TASK_TTL_SECONDS = int(os.environ.get("DOWNLOAD_TASK_TTL_SECONDS", "3600"))
DOWNLOAD_MAX_BYTES = int(os.environ.get("DOWNLOAD_MAX_BYTES", str(500 * 1024 * 1024)))
DAILY_QUOTA_BYTES = int(os.environ.get("DAILY_QUOTA_BYTES", str(2 * 1024 * 1024 * 1024)))
ACTIVE_DOWNLOAD_LIMIT = int(os.environ.get("ACTIVE_DOWNLOAD_LIMIT", "2"))
INSPECTION_RATE_LIMIT = int(os.environ.get("INSPECTION_RATE_LIMIT", "20"))
INSPECTION_RATE_WINDOW_SECONDS = int(os.environ.get("INSPECTION_RATE_WINDOW_SECONDS", "3600"))
STALE_TASK_SECONDS = int(os.environ.get("STALE_TASK_SECONDS", "300"))
MAINTENANCE_INTERVAL_SECONDS = int(os.environ.get("MAINTENANCE_INTERVAL_SECONDS", "300"))
WORKER_HEARTBEAT_KEY = "fetchly:worker:heartbeat"
_resolver_keys = os.environ.get("RESOLVER_ENCRYPTION_KEYS", "")
if ENVIRONMENT == "production" and not _resolver_keys:
    raise RuntimeError("RESOLVER_ENCRYPTION_KEYS is required in production")
RESOLVER_ENCRYPTION_KEYS = [key for key in _resolver_keys.split(",") if key] or [
    base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()).decode()
]
IDENTITY_HMAC_KEYS = [
    key for key in os.environ.get("IDENTITY_HMAC_KEYS", SECRET_KEY).split(",") if key
]
TRUSTED_PROXY_NETWORKS = [
    network
    for network in os.environ.get("TRUSTED_PROXY_NETWORKS", "127.0.0.1/32,::1/128").split(",")
    if network
]

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"
MIGRATION_MODULES = {
    "admin": "mongo_migrations.admin",
    "auth": "mongo_migrations.auth",
    "contenttypes": "mongo_migrations.contenttypes",
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
CSRF_COOKIE_SECURE = ENVIRONMENT == "production"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"
SESSION_COOKIE_AGE = int(os.environ.get("STAFF_SESSION_SECONDS", "28800"))
