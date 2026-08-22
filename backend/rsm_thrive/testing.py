"""Factories shared by tests and the seed_demo command."""
import datetime as dt
import itertools

from django.contrib.auth import get_user_model
from django.utils import timezone

from rsm_thrive.models import (
    Assignment, Course, CourseMeeting, Enrollment, Event, StudentAssignment, StudentProfile, Syllabus,
)


def make_student(username="ada", **overrides) -> StudentProfile:
    user = get_user_model().objects.create_user(username=username)
    fields = {
        "display_name": "Ada Lovelace",
        "program_start": dt.date(2026, 8, 1),
    }
    fields.update(overrides)
    return StudentProfile.objects.create(user=user, **fields)


_counter = itertools.count(1)


def make_course(id=None, **overrides) -> Course:
    n = next(_counter)
    fields = {
        "id": id or f"course-{n}",
        "code": f"MGTA {450 + n}",
        "title": "Business Analytics",
        "instructor": "V. Nijs",
        "term": "Fall 2026",
        "units": 4,
    }
    fields.update(overrides)
    return Course.objects.create(**fields)


def make_meeting(course, **overrides) -> CourseMeeting:
    fields = {"day_of_week": 1, "start_time": "09:00", "end_time": "10:20",
              "location": "Rady 2S111"}
    fields.update(overrides)
    return CourseMeeting.objects.create(course=course, **fields)


def make_syllabus(course, **overrides) -> Syllabus:
    fields = {
        "id": f"syl-{course.id}",
        "description": "What the course covers.",
        "grade_breakdown": [{"label": "Final project", "weight": 40}],
        "policies": ["No late work"],
        "office_hours": "Tue 2-4pm",
        "last_updated": timezone.localdate(),
    }
    fields.update(overrides)
    return Syllabus.objects.create(course=course, **fields)


def make_assignment(course, id=None, due=None, **overrides) -> Assignment:
    n = next(_counter)
    fields = {
        "id": id or f"asg-{n}",
        "title": f"Homework {n}",
        "due_date": due or (timezone.now() + timezone.timedelta(days=7)),
        "weight": 10,
    }
    fields.update(overrides)
    return Assignment.objects.create(course=course, **fields)


def enroll(profile, course, **overrides) -> Enrollment:
    return Enrollment.objects.create(user=profile.user, course=course, **overrides)


def set_assignment_status(profile, assignment, status, grade="") -> StudentAssignment:
    return StudentAssignment.objects.create(
        user=profile.user, assignment=assignment, status=status, grade=grade
    )


def make_event(id=None, start=None, **overrides) -> Event:
    n = next(_counter)
    fields = {
        "id": id or f"evt-{n}",
        "title": f"Event {n}",
        "start": start or (timezone.now() + timezone.timedelta(days=2)),
        "location": "Rady Courtyard",
    }
    fields.update(overrides)
    return Event.objects.create(**fields)
