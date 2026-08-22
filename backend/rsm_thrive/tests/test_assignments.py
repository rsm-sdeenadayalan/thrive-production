import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_student, set_assignment_status,
)

pytestmark = pytest.mark.django_db


def test_assignments_scoped_sorted_and_shaped(client):
    profile = make_student()
    mine = make_course(id="c1")
    other = make_course(id="c2")
    enroll(profile, mine)
    late = make_assignment(mine, id="a-late", due=timezone.now() + timezone.timedelta(days=9))
    soon = make_assignment(mine, id="a-soon", due=timezone.now() + timezone.timedelta(days=1))
    make_assignment(other, id="a-other")  # not enrolled: must not appear
    set_assignment_status(profile, soon, "graded", grade="A-")

    client.force_login(profile.user)
    body = client.get("/api/thrive/assignments").json()

    assert [a["id"] for a in body] == ["a-soon", "a-late"]  # due asc
    graded = body[0]
    assert graded["courseId"] == "c1"
    assert graded["status"] == "graded"
    assert graded["grade"] == "A-"
    assert graded["weight"] == 10
    assert graded["dueDate"].endswith("-07:00") or graded["dueDate"].endswith("-08:00")
    unstarted = body[1]
    assert unstarted["status"] == "not-started"  # no StudentAssignment row yet
    assert "grade" not in unstarted


def test_assignments_requires_login(client):
    assert client.get("/api/thrive/assignments").status_code == 401
