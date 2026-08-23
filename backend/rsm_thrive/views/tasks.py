import datetime as dt

from django.db.models import Q
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import StudentTask, TaskOverride
from rsm_thrive.services.tasks import assemble_source_tasks, assemble_tasks


@api_login_required
def tasks(request):
    if request.GET.get("view") == "source":
        return json_ok(assemble_source_tasks(request.user))
    return json_ok(assemble_tasks(request.user))


def tasks_dispatch(request):
    if request.method == "POST":
        return create_task(request)
    if request.method == "GET":
        return tasks(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)


OVERRIDE_FACETS = {
    "done": "done", "title": "title", "priority": "priority",
    "dueDate": "due_date", "order": "sort_order", "subtaskDone": "subtask_done",
}

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_TASK_SOURCES = {"class", "career", "admin", "event"}


def _parse_instant(value) -> dt.datetime:
    if not isinstance(value, str):
        raise BadRequest("dueDate must be an ISO-8601 instant with offset.")
    parsed = parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        raise BadRequest("dueDate must be an ISO-8601 instant with offset.")
    return parsed


def _validate_title(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BadRequest("title must be a non-empty string.")
    return value


def _validate_override_value(key: str, value):
    """Validate a non-null override facet value. Callers only invoke this
    for values that are not None (None means "clear the facet")."""
    if key == "done":
        if not isinstance(value, bool):
            raise BadRequest("done must be a boolean.")
    elif key == "title":
        _validate_title(value)
    elif key == "priority":
        if not isinstance(value, str) or value not in VALID_PRIORITIES:
            raise BadRequest(f"priority must be one of {sorted(VALID_PRIORITIES)}.")
    elif key == "order":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BadRequest("order must be an integer.")
    elif key == "subtaskDone":
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, bool) for k, v in value.items()
        ):
            raise BadRequest("subtaskDone must be an object of string keys to booleans.")


@api_login_required
@require_http_methods(["PATCH"])
def override(request, task_id):
    current = {t["id"]: t for t in assemble_tasks(request.user)}
    if task_id not in current:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    try:
        body = parse_body(request)
        updates = {}
        for key, value in body.items():
            if key not in OVERRIDE_FACETS:
                raise BadRequest(f"Unknown facet {key}.")
            if value is not None:
                if key == "dueDate":
                    value = _parse_instant(value)
                else:
                    _validate_override_value(key, value)
            updates[OVERRIDE_FACETS[key]] = value
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    row, _ = TaskOverride.objects.get_or_create(user=request.user, task_key=task_id)
    for field, value in updates.items():
        setattr(row, field, value)
    if all(getattr(row, f) is None for f in OVERRIDE_FACETS.values()):
        row.delete()
    else:
        row.save()
    merged = {t["id"]: t for t in assemble_tasks(request.user)}
    return json_ok(merged[task_id])


@api_login_required
@require_http_methods(["POST"])
def create_task(request):
    try:
        body = parse_body(request)
        title = _validate_title(body.get("title") or "")
        due = _parse_instant(body.get("dueDate") or "")
        priority = body.get("priority", "medium")
        if not isinstance(priority, str) or priority not in VALID_PRIORITIES:
            raise BadRequest(f"priority must be one of {sorted(VALID_PRIORITIES)}.")
        source = body.get("source", "admin")
        if not isinstance(source, str) or source not in VALID_TASK_SOURCES:
            raise BadRequest(f"source must be one of {sorted(VALID_TASK_SOURCES)}.")
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    client_key = body.get("clientKey")
    if client_key is not None:
        if (not isinstance(client_key, str) or not client_key.strip()
                or len(client_key) > 64
                or client_key.startswith(("asg:", "shared:", "stu:"))):
            return json_error("bad_request", "clientKey is invalid.", 400)
        row, _created = StudentTask.objects.update_or_create(
            user=request.user, client_key=client_key,
            defaults={"title": title.strip(), "due_date": due,
                      "priority": priority, "source": source},
        )
    else:
        row = StudentTask.objects.create(
            user=request.user, title=title.strip(), due_date=due,
            priority=priority, source=source,
        )
    merged = {t["id"]: t for t in assemble_tasks(request.user)}
    return json_ok(merged[row.client_key or f"stu:{row.pk}"], status=201)


@api_login_required
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    if task_id.startswith(("asg:", "shared:")):
        return json_error("not_deletable", "Only self-added tasks can be deleted.", 400)
    if task_id.startswith("stu:"):
        lookup = Q(pk=task_id.removeprefix("stu:"))
    else:
        lookup = Q(client_key=task_id)
    deleted, _ = StudentTask.objects.filter(user=request.user).filter(lookup).delete()
    if not deleted:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    TaskOverride.objects.filter(user=request.user, task_key=task_id).delete()
    return HttpResponse(status=204)


@api_login_required
@require_http_methods(["PATCH"])
def bulk_order(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    orders = body.get("orders")
    if not isinstance(orders, dict):
        return json_error("bad_request", "orders must be an object.", 400)
    for value in orders.values():
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            return json_error("bad_request", "order values must be integers or null.", 400)
    known = {t["id"] for t in assemble_tasks(request.user)}
    for key, value in orders.items():
        if key not in known:
            continue
        if value is None:
            row = TaskOverride.objects.filter(user=request.user, task_key=key).first()
            if row:
                row.sort_order = None
                if all(getattr(row, f) is None for f in OVERRIDE_FACETS.values()):
                    row.delete()
                else:
                    row.save(update_fields=["sort_order"])
        else:
            row, _ = TaskOverride.objects.get_or_create(user=request.user, task_key=key)
            row.sort_order = value
            row.save(update_fields=["sort_order"])
    return HttpResponse(status=204)
