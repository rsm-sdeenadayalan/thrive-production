import datetime as dt

import jsonschema
import pytest
from django.utils import timezone

from rsm_thrive.services.requests import build_prefill
from rsm_thrive.services.resume import generate_version
from rsm_thrive.testing import (
    enroll, make_advisor, make_assignment, make_conversation, make_course,
    make_course_request, make_event, make_gap, make_highlight, make_meeting,
    make_message, make_phase, make_requirement, make_resource, make_shared_task,
    make_skill, make_slot, make_student, make_student_task, make_syllabus,
    set_assignment_status, set_override,
)
from . import schemas

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(client):
    profile = make_student(goal="Data Scientist")
    course = make_course(id="c1", code="MGTA 453")
    make_meeting(course)
    make_syllabus(course, source_url="https://rady.ucsd.edu/syllabus.pdf")
    a1 = make_assignment(course, id="a1", weight=30)
    make_assignment(course, id="a2", due=timezone.now() + timezone.timedelta(days=9))
    enroll(profile, course, nudge="Check in", current_grade="A-",
           bucket="core", completed=False)
    set_assignment_status(profile, a1, "graded", grade="A")
    set_override(profile, "asg:a1", done=False, title="Renamed")
    make_shared_task(source="career")
    make_student_task(profile)
    make_event(goal_tags=["data scientist"], end=timezone.now() + timezone.timedelta(days=3))
    make_resource(owner="Rady CMC")
    today = timezone.localdate()
    make_phase("11 month", "fall", today - dt.timedelta(days=10),
               today + dt.timedelta(days=60))
    make_requirement("11 month")
    make_gap(profile)
    adv = make_advisor(id="adv-c1", blurb="Ask me anything",
                       avatar_url="https://rady.ucsd.edu/a.png")
    slot_a = make_slot(adv)
    make_slot(adv, mode="in person")
    from rsm_thrive.models import Appointment
    Appointment.objects.create(slot=slot_a, student=profile.user, reason="contract")
    make_skill(profile, name="SQL", source="course", course=course)
    make_skill(profile, name="Stakeholder communication")
    make_highlight("MGTA 453", title="Business Analytics",
                   highlight="Can build a demand forecast")
    prefill = build_prefill(profile)
    make_course_request(profile, type="enroll", course="MGTA 999 · Test Course",
                        reason="Prereq satisfied", status="draft", prefill=prefill)
    make_course_request(profile, type="drop", course="MGTA 453 · Business Analytics",
                        reason="Scheduling conflict", status="submitted",
                        submitted_at=timezone.now(), prefill=prefill)
    conv = make_conversation(profile)
    make_message(conv)
    make_message(conv, role="thrive", body="answer")
    generate_version(profile)
    client.force_login(profile.user)
    return profile


CASES = [
    ("/api/thrive/me", schemas.STUDENT, False),
    ("/api/thrive/conversations", schemas.CONVERSATION, True),
    ("/api/thrive/courses", schemas.COURSE, True),
    ("/api/thrive/syllabi", schemas.SYLLABUS, True),
    ("/api/thrive/assignments", schemas.ASSIGNMENT, True),
    ("/api/thrive/tasks", schemas.TASK, True),
    ("/api/thrive/events", schemas.EVENT, True),
    ("/api/thrive/resources", schemas.RESOURCE_LINK, True),
    ("/api/thrive/degree/progress", schemas.DEGREE_PROGRESS, False),
    ("/api/thrive/degree/timeline", schemas.PROGRAM_TIMELINE, False),
    ("/api/thrive/overlay", schemas.OVERLAY, False),
    ("/api/thrive/advisors", schemas.ADVISOR, True),
    ("/api/thrive/advisors/adv-c1/slots", schemas.APPOINTMENT_SLOT, True),
    ("/api/thrive/appointments", schemas.APPOINTMENT, True),
    ("/api/thrive/requests/prefill", schemas.COURSE_REQUEST_PREFILL, False),
    ("/api/thrive/requests", schemas.COURSE_REQUEST, True),
    ("/api/thrive/tss", schemas.TSS, False),
    ("/api/thrive/resume/skills", schemas.SKILL, True),
    ("/api/thrive/resume/versions", schemas.RESUME_VERSION, True),
    ("/api/thrive/resume/current", schemas.RESUME_VERSION, False),
]


@pytest.mark.parametrize("path,schema,is_list", CASES)
def test_contract(world, client, path, schema, is_list):
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    if is_list:
        assert isinstance(body, list) and body, f"{path} returned an empty list"
        for item in body:
            jsonschema.validate(item, schema)
    else:
        jsonschema.validate(body, schema)
