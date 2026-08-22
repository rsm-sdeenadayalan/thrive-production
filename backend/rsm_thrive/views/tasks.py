import datetime as dt

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import StudentTask, TaskOverride
from rsm_thrive.services.tasks import assemble_tasks


@api_login_required
def tasks(request):
    return json_ok(assemble_tasks(request.user))


def tasks_dispatch(request):
    if request.method == "POST":
        return create_task(request)
    return tasks(request)


OVERRIDE_FACETS = {
    "done": "done", "title": "title", "priority": "priority",
    "dueDate": "due_date", "order": "sort_order", "subtaskDone": "subtask_done",
}


def _parse_instant(value: str) -> dt.datetime:
    parsed = parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        raise BadRequest("dueDate must be an ISO-8601 instant with offset.")
    return parsed


@api_login_required
@require_http_methods(["PATCH"])
def override(request, task_id):
    current = {t["id"]: t for t in assemble_tasks(request.user)}
    if task_id not in current:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    try:
        body = parse_body(request)
        row, _ = TaskOverride.objects.get_or_create(user=request.user, task_key=task_id)
        for key, value in body.items():
            if key not in OVERRIDE_FACETS:
                raise BadRequest(f"Unknown facet {key}.")
            if key == "dueDate" and value is not None:
                value = _parse_instant(value)
            setattr(row, OVERRIDE_FACETS[key], value)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
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
        title = body.get("title") or ""
        if not title.strip():
            raise BadRequest("title is required.")
        due = _parse_instant(body.get("dueDate") or "")
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    row = StudentTask.objects.create(
        user=request.user, title=title.strip(), due_date=due,
        priority=body.get("priority", "medium"), source=body.get("source", "admin"),
    )
    merged = {t["id"]: t for t in assemble_tasks(request.user)}
    return json_ok(merged[f"stu:{row.pk}"], status=201)


@api_login_required
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    if not task_id.startswith("stu:"):
        return json_error("not_deletable", "Only self-added tasks can be deleted.", 400)
    deleted, _ = StudentTask.objects.filter(
        user=request.user, pk=task_id.removeprefix("stu:")
    ).delete()
    if not deleted:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    TaskOverride.objects.filter(user=request.user, task_key=task_id).delete()
    return HttpResponse(status=204)
