import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_meeting, make_student, make_syllabus,
)

pytestmark = pytest.mark.django_db


def test_courses_shape_and_next_assignment(client):
    profile = make_student()
    course = make_course(id="c1", code="MGTA 453")
    make_meeting(course, day_of_week=2, start_time="09:00", end_time="10:20",
                 location="Rady 2S111")
    make_syllabus(course, id="syl-c1")
    make_assignment(course, id="past", due=timezone.now() - timezone.timedelta(days=3))
    make_assignment(course, id="next", title="Case write-up",
                    due=timezone.now() + timezone.timedelta(days=2))
    make_assignment(course, id="later", due=timezone.now() + timezone.timedelta(days=20))
    enroll(profile, course, progress=40, standing="watch", nudge="Submit the case",
           current_grade="B+")

    client.force_login(profile.user)
    [row] = client.get("/api/thrive/courses").json()

    assert row["id"] == "c1"
    assert row["code"] == "MGTA 453"
    assert row["schedule"] == [{"dayOfWeek": 2, "startTime": "09:00",
                                "endTime": "10:20", "location": "Rady 2S111"}]
    assert row["progress"] == 40
    assert row["standing"] == "watch"
    assert row["nextAssignment"]["title"] == "Case write-up"
    assert row["nudge"] == "Submit the case"
    assert row["currentGrade"] == "B+"
    assert row["syllabusId"] == "syl-c1"
    assert row["units"] == 4


def test_syllabi_scoped_to_enrollments(client):
    profile = make_student()
    mine = make_course(id="c1")
    other = make_course(id="c2")
    make_syllabus(mine, id="syl-1")
    make_syllabus(other, id="syl-2")
    enroll(profile, mine)

    client.force_login(profile.user)
    body = client.get("/api/thrive/syllabi").json()
    assert [s["id"] for s in body] == ["syl-1"]
    assert body[0]["courseId"] == "c1"
    assert body[0]["gradeBreakdown"] == [{"label": "Final project", "weight": 40}]
    assert "sourceUrl" not in body[0]
