import os
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ON_VERCEL = os.getenv("VERCEL") == "1"
if not ON_VERCEL:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
DEBUG = os.getenv("RESILIO_DEBUG", "0" if ON_VERCEL else "1") == "1"
if ON_VERCEL and DEBUG:
    raise ImproperlyConfigured("RESILIO_DEBUG must be 0 on Vercel.")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if ON_VERCEL and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5):
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY to a generated private key (at least 50 characters)."
    )
if not SECRET_KEY:
    secret_file = BASE_DIR / ".local-secret"
    if not secret_file.exists():
        from django.core.management.utils import get_random_secret_key

        try:
            fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(get_random_secret_key())
        except FileExistsError:
            pass
    SECRET_KEY = secret_file.read_text()


def configured_list(name):
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


ALLOWED_HOSTS = configured_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = configured_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if ON_VERCEL:
    for name in ["VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"]:
        value = os.getenv(name, "").strip()
        if value:
            host = urlsplit(value if "://" in value else "https://" + value).hostname
            if host:
                ALLOWED_HOSTS.append(host)
                CSRF_TRUSTED_ORIGINS.append("https://" + host)
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Enable Vercel system environment variables or set DJANGO_ALLOWED_HOSTS."
        )
    if "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Use explicit hostnames, not *.")
else:
    ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "coordination",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
database_url = os.getenv("DATABASE_URL", "")
if ON_VERCEL and os.getenv("VERCEL_ENV") == "preview":
    database_url = os.getenv("RESILIO_PREVIEW_DATABASE_URL", "")
    if not database_url:
        raise ImproperlyConfigured(
            "Preview builds require an isolated RESILIO_PREVIEW_DATABASE_URL. Production DATABASE_URL is never reused for previews."
        )
if ON_VERCEL and not database_url:
    raise ImproperlyConfigured(
        "Connect a PostgreSQL database and set DATABASE_URL before deploying."
    )
if database_url:
    import dj_database_url

    config = dj_database_url.parse(
        database_url, conn_max_age=0, conn_health_checks=True
    )
    if config["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL URL.")
    config["DISABLE_SERVER_SIDE_CURSORS"] = True
    config.setdefault("OPTIONS", {}).update({"connect_timeout": 10})
    if ON_VERCEL:
        config["OPTIONS"]["sslmode"] = "require"
    DATABASES = {"default": config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("RESILIO_DB", str(BASE_DIR / "db.sqlite3")),
            "OPTIONS": {"timeout": 8, "transaction_mode": "IMMEDIATE"},
        }
    }
if os.getenv("RESILIO_TEST_DB"):
    DATABASES["default"]["TEST"] = {"NAME": os.environ["RESILIO_TEST_DB"]}
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if ON_VERCEL or os.getenv("RESILIO_HTTPS") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

if ON_VERCEL:
    # Vercel's trusted edge supplies this header; never trust it on an unproxied LAN server.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 2592000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_REFERRER_POLICY = "same-origin"
