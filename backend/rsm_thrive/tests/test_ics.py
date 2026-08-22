import datetime as dt

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.services.ics import build_ics
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def appt():
    adv = make_advisor(id="a1", name="Casey, PhD", email="casey@ucsd.edu")
    slot = make_slot(adv, start=dt.datetime(2026, 9, 1, 16, 0, tzinfo=dt.timezone.utc))
    student = make_student(username="ada")
    return Appointment.objects.create(slot=slot, student=student.user, reason="r",
                                      zoom_join_url="https://ucsd.zoom.us/j/123")


def test_request_ics(appt):
    ics = build_ics(appt, "REQUEST")
    assert "BEGIN:VCALENDAR" in ics and ics.endswith("END:VCALENDAR\r\n")
    assert "METHOD:REQUEST" in ics
    assert f"UID:thrive-appt-{appt.pk}@thrive.rady.ucsd.edu" in ics
    assert "DTSTART:20260901T160000Z" in ics
    assert "DTEND:20260901T163000Z" in ics
    assert "SUMMARY:THRIVE: Casey\\, PhD — advising" in ics
    assert "LOCATION:https://ucsd.zoom.us/j/123" in ics
    assert "ATTENDEE:mailto:ada@ucsd.edu" in ics
    assert "ATTENDEE:mailto:casey@ucsd.edu" in ics
    assert "SEQUENCE:0" in ics
    assert "\r\n" in ics


def test_cancel_ics_and_bad_method(appt):
    ics = build_ics(appt, "CANCEL")
    assert "METHOD:CANCEL" in ics and "STATUS:CANCELLED" in ics and "SEQUENCE:1" in ics
    with pytest.raises(ValueError):
        build_ics(appt, "PUBLISH")
