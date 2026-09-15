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
# Extra hosts (comma-separated) let a temporary tunnel or preview host reach
# the API; the localhost defaults always stay so normal dev never breaks.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"] + [
    host.strip()
    for host in os.environ.get("THRIVE_EXTRA_HOSTS", "").split(",")
    if host.strip()
]

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
    "rsm_thrive.views.auth.ThriveAllowlistMiddleware",
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
SESSION_COOKIE_NAME = os.environ.get("THRIVE_SESSION_COOKIE_NAME", "sessionid_thrive")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Send mail to the local Postfix listener. Postfix is configured on this server
# to relay through UCSD with TLS and without an application plaintext password.
# Django only talks to localhost; override these if a different relay is needed.
THRIVE_EMAIL_HOST = os.environ.get("THRIVE_EMAIL_HOST", "127.0.0.1")
THRIVE_EMAIL_PORT = int(os.environ.get("THRIVE_EMAIL_PORT", "25"))
THRIVE_EMAIL_USE_TLS = os.environ.get("THRIVE_EMAIL_USE_TLS", "0") == "1"
THRIVE_EMAIL_TIMEOUT = int(os.environ.get("THRIVE_EMAIL_TIMEOUT", "15"))

# No EMAIL_BACKEND was configured before Django's MAILERS setting existed. With
# Django 6.1, MAILERS must provide explicit SMTP OPTIONS.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": THRIVE_EMAIL_HOST,
            "port": THRIVE_EMAIL_PORT,
            "use_tls": THRIVE_EMAIL_USE_TLS,
            "timeout": THRIVE_EMAIL_TIMEOUT,
        },
    },
}

THRIVE_DEV_LOGIN_ENABLED = os.environ.get("THRIVE_DEV_LOGIN", "1") == "1"
THRIVE_AUTH = os.environ.get("THRIVE_AUTH", "local").lower()
THRIVE_REQUIRE_ALLOWLIST = os.environ.get(
    "THRIVE_REQUIRE_ALLOWLIST",
    "1" if THRIVE_AUTH == "ucsd_ldap" else "0",
) == "1"
THRIVE_ALLOWED_USERS = [
    user.strip().lower().removesuffix("@ucsd.edu")
    for user in os.environ.get("THRIVE_ALLOWED_USERS", "").split(",")
    if user.strip()
]
THRIVE_ALLOWED_USERS_FILE = os.environ.get("THRIVE_ALLOWED_USERS_FILE", "")
THRIVE_AUTO_CREATE_PROFILE = os.environ.get("THRIVE_AUTO_CREATE_PROFILE", "1") == "1"
THRIVE_DEFAULT_PROFILE_PROGRAM = os.environ.get("THRIVE_DEFAULT_PROFILE_PROGRAM", "MSBA")
THRIVE_DEFAULT_PROFILE_TRACK = os.environ.get("THRIVE_DEFAULT_PROFILE_TRACK", "11 month")
THRIVE_DEFAULT_PROFILE_CURRENT_TERM = os.environ.get(
    "THRIVE_DEFAULT_PROFILE_CURRENT_TERM", "Fall 2026")
THRIVE_DEFAULT_PROFILE_PROGRAM_START = os.environ.get(
    "THRIVE_DEFAULT_PROFILE_PROGRAM_START", "2026-09-01")
THRIVE_FRONTEND_BASE_PATH = os.environ.get("THRIVE_FRONTEND_BASE_PATH", "").rstrip("/")
THRIVE_FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "THRIVE_FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:3123",
    ).split(",")
    if origin.strip()
]

# Browsers send an Origin header on POSTs and Django rejects any origin it
# does not trust — so every frontend origin (including a temporary tunnel
# host passed via THRIVE_FRONTEND_ORIGINS) must also be CSRF-trusted.
CSRF_TRUSTED_ORIGINS = [
    origin for origin in THRIVE_FRONTEND_ORIGINS if origin.startswith("http")
]

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
if THRIVE_AUTH == "ucsd_ldap":
    AUTHENTICATION_BACKENDS = ["rsm_thrive.views.auth.UCSDLDAPBackend"]
    if os.environ.get("THRIVE_LOCAL_AUTH_FALLBACK", "0") == "1":
        AUTHENTICATION_BACKENDS.append("django.contrib.auth.backends.ModelBackend")
    LDAP_AUTH_URL = os.environ.get("LDAP_AUTH_URL", "ldaps://ldap.ad.ucsd.edu:636")
    LDAP_AUTH_SEARCH_BASE = os.environ.get("LDAP_AUTH_SEARCH_BASE", "dc=ad,dc=ucsd,dc=edu")
    LDAP_AUTH_OBJECT_CLASS = os.environ.get("LDAP_AUTH_OBJECT_CLASS", "user")
    LDAP_AUTH_CONNECTION_USERNAME = os.environ.get(
        "LDAP_AUTH_CONNECTION_USERNAME",
        "cn=LDAP Access,OU=Service Account,OU=ITS,OU=SDSC,dc=ad,dc=ucsd,dc=edu",
    )
    LDAP_AUTH_CONNECTION_PASSWORD = os.environ.get("LDAP_AUTH_CONNECTION_PASSWORD", "")
    LDAP_AUTH_CONNECTION_PASSWORD_FILE = os.environ.get(
        "LDAP_AUTH_CONNECTION_PASSWORD_FILE",
        "/etc/shiny-server/ldap-base-bind-password.txt",
    )
    LDAP_AUTH_ACTIVE_DIRECTORY_DOMAIN = os.environ.get(
        "LDAP_AUTH_ACTIVE_DIRECTORY_DOMAIN", "UCSD.EDU")

# Which chat backend answers a turn:
#
#   "codex"    LOCAL DEV DEFAULT. A personal ChatGPT/Codex subscription over
#              OAuth, needing no API key at all. See `CodexOAuthLLM`.
#   "tritonai" What the DEPLOYED service must run. Needs TRITONAI_API_KEY.
#   "fake"     Tests, which inject their own FakeLLM.
#
# The default is `codex` because the TritonAI keys this project is issued carry
# a fixed one-time budget with no reset, so an exhausted key stops all local
# work on the chatbots and there is nothing to wait for.
#
# DEPLOYMENT MUST SET THRIVE_LLM=tritonai EXPLICITLY. The codex backend
# authenticates as a person rather than as a metered service and talks to an
# endpoint with no compatibility promise; it is a laptop convenience, not a
# production dependency. `docs/VINCENT-ASKS.md` already lists the API key as
# something we supply, so the server environment is the place that pins this.
THRIVE_LLM = os.environ.get("THRIVE_LLM", "codex")
CODEX_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.4")
CODEX_TIMEOUT_SECONDS = int(os.environ.get("CODEX_TIMEOUT_SECONDS", "90"))
# Shared-credential serving, for a hosted TEST instance. Point this at a
# credential file copied from a developer's ~/.codex/auth.json; every request
# then uses that one account and no student ever signs in. Unset, the app falls
# back to the Codex CLI's own file, which is what a laptop wants.
#
# TREAT THE FILE AS A SECRET -- it holds a long-lived refresh token for a
# personal ChatGPT account.
CODEX_CREDENTIALS_PATH = os.environ.get("CODEX_CREDENTIALS_PATH", "")
# Whether this host may open a browser to sign in. Unset means "only if a
# terminal is attached", which keeps a laptop convenient and stops a headless
# server hanging a worker on a sign-in nobody can see.
CODEX_ALLOW_BROWSER_LOGIN = (
    None if os.environ.get("CODEX_ALLOW_BROWSER_LOGIN") is None
    else os.environ.get("CODEX_ALLOW_BROWSER_LOGIN") == "1")
# Embeddings are a SEPARATE provider from chat -- the codex backend has none.
# Unset, this follows THRIVE_LLM. See services/embeddings.py.
THRIVE_EMBEDDINGS = os.environ.get("THRIVE_EMBEDDINGS", "")
# The on-machine embedding model used when THRIVE_EMBEDDINGS resolves to
# "local" (which THRIVE_LLM=codex does). ~123MB, downloaded once from HF.
THRIVE_LOCAL_EMBED_MODEL = os.environ.get(
    "THRIVE_LOCAL_EMBED_MODEL", "minishlab/potion-retrieval-32M")
# Retrieval thresholds are calibrated PER ENCODER, so the overlay follows the
# embedding backend rather than being set by hand. An explicit THRIVE_BOT_CONFIG
# always wins -- that is the deploy-free tuning hook and this must not shadow it.
_embed_backend = THRIVE_EMBEDDINGS or THRIVE_LLM
THRIVE_BOT_CONFIG = os.environ.get("THRIVE_BOT_CONFIG", "")
if not THRIVE_BOT_CONFIG and _embed_backend in ("local", "codex"):
    THRIVE_BOT_CONFIG = str(BASE_DIR / "config" / "bots.local-embed.json")
# Who performs a web search when a backend cannot do it itself. Only the codex
# backend searches natively (OpenAI hosts the loop); TritonAI is vLLM behind
# LiteLLM and has no such loop, so without this `search_chat` silently answered
# from training data. See services/websearch.py.
#
#   "duckduckgo"  no key, and therefore the default. Parses a public HTML
#                 endpoint, so it is the one that breaks on a markup change.
#   "brave" | "serper" | "tavily"   keyed, via THRIVE_SEARCH_API_KEY.
#   "none"        no search. `search_chat` degrades to the model's own memory,
#                 which is what the whole codebase did before this existed.
THRIVE_SEARCH = os.environ.get("THRIVE_SEARCH", "duckduckgo")
THRIVE_SEARCH_API_KEY = os.environ.get("THRIVE_SEARCH_API_KEY", "")
TRITONAI_API_KEY = os.environ.get("TRITONAI_API_KEY", "")
TRITONAI_MODEL = os.environ.get("TRITONAI_MODEL", "claude-sonnet-4-6")
# Placeholder — verify via list_models at the TritonAI portal and correct.
TRITONAI_EMBED_MODEL = os.environ.get("TRITONAI_EMBED_MODEL", "api-tgpt-embeddings")
