import pytest
from django.db import IntegrityError

from rsm_thrive.testing import enroll, make_course, make_student

pytestmark = pytest.mark.django_db


def test_enrollment_unique_per_student_and_course():
    profile = make_student()
    course = make_course()
    enroll(profile, course)
    with pytest.raises(IntegrityError):
        enroll(profile, course)


def test_meetings_ordered_by_day_then_time():
    from rsm_thrive.testing import make_meeting
    course = make_course()
    make_meeting(course, day_of_week=3, start_time="09:00")
    make_meeting(course, day_of_week=1, start_time="14:00")
    make_meeting(course, day_of_week=1, start_time="09:00")
    got = [(m.day_of_week, m.start_time) for m in course.meetings.all()]
    assert got == [(1, "09:00"), (1, "14:00"), (3, "09:00")]
