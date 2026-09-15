"""Session login views for THRIVE."""
import datetime as dt
import logging

import ldap3
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import escape
from ldap3.utils.conv import escape_filter_chars

from rsm_thrive.http import json_error

logger = logging.getLogger(__name__)


class UCSDLDAPBackend(ModelBackend):
    """Authenticate UCSD users against Active Directory and maintain Django users."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        username = _normalize_username(username)
        if not _is_allowed_username(username):
            logger.warning("LDAP login denied by THRIVE allowlist: %s", username)
            return None

        try:
            bind_password = self._bind_password()
            if not bind_password:
                logger.error("LDAP service account password is not configured")
                return None

            server = ldap3.Server(settings.LDAP_AUTH_URL, get_info=ldap3.ALL)
            service_conn = ldap3.Connection(
                server,
                user=settings.LDAP_AUTH_CONNECTION_USERNAME,
                password=bind_password,
                auto_bind=True,
            )
            service_conn.search(
                search_base=settings.LDAP_AUTH_SEARCH_BASE,
                search_filter=(
                    f"(&(sAMAccountName={escape_filter_chars(username)})"
                    f"(objectClass={escape_filter_chars(settings.LDAP_AUTH_OBJECT_CLASS)}))"
                ),
                attributes=[
                    "sAMAccountName",
                    "mail",
                    "givenName",
                    "sn",
                    "distinguishedName",
                ],
            )
            if not service_conn.entries:
                service_conn.unbind()
                logger.warning("LDAP user not found: %s", username)
                return None

            entry = service_conn.entries[0]
            email = _entry_value(entry, "mail") or f"{username}@ucsd.edu"
            first_name = _entry_value(entry, "givenName")
            last_name = _entry_value(entry, "sn")
            service_conn.unbind()

            user_conn = ldap3.Connection(
                server,
                user=f"{username}@{settings.LDAP_AUTH_ACTIVE_DIRECTORY_DOMAIN}",
                password=password,
                auto_bind=True,
            )
            user_conn.unbind()

            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )
            changed = created
            for field, value in {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            }.items():
                if value and getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if created:
                user.set_unusable_password()
            if changed:
                user.save()
            return user
        except ldap3.core.exceptions.LDAPBindError:
            logger.warning("LDAP bind failed for %s", username)
            return None
        except ldap3.core.exceptions.LDAPException as exc:
            logger.error("LDAP error for %s: %s", username, exc)
            return None

    def _bind_password(self) -> str:
        if settings.LDAP_AUTH_CONNECTION_PASSWORD:
            return settings.LDAP_AUTH_CONNECTION_PASSWORD
        password_file = getattr(settings, "LDAP_AUTH_CONNECTION_PASSWORD_FILE", "")
        if not password_file:
            return ""
        try:
            with open(password_file, encoding="utf-8") as file:
                return file.read().strip()
        except OSError as exc:
            logger.error("Could not read LDAP bind password file: %s", exc)
            return ""


class ThriveAllowlistMiddleware:
    """Log out already-authenticated users who are no longer allowlisted."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            getattr(settings, "THRIVE_REQUIRE_ALLOWLIST", False)
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not _is_allowed_username(request.user.username)
        ):
            logger.warning(
                "Logged out non-allowlisted THRIVE user: %s",
                request.user.username,
            )
            logout(request)
        return self.get_response(request)


def _normalize_username(username: str) -> str:
    username = (username or "").strip().lower()
    if username.endswith("@ucsd.edu"):
        username = username[:-9]
    return username


def _allowed_usernames() -> set[str]:
    allowed = {
        _normalize_username(username)
        for username in getattr(settings, "THRIVE_ALLOWED_USERS", [])
        if _normalize_username(username)
    }
    allowed_file = getattr(settings, "THRIVE_ALLOWED_USERS_FILE", "")
    if allowed_file:
        try:
            with open(allowed_file, encoding="utf-8") as file:
                for raw_line in file:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    for part in line.replace(",", " ").split():
                        if part.startswith("#"):
                            break
                        username = _normalize_username(part)
                        if username:
                            allowed.add(username)
        except OSError as exc:
            logger.error("Could not read THRIVE allowlist file %s: %s", allowed_file, exc)
    return allowed


def _is_allowed_username(username: str) -> bool:
    allowed = _allowed_usernames()
    if allowed:
        return _normalize_username(username) in allowed
    if getattr(settings, "THRIVE_REQUIRE_ALLOWLIST", False):
        logger.error("THRIVE allowlist is required but empty; refusing login")
        return False
    return True


def _safe_next(next_url: str, fallback: str = "/") -> str:
    next_url = next_url.replace("\\", "/")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    for origin in settings.THRIVE_FRONTEND_ORIGINS:
        if next_url == origin or next_url.startswith(origin + "/"):
            return next_url
    return fallback


def _default_next(request=None) -> str:
    origins = getattr(settings, "THRIVE_FRONTEND_ORIGINS", [])
    base_path = getattr(settings, "THRIVE_FRONTEND_BASE_PATH", "")
    path = f"{base_path}/" if base_path else "/"
    if request is not None:
        current_origin = f"{request.scheme}://{request.get_host()}"
        if current_origin in origins:
            return current_origin + path
    return origins[0] + path if origins else path


def _entry_value(entry, field: str) -> str:
    value = getattr(entry, field, None)
    return value.value if value and value.value else ""


def _display_name(user) -> str:
    return user.get_full_name() or user.email.split("@")[0] or user.username


def _ensure_profile(user):
    if not settings.THRIVE_AUTO_CREATE_PROFILE:
        return
    from rsm_thrive.models import StudentProfile

    if StudentProfile.objects.filter(user=user).exists():
        return
    StudentProfile.objects.create(
        user=user,
        display_name=_display_name(user),
        program=settings.THRIVE_DEFAULT_PROFILE_PROGRAM,
        track=settings.THRIVE_DEFAULT_PROFILE_TRACK,
        current_term=settings.THRIVE_DEFAULT_PROFILE_CURRENT_TERM,
        program_start=dt.date.fromisoformat(settings.THRIVE_DEFAULT_PROFILE_PROGRAM_START),
        consent_calendar_read=False,
        consent_lms_read=False,
        consent_career_recommendations=False,
        consent_advisor_sharing=False,
    )


def login_view(request):
    default_next = _default_next(request)
    next_url = request.POST.get("next") or request.GET.get("next") or default_next
    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", ""),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            _ensure_profile(user)
            login(request, user)
            return HttpResponseRedirect(_safe_next(next_url, default_next))
        error = "<p class='error'>Wrong username or password.</p>"
    token = get_token(request)
    html = (
        "<!doctype html><meta charset='utf-8'><title>THRIVE sign in</title>"
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:3rem;max-width:28rem}"
        "label,input{display:block;width:100%}input{box-sizing:border-box;margin:.35rem 0 1rem;padding:.65rem}"
        "button{padding:.65rem 1rem}.error{color:#b42318}"
        "</style>"
        "<h1>THRIVE sign in</h1>"
        "<p>Use the first part of your @ucsd.edu email and your AD/email password.</p>"
        + error +
        "<form method='post'>"
        f"<input type='hidden' name='csrfmiddlewaretoken' value='{token}'>"
        f"<input type='hidden' name='next' value='{escape(next_url)}'>"
        "<label>UCSD username <input name='username' autocomplete='username' autofocus></label>"
        "<label>Password <input type='password' name='password' autocomplete='current-password'></label>"
        "<button>Sign in</button></form>"
    )
    return HttpResponse(html)


def dev_login(request):
    if not settings.THRIVE_DEV_LOGIN_ENABLED:
        return json_error("not_found", "No such page.", 404)
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", ""),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            _ensure_profile(user)
            login(request, user)
            return HttpResponseRedirect(_safe_next(next_url))
        error = "<p>Wrong username or password.</p>"
    token = get_token(request)
    html = (
        "<!doctype html><meta charset='utf-8'><title>THRIVE dev login</title>"
        "<h1>THRIVE dev login</h1>" + error +
        "<form method='post'>"
        f"<input type='hidden' name='csrfmiddlewaretoken' value='{token}'>"
        f"<input type='hidden' name='next' value='{escape(next_url)}'>"
        "<p><label>Username <input name='username' autofocus></label></p>"
        "<p><label>Password <input type='password' name='password'></label></p>"
        "<p><button>Sign in</button></p></form>"
    )
    return HttpResponse(html)
