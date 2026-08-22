import json

import pytest
from django.utils import timezone

from rsm_thrive.models import TaskOverride
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _setup(client):
    profile = make_student()
    course = make_course(id="c1")
    enroll(profile, course)
    make_assignment(course, id="a1", title="Homework 1",
                     due=timezone.now() + timezone.timedelta(days=1))
    client.force_login(profile.user)
    return profile


def _patch(client, task_id, body):
    return client.patch(
        f"/api/thrive/tasks/{task_id}/override",
        data=json.dumps(body), content_type="application/json",
    )


def test_override_set_and_clear(client):
    profile = _setup(client)
    resp = _patch(client, "asg:a1", {"done": True, "title": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["done"] is True and resp.json()["title"] == "Renamed"

    resp = _patch(client, "asg:a1", {"title": None})  # clear one facet
    assert resp.json()["title"] == "Homework 1"        # back to source
    assert resp.json()["done"] is True                 # other facet untouched

    _patch(client, "asg:a1", {"done": None})           # last facet cleared
    assert TaskOverride.objects.count() == 0           # row garbage-collected


def test_override_unknown_task_404(client):
    _setup(client)
    assert _patch(client, "asg:nope", {"done": True}).status_code == 404


def test_create_and_delete_student_task(client):
    _setup(client)
    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"title": "Print resume",
                         "dueDate": "2026-09-01T12:00:00-07:00"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    assert task_id.startswith("stu:")

    assert client.delete(f"/api/thrive/tasks/{task_id}").status_code == 204
    assert client.delete("/api/thrive/tasks/asg:a1").status_code == 400


def test_override_unknown_facet_leaves_no_row(client):
    _setup(client)
    resp = _patch(client, "asg:a1", {"bogus": True})
    assert resp.status_code == 400
    assert TaskOverride.objects.count() == 0


def test_override_naive_due_date_400(client):
    _setup(client)
    resp = _patch(client, "asg:a1", {"dueDate": "2026-09-01T12:00:00"})
    assert resp.status_code == 400
    assert TaskOverride.objects.count() == 0


def test_create_task_missing_title_400(client):
    _setup(client)
    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"title": "  ", "dueDate": "2026-09-01T12:00:00-07:00"}),
        content_type="application/json",
    )
    assert resp.status_code == 400

    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"dueDate": "2026-09-01T12:00:00-07:00"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_delete_nonexistent_student_task_404(client):
    _setup(client)
    assert client.delete("/api/thrive/tasks/stu:99999").status_code == 404


def test_tasks_put_method_not_allowed(client):
    _setup(client)
    assert client.put("/api/thrive/tasks").status_code == 405


def test_override_bad_order_value_400_and_tasks_still_readable(client):
    _setup(client)
    resp = _patch(client, "asg:a1", {"order": "top"})
    assert resp.status_code == 400
    assert TaskOverride.objects.count() == 0

    # The bug this guards against: a bad sort_order write used to corrupt
    # assemble_tasks for every subsequent call (str vs float comparison).
    assert client.get("/api/thrive/tasks").status_code == 200


def test_override_bad_due_date_type_400(client):
    _setup(client)
    resp = _patch(client, "asg:a1", {"dueDate": 123})
    assert resp.status_code == 400
    assert TaskOverride.objects.count() == 0


def test_override_bad_subtask_done_value_400(client):
    _setup(client)
    resp = _patch(client, "asg:a1", {"subtaskDone": {"s1": "yes"}})
    assert resp.status_code == 400
    assert TaskOverride.objects.count() == 0


def test_create_task_explicit_null_priority_400(client):
    _setup(client)
    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"title": "x", "dueDate": "2026-09-01T12:00:00-07:00",
                         "priority": None}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_create_task_invalid_priority_400(client):
    _setup(client)
    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"title": "x", "dueDate": "2026-09-01T12:00:00-07:00",
                         "priority": "urgent"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
