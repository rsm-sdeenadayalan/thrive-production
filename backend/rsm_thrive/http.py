import functools
import json

from django.http import JsonResponse


class BadRequest(Exception):
    pass


def json_ok(payload, status=200):
    return JsonResponse(payload, status=status, safe=False)


def json_error(code: str, message: str, status: int):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def api_login_required(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error("unauthenticated", "Log in to use THRIVE.", 401)
        return view(request, *args, **kwargs)
    return wrapper


def profile_required(view):
    """Use under api_login_required: guarantees request.thrive_profile."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        from rsm_thrive.models import StudentProfile
        try:
            request.thrive_profile = request.user.thrive_profile
        except StudentProfile.DoesNotExist:
            return json_error("no_profile", "No student profile for this account.", 403)
        return view(request, *args, **kwargs)
    return wrapper


def parse_body(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise BadRequest("Body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise BadRequest("Body must be a JSON object.")
    return data
