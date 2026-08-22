import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_shared_task, make_student,
    make_student_task, set_assignment_status, set_override,
)

pytestmark = pytest.mark.django_db
DAY = timezone.timedelta(days=1)


def _setup(client):
    profile = make_student()
    course = make_course(id="c1", code="MGTA 453")
    enroll(profile, course)
    client.force_login(profile.user)
    return profile, course


def test_assignment_derived_task_shape(client):
    profile, course = _setup(client)
    asg = make_assignment(course, id="a1", title="Case study",
                          due=timezone.now() + DAY, weight=30)
    [task] = client.get("/api/thrive/tasks").json()
    assert task["id"] == "asg:a1"
    assert task["title"] == "Case study"
    assert task["source"] == "class"
    assert task["priority"] == "high"        # weight 30 >= 25
    assert task["done"] is False
    assert task["subtasks"] == []
    assert task["courseId"] == "c1"
    assert task["courseCode"] == "MGTA 453"


def test_sort_done_last_then_due(client):
    profile, course = _setup(client)
    a = make_assignment(course, id="a1", due=timezone.now() + 1 * DAY)
    make_assignment(course, id="a2", due=timezone.now() + 2 * DAY)
    make_student_task(profile, title="Print resume", due=timezone.now() + 3 * DAY)
    set_assignment_status(profile, a, "submitted")  # a1 becomes done -> sinks
    ids = [t["id"] for t in client.get("/api/thrive/tasks").json()]
    assert ids[:2] == ["asg:a2", ids[1]] and ids[-1] == "asg:a1"


def test_override_can_untick_a_shipped_done_task(client):
    profile, course = _setup(client)
    a = make_assignment(course, id="a1", due=timezone.now() + DAY)
    set_assignment_status(profile, a, "graded")           # ships done
    set_override(profile, "asg:a1", done=False)           # student unticks
    [task] = client.get("/api/thrive/tasks").json()
    assert task["done"] is False                          # override wins


def test_override_title_and_priority_absent_means_source(client):
    profile, course = _setup(client)
    make_assignment(course, id="a1", title="Original", due=timezone.now() + DAY)
    set_override(profile, "asg:a1", title="Renamed")
    [task] = client.get("/api/thrive/tasks").json()
    assert task["title"] == "Renamed"
    assert task["priority"] == "medium"  # untouched facet: source value (weight 10)
