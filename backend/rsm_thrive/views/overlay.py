from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import CalendarPrefs, EventJoin, IgnoredEvent, TaskNote


@api_login_required
def overlay(request):
    prefs = CalendarPrefs.objects.filter(user=request.user).first()
    return json_ok({
        "ignoredEventIds": sorted(
            IgnoredEvent.objects.filter(user=request.user)
            .values_list("event_id", flat=True)
        ),
        "joinedEventIds": sorted(
            EventJoin.objects.filter(user=request.user)
            .values_list("event_id", flat=True)
        ),
        "calendarPrefs": prefs.prefs if prefs else {},
        "taskNotes": {
            n.task_key: n.note for n in TaskNote.objects.filter(user=request.user)
        },
    })


def _flag_views(model):
    @api_login_required
    @require_http_methods(["PUT", "DELETE"])
    def view(request, event_id):
        if request.method == "PUT":
            model.objects.get_or_create(user=request.user, event_id=event_id)
        else:
            model.objects.filter(user=request.user, event_id=event_id).delete()
        return HttpResponse(status=204)
    return view


ignore_event = _flag_views(IgnoredEvent)
join_event = _flag_views(EventJoin)


@api_login_required
@require_http_methods(["PUT"])
def calendar_prefs(request):
    if len(request.body) > 8192:
        return json_error("too_large", "Prefs object too large.", 400)
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    row, _ = CalendarPrefs.objects.get_or_create(user=request.user)
    row.prefs = body
    row.save()
    return HttpResponse(status=204)


@api_login_required
@require_http_methods(["PUT"])
def task_note(request, task_id):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    note = (body.get("note") or "").strip()
    if note:
        TaskNote.objects.update_or_create(
            user=request.user, task_key=task_id, defaults={"note": note}
        )
    else:
        TaskNote.objects.filter(user=request.user, task_key=task_id).delete()
    return HttpResponse(status=204)
