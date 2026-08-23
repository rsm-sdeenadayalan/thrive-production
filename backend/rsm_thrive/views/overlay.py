from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import (
    CalendarItemLabel, CalendarItemUrgent, CalendarPrefs, CustomCalendarEvent,
    EventJoin, IgnoredEvent, QuickListItem, StudentTask, TaskNote, TaskOverride,
)
from rsm_thrive.serialize import iso_instant


def _stores_payload(user: User) -> dict:
    """Build the stores map mirroring localStorage shapes."""
    stores = {
        "thrive:task-done": {},
        "thrive:task-titles": {},
        "thrive:task-priority": {},
        "thrive:task-due": {},
        "thrive:task-order": {},
        "thrive:task-added": {},
        "thrive:ignored-events": {},
        "thrive:event-joins": {},
        "thrive:item-labels": {},
        "thrive:item-urgent": {},
        "thrive:custom-events": {},
        "thrive:quicklist": {},
        "thrive:task-notes": {},
        "thrive:calendar-prefs": {},
    }

    # TaskOverride facets - only include non-null facets
    for override in TaskOverride.objects.filter(user=user):
        if override.done is not None:
            stores["thrive:task-done"][override.task_key] = override.done
        if override.title is not None:
            stores["thrive:task-titles"][override.task_key] = override.title
        if override.priority is not None:
            stores["thrive:task-priority"][override.task_key] = override.priority
        if override.due_date is not None:
            stores["thrive:task-due"][override.task_key] = iso_instant(override.due_date)
        if override.sort_order is not None:
            stores["thrive:task-order"][override.task_key] = override.sort_order

    # StudentTask - added tasks
    for task in StudentTask.objects.filter(user=user):
        task_id = task.client_key or f"stu:{task.pk}"
        stores["thrive:task-added"][task_id] = {
            "id": task_id,
            "title": task.title,
            "dueDate": iso_instant(task.due_date),
            "source": task.source,
            "priority": task.priority,
            "done": False,
            "subtasks": task.subtasks,
        }

    # IgnoredEvent and EventJoin
    for evt in IgnoredEvent.objects.filter(user=user):
        stores["thrive:ignored-events"][evt.event_id] = True
    for evt in EventJoin.objects.filter(user=user):
        stores["thrive:event-joins"][evt.event_id] = True

    # CalendarItemLabel and CalendarItemUrgent
    for label in CalendarItemLabel.objects.filter(user=user):
        stores["thrive:item-labels"][label.item_key] = label.label
    for urgent in CalendarItemUrgent.objects.filter(user=user):
        stores["thrive:item-urgent"][urgent.item_key] = True

    # CustomCalendarEvent - omit time/label when blank, omit urgent when False
    for event in CustomCalendarEvent.objects.filter(user=user):
        event_obj = {
            "id": event.key,
            "title": event.title,
            "dayKey": event.day_key,
            "createdAt": event.created_at_ms,
        }
        if event.time:
            event_obj["time"] = event.time
        if event.label:
            event_obj["label"] = event.label
        if event.urgent:
            event_obj["urgent"] = event.urgent
        stores["thrive:custom-events"][event.key] = event_obj

    # QuickListItem - omit blank optionals
    for item in QuickListItem.objects.filter(user=user):
        item_obj = {
            "id": item.key,
            "title": item.title,
            "done": item.done,
            "createdAt": item.created_at_ms,
        }
        if item.copied_from:
            item_obj["copiedFrom"] = item.copied_from
        if item.due_date:
            item_obj["dueDate"] = item.due_date
        if item.note:
            item_obj["note"] = item.note
        stores["thrive:quicklist"][item.key] = item_obj

    # TaskNote
    for note in TaskNote.objects.filter(user=user):
        stores["thrive:task-notes"][note.task_key] = note.note

    # CalendarPrefs - wrap as {"value": prefs.prefs} when present else {}
    prefs = CalendarPrefs.objects.filter(user=user).first()
    if prefs:
        stores["thrive:calendar-prefs"] = {"value": prefs.prefs}
    else:
        stores["thrive:calendar-prefs"] = {}

    return stores


@api_login_required
@require_http_methods(["GET"])
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
        "stores": _stores_payload(request.user),
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
    CalendarPrefs.objects.update_or_create(user=request.user, defaults={"prefs": body})
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
