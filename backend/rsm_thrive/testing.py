"""Factories shared by tests and the seed_demo command."""
import datetime as dt
import itertools

from django.contrib.auth import get_user_model
from django.utils import timezone

from rsm_thrive.models import (
    Advisor, AppointmentSlot, Assignment, Course, CourseMeeting, CourseRequest,
    DegreeGap, DegreeRequirement, Enrollment, Event, ProgramPhaseRow,
    ResumeCourseHighlight, ResourceLink, SharedTask, Skill, StudentAssignment,
    StudentProfile, StudentTask, Syllabus, TaskOverride,
)


def make_student(username="ada", **overrides) -> StudentProfile:
    user = get_user_model().objects.create_user(username=username, email=f"{username}@ucsd.edu")
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


def make_resource(id=None, **overrides) -> ResourceLink:
    n = next(_counter)
    fields = {
        "id": id or f"res-{n}",
        "title": f"Resource {n}",
        "description": "What this is for.",
        "url": "https://rady.ucsd.edu/",
        "category": "academic",
    }
    fields.update(overrides)
    return ResourceLink.objects.create(**fields)


def make_shared_task(**overrides) -> SharedTask:
    n = next(_counter)
    fields = {"title": f"Shared task {n}",
              "due_date": timezone.now() + timezone.timedelta(days=4)}
    fields.update(overrides)
    return SharedTask.objects.create(**fields)


def make_student_task(profile, due=None, **overrides) -> StudentTask:
    n = next(_counter)
    fields = {"title": f"My task {n}",
              "due_date": due or (timezone.now() + timezone.timedelta(days=4))}
    if "due" in overrides:
        fields["due_date"] = overrides.pop("due")
    fields.update(overrides)
    return StudentTask.objects.create(user=profile.user, **fields)


def set_override(profile, task_key, **facets) -> TaskOverride:
    field_map = {"dueDate": "due_date", "order": "sort_order",
                 "subtaskDone": "subtask_done"}
    row, _ = TaskOverride.objects.get_or_create(user=profile.user, task_key=task_key)
    for key, value in facets.items():
        setattr(row, field_map.get(key, key), value)
    row.save()
    return row


def make_phase(track, phase_id, start, end, **overrides) -> ProgramPhaseRow:
    fields = {"label": phase_id.title(), "term": "Fall 2026", "optional": False}
    fields.update(overrides)
    return ProgramPhaseRow.objects.create(
        track=track, phase_id=phase_id, start=start, end=end, **fields
    )


def make_requirement(track, **overrides) -> DegreeRequirement:
    fields = {"units_required": 50, "core_required": 8, "elective_required": 4}
    fields.update(overrides)
    return DegreeRequirement.objects.create(track=track, **fields)


def make_gap(profile, **overrides) -> DegreeGap:
    fields = {"label": "Gap", "detail": "Why it matters.", "severity": "watch"}
    fields.update(overrides)
    return DegreeGap.objects.create(user=profile.user, **fields)


def make_advisor(id=None, **overrides) -> Advisor:
    n = next(_counter)
    fields = {
        "id": id or f"adv-{n}",
        "name": f"Casey Advisor {n}",
        "role": "Graduate Student Advisor",
        "service": "advising",
        "location": "Rady 2S111",
        "email": f"advisor{n}@ucsd.edu",
    }
    fields.update(overrides)
    return Advisor.objects.create(**fields)


def make_slot(advisor, start=None, **overrides) -> AppointmentSlot:
    n = next(_counter)
    start = start or (timezone.now() + timezone.timedelta(days=2))
    fields = {
        "id": f"slot-{n}",
        "start": start,
        "end": start + timezone.timedelta(minutes=30),
        "mode": "zoom",
    }
    fields.update(overrides)
    return AppointmentSlot.objects.create(advisor=advisor, **fields)


def make_skill(profile, **overrides) -> Skill:
    n = next(_counter)
    fields = {"name": f"Skill {n}", "source": "manual"}
    fields.update(overrides)
    return Skill.objects.create(user=profile.user, **fields)


def make_highlight(code, **overrides) -> ResumeCourseHighlight:
    fields = {"title": f"Course {code}", "highlight": "Can analyze data"}
    fields.update(overrides)
    return ResumeCourseHighlight.objects.create(code=code, **fields)


def make_course_request(profile, **overrides) -> CourseRequest:
    fields = {"type": "enroll", "course": "MGTA 999 · Test Course",
              "reason": "why", "prefill": {}}
    fields.update(overrides)
    return CourseRequest.objects.create(user=profile.user, **fields)
