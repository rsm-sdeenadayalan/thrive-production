import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_course, make_gap, make_phase, make_requirement, make_student,
)

pytestmark = pytest.mark.django_db


def _phases(track="11 month"):
    today = timezone.localdate()
    make_phase(track, "orientation", today - dt.timedelta(days=40),
               today - dt.timedelta(days=30), label="Orientation", term="Fall 2026")
    make_phase(track, "fall", today - dt.timedelta(days=29),
               today + dt.timedelta(days=30), label="Fall Quarter", term="Fall 2026")
    make_phase(track, "winter", today + dt.timedelta(days=31),
               today + dt.timedelta(days=120), label="Winter Quarter", term="Winter 2027")


def test_timeline_statuses_and_percent(client):
    profile = make_student(program_start=timezone.localdate() - dt.timedelta(days=40))
    _phases()
    client.force_login(profile.user)
    body = client.get("/api/thrive/degree/timeline").json()

    statuses = {p["id"]: p["status"] for p in body["phases"]}
    assert statuses == {"orientation": "complete", "fall": "current",
                        "winter": "upcoming"}
    assert body["currentPhaseId"] == "fall"
    assert body["track"] == "11 month"
    assert body["expectedFinishTerm"] == "Winter 2027"
    assert 0 <= body["percentComplete"] <= 100
    assert body["programEnd"] == body["phases"][-1]["end"]


def test_degree_progress_counts(client):
    profile = make_student()
    make_requirement("11 month", units_required=50, core_required=8,
                     elective_required=4)
    done_core = make_course(id="c1", units=4)
    done_elec = make_course(id="c2", units=4)
    pending = make_course(id="c3", units=4)
    enroll(profile, done_core, bucket="core", completed=True)
    enroll(profile, done_elec, bucket="elective", completed=True)
    enroll(profile, pending, bucket="core", completed=False)
    make_gap(profile, label="Capstone not scheduled", severity="watch")

    client.force_login(profile.user)
    body = client.get("/api/thrive/degree/progress").json()
    assert body["unitsCompleted"] == 8
    assert body["unitsRequired"] == 50
    assert body["coreDone"] == 1 and body["coreRequired"] == 8
    assert body["electiveDone"] == 1 and body["electiveRequired"] == 4
    assert body["gaps"][0]["label"] == "Capstone not scheduled"
    assert body["track"] == "11 month"
