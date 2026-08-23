import re

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, parse_body
from rsm_thrive.models import (
    CalendarItemLabel, CalendarItemUrgent, CustomCalendarEvent, QuickListItem,
)

DAY_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


@api_login_required
@require_http_methods(["PUT"])
def item_label(request, item_key):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    label = body.get("label")
    if not isinstance(label, str):
        return json_error("bad_request", "label must be a string.", 400)
    trimmed = label.strip()
    if trimmed:
        CalendarItemLabel.objects.update_or_create(
            user=request.user, item_key=item_key, defaults={"label": trimmed})
    else:
        CalendarItemLabel.objects.filter(user=request.user, item_key=item_key).delete()
    return HttpResponse(status=204)


def _flag_views(model, key_field):
    """Factory for PUT/DELETE flag endpoints (e.g., urgent markers)."""
    @api_login_required
    @require_http_methods(["PUT", "DELETE"])
    def view(request, item_key):
        if request.method == "PUT":
            model.objects.get_or_create(user=request.user, **{key_field: item_key})
        else:
            model.objects.filter(user=request.user, **{key_field: item_key}).delete()
        return HttpResponse(status=204)
    return view


item_urgent = _flag_views(CalendarItemUrgent, "item_key")


@api_login_required
@require_http_methods(["PUT", "DELETE"])
def custom_event(request, key):
    if request.method == "DELETE":
        CustomCalendarEvent.objects.filter(user=request.user, key=key).delete()
        derived = f"custom-{key}"
        CalendarItemLabel.objects.filter(user=request.user, item_key=derived).delete()
        CalendarItemUrgent.objects.filter(user=request.user, item_key=derived).delete()
        return HttpResponse(status=204)

    # PUT method - validate and upsert
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)

    # Validate title
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return json_error("bad_request", "title must be a non-empty string.", 400)

    # Validate dayKey
    day_key = body.get("dayKey")
    if not isinstance(day_key, str) or not DAY_KEY_RE.match(day_key):
        return json_error("bad_request", "dayKey must match YYYY-MM-DD format.", 400)

    # Validate time (optional, but if present must match HH:MM)
    time = body.get("time") or ""  # Normalize None and missing to ""
    if time and (not isinstance(time, str) or not TIME_RE.match(time)):
        return json_error("bad_request", "time must match HH:MM format or be absent.", 400)

    # Validate urgent (optional bool, default False)
    urgent = body.get("urgent", False)
    if not isinstance(urgent, bool):
        return json_error("bad_request", "urgent must be a boolean.", 400)

    # Validate label (optional string, default "")
    label = body.get("label") or ""  # Normalize None and missing to ""
    if label and not isinstance(label, str):
        return json_error("bad_request", "label must be a string.", 400)

    # Validate createdAt (required int, not bool)
    created_at = body.get("createdAt")
    if isinstance(created_at, bool) or not isinstance(created_at, int):
        return json_error("bad_request", "createdAt must be an integer.", 400)

    CustomCalendarEvent.objects.update_or_create(
        user=request.user,
        key=key,
        defaults={
            "title": title.strip(),
            "day_key": day_key,
            "time": time,
            "label": label,
            "urgent": urgent,
            "created_at_ms": created_at,
        },
    )
    return HttpResponse(status=204)


@api_login_required
@require_http_methods(["PUT", "DELETE"])
def quick_item(request, key):
    if request.method == "DELETE":
        QuickListItem.objects.filter(user=request.user, key=key).delete()
        return HttpResponse(status=204)

    # PUT method - validate and upsert
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)

    # Validate title
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return json_error("bad_request", "title must be a non-empty string.", 400)

    # Validate done
    done = body.get("done")
    if not isinstance(done, bool):
        return json_error("bad_request", "done must be a boolean.", 400)

    # Validate createdAt (required int, not bool)
    created_at = body.get("createdAt")
    if isinstance(created_at, bool) or not isinstance(created_at, int):
        return json_error("bad_request", "createdAt must be an integer.", 400)

    # Validate optional fields (normalize None and missing to "")
    copied_from = body.get("copiedFrom") or ""
    if copied_from and not isinstance(copied_from, str):
        return json_error("bad_request", "copiedFrom must be a string.", 400)

    due_date = body.get("dueDate") or ""
    if due_date and not isinstance(due_date, str):
        return json_error("bad_request", "dueDate must be a string.", 400)

    note = body.get("note") or ""
    if note and not isinstance(note, str):
        return json_error("bad_request", "note must be a string.", 400)

    QuickListItem.objects.update_or_create(
        user=request.user,
        key=key,
        defaults={
            "title": title.strip(),
            "done": done,
            "created_at_ms": created_at,
            "copied_from": copied_from,
            "due_date": due_date,
            "note": note,
        },
    )
    return HttpResponse(status=204)
