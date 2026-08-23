import json

import pytest
from django.utils import timezone

from rsm_thrive.models import StudentTask, TaskOverride
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _post(client, body):
    return client.post("/api/thrive/tasks", data=json.dumps(body),
                       content_type="application/json")


def test_client_key_create_upsert_and_delete(client):
    me = make_student()
    client.force_login(me.user)
    body = {"title": "Print resume", "dueDate": "2026-09-01T12:00:00-07:00",
            "clientKey": "task-add-abc"}
    created = _post(client, body).json()
    assert created["id"] == "task-add-abc"

    # re-POST with the same key updates in place (setTaskDue re-sends the object)
    body["title"] = "Print resume tonight"
    updated = _post(client, body)
    assert updated.status_code == 201
    assert StudentTask.objects.count() == 1
    assert StudentTask.objects.get().title == "Print resume tonight"

    # overrides key on the client key; delete cascades them
    client.patch("/api/thrive/tasks/task-add-abc/override",
                 data=json.dumps({"done": True}), content_type="application/json")
    assert TaskOverride.objects.filter(task_key="task-add-abc").exists()
    assert client.delete("/api/thrive/tasks/task-add-abc").status_code == 204
    assert StudentTask.objects.count() == 0
    assert not TaskOverride.objects.filter(task_key="task-add-abc").exists()


def test_client_key_rejects_reserved_prefixes(client):
    me = make_student()
    client.force_login(me.user)
    for bad in ("asg:x", "shared:9", "stu:9"):
        resp = _post(client, {"title": "x", "dueDate": "2026-09-01T12:00:00-07:00",
                              "clientKey": bad})
        assert resp.status_code == 400


def test_source_view_excludes_student_tasks_and_overrides(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", title="Homework 1",
                     due=timezone.now() + timezone.timedelta(days=1))
    _post(client if client.force_login(me.user) is None else client,
          {"title": "Mine", "dueDate": "2026-09-01T12:00:00-07:00",
           "clientKey": "task-add-1"})
    client.patch("/api/thrive/tasks/asg:a1/override",
                 data=json.dumps({"title": "Renamed"}),
                 content_type="application/json")

    merged = client.get("/api/thrive/tasks").json()
    source = client.get("/api/thrive/tasks?view=source").json()
    assert any(t["id"] == "task-add-1" for t in merged)
    assert [t["id"] for t in source] == ["asg:a1"]
    assert source[0]["title"] == "Homework 1"  # no override applied
