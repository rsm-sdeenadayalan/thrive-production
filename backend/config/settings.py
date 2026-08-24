import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Tiny stdlib .env loader (no python-dotenv dependency): backend/.env, if
# present, seeds os.environ for local dev. Real env vars always win —
# setdefault never overrides something already exported. Not used/needed in
# production, where the platform injects env vars directly.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _value = _line.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip())

SECRET_KEY = os.environ.get("THRIVE_SECRET_KEY", "dev-only-insecure")
DEBUG = os.environ.get("THRIVE_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rsm_thrive",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# SQLite by default (tests, quick local). THRIVE_PG=1 switches to Postgres —
# the shape production uses (spec §7: nothing debugged first on the server).
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if os.environ.get("THRIVE_PG") == "1":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "thrive_dev"),
        "USER": os.environ.get("PGUSER", "thrive"),
        "PASSWORD": os.environ.get("PGPASSWORD", "thrive"),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Los_Angeles"
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DEFAULT_FROM_EMAIL = os.environ.get("THRIVE_FROM_EMAIL", "thrive-noreply@rady.ucsd.edu")

# No EMAIL_BACKEND was configured before Django's MAILERS setting existed, so
# email implicitly used the SMTP backend. MAILERS makes that explicit (Django
# test runner overrides "default" to locmem for the test suite regardless).
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    },
}

THRIVE_DEV_LOGIN_ENABLED = os.environ.get("THRIVE_DEV_LOGIN", "1") == "1"
THRIVE_FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "THRIVE_FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:3123",
    ).split(",")
    if origin.strip()
]

THRIVE_LLM = os.environ.get("THRIVE_LLM", "tritonai")
THRIVE_BOT_CONFIG = os.environ.get("THRIVE_BOT_CONFIG", "")
TRITONAI_API_KEY = os.environ.get("TRITONAI_API_KEY", "")
TRITONAI_MODEL = os.environ.get("TRITONAI_MODEL", "claude-opus-4-6-v1")
# Placeholder — verify via list_models at the TritonAI portal and correct.
TRITONAI_EMBED_MODEL = os.environ.get("TRITONAI_EMBED_MODEL", "embed-default")
