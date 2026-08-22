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


def test_course_without_syllabus_returns_empty_syllabus_id(client):
    profile = make_student()
    course = make_course(id="c1", code="MGTA 453")
    # Deliberately no make_syllabus(course) call here.
    enroll(profile, course)

    client.force_login(profile.user)
    resp = client.get("/api/thrive/courses")
    assert resp.status_code == 200
    [row] = resp.json()
    assert row["syllabusId"] == ""


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


def test_courses_constant_queries_with_multiple_enrollments(client, django_assert_num_queries):
    # Verify that next_assignment_for uses prefetch cache, not N+1 queries.
    # Query count must be constant regardless of course count:
    # 1 session, 1 auth_user, 1 enrollments (with select_related course/syllabus),
    # 1 meetings prefetch, 1 assignments prefetch = 5 total, independent of course count
    profile = make_student()

    # Create two courses with meetings and assignments
    course1 = make_course(id="c1", code="MGTA 451")
    course2 = make_course(id="c2", code="MGTA 452")

    make_meeting(course1, day_of_week=1, start_time="09:00", end_time="10:20")
    make_meeting(course2, day_of_week=2, start_time="14:00", end_time="15:20")

    make_syllabus(course1, id="syl-c1")
    make_syllabus(course2, id="syl-c2")

    make_assignment(course1, id="c1-past", title="Quiz 1",
                    due=timezone.now() - timezone.timedelta(days=1))
    make_assignment(course1, id="c1-next", title="Project 1",
                    due=timezone.now() + timezone.timedelta(days=3))

    make_assignment(course2, id="c2-past", title="Quiz 2",
                    due=timezone.now() - timezone.timedelta(days=1))
    make_assignment(course2, id="c2-next", title="Project 2",
                    due=timezone.now() + timezone.timedelta(days=3))

    enroll(profile, course1)
    enroll(profile, course2)

    client.force_login(profile.user)

    # Assert query count is constant (5); scales linearly only with auth framework, not courses
    with django_assert_num_queries(5):
        rows = client.get("/api/thrive/courses").json()

    # Verify both courses are returned with correct nextAssignment titles
    assert len(rows) == 2
    assert rows[0]["code"] == "MGTA 451"
    assert rows[0]["nextAssignment"]["title"] == "Project 1"
    assert rows[1]["code"] == "MGTA 452"
    assert rows[1]["nextAssignment"]["title"] == "Project 2"
