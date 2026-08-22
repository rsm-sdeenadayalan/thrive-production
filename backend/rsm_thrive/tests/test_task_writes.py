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
