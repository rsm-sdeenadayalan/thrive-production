"""Dev-only session login. On the server, UCSD LDAP replaces this (F5)."""
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import escape

from rsm_thrive.http import json_error


def _safe_next(next_url: str) -> str:
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    for origin in settings.THRIVE_FRONTEND_ORIGINS:
        if next_url == origin or next_url.startswith(origin + "/"):
            return next_url
    return "/"


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
