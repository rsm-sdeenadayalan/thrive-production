"""Assemble the per-student task list: derive, overlay, sort."""
from rsm_thrive.models import (
    Assignment, Enrollment, SharedTask, StudentAssignment, StudentTask, TaskOverride,
)
from rsm_thrive.serialize import iso_instant

DONE_STATUSES = {"submitted", "graded"}


def _priority_for_weight(weight: int) -> str:
    if weight >= 25:
        return "high"
    if weight >= 10:
        return "medium"
    return "low"


def _base_tasks(user, include_student=True):
    course_ids = dict(
        Enrollment.objects.filter(user=user).values_list("course_id", "course__code")
    )
    done_by_asg = {
        sa.assignment_id: sa.status in DONE_STATUSES
        for sa in StudentAssignment.objects.filter(user=user)
    }
    tasks = []
    for a in Assignment.objects.filter(course_id__in=course_ids).select_related("course"):
        tasks.append({
            "id": f"asg:{a.id}",
            "title": a.title,
            "dueDate": iso_instant(a.due_date),
            "_due": a.due_date,
            "source": "class",
            "priority": _priority_for_weight(a.weight),
            "done": done_by_asg.get(a.id, False),
            "subtasks": [],
            "courseId": a.course_id,
            "courseCode": a.course.code,
        })
    for s in SharedTask.objects.filter(active=True).select_related("course"):
        row = {
            "id": f"shared:{s.pk}",
            "title": s.title,
            "dueDate": iso_instant(s.due_date),
            "_due": s.due_date,
            "source": s.source,
            "priority": s.priority,
            "done": False,
            "subtasks": [dict(st) for st in s.subtasks],
        }
        if s.course_id:
            row["courseId"] = s.course_id
            row["courseCode"] = s.course.code
        tasks.append(row)
    if include_student:
        for t in StudentTask.objects.filter(user=user):
            tasks.append({
                "id": t.client_key or f"stu:{t.pk}",
                "title": t.title,
                "dueDate": iso_instant(t.due_date),
                "_due": t.due_date,
                "source": t.source,
                "priority": t.priority,
                "done": False,
                "subtasks": [dict(st) for st in t.subtasks],
            })
    return tasks


def _apply_override(task: dict, ov: TaskOverride) -> None:
    if ov.done is not None:
        task["done"] = ov.done
    if ov.title is not None:
        task["title"] = ov.title
    if ov.priority is not None:
        task["priority"] = ov.priority
    if ov.due_date is not None:
        task["dueDate"] = iso_instant(ov.due_date)
        task["_due"] = ov.due_date
    if ov.sort_order is not None:
        task["_order"] = ov.sort_order
    if ov.subtask_done is not None:
        for st in task["subtasks"]:
            if st["id"] in ov.subtask_done:
                st["done"] = ov.subtask_done[st["id"]]


def assemble_source_tasks(user) -> list[dict]:
    """Assignment-derived + shared tasks only, no overrides — the mock-parity
    source view the API frontend merges client overrides onto."""
    tasks = _base_tasks(user, include_student=False)
    tasks.sort(key=lambda t: (t["done"], t["_due"], t["id"]))
    for task in tasks:
        task.pop("_due", None)
        task.pop("_order", None)
    return tasks


def assemble_tasks(user) -> list[dict]:
    tasks = _base_tasks(user)
    overrides = {o.task_key: o for o in TaskOverride.objects.filter(user=user)}
    for task in tasks:
        if task["id"] in overrides:
            _apply_override(task, overrides[task["id"]])
    tasks.sort(key=lambda t: (t["done"], t.get("_order", float("inf")), t["_due"], t["id"]))
    for task in tasks:
        task.pop("_due", None)
        task.pop("_order", None)
    return tasks
