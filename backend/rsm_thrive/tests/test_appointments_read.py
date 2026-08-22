import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_my_appointments_confirmed_only_sorted(client):
    me = make_student()
    other = make_student(username="other")
    adv = make_advisor(id="a1")
    base = timezone.now() + dt.timedelta(days=3)
    late = make_slot(adv, start=base + dt.timedelta(hours=2))
    early = make_slot(adv, start=base, mode="in person")
    gone = make_slot(adv, start=base + dt.timedelta(hours=4))
    theirs = make_slot(adv, start=base + dt.timedelta(hours=6))

    a_late = Appointment.objects.create(slot=late, student=me.user, reason="r")
    a_early = Appointment.objects.create(slot=early, student=me.user, reason="q")
    Appointment.objects.create(slot=gone, student=me.user, reason="x",
                               status="cancelled")          # excluded
    Appointment.objects.create(slot=theirs, student=other.user, reason="y")  # not mine

    client.force_login(me.user)
    body = client.get("/api/thrive/appointments").json()
    assert [a["id"] for a in body] == [f"appt-{a_early.pk}", f"appt-{a_late.pk}"]
    first = body[0]
    assert first == {
        "id": f"appt-{a_early.pk}",
        "advisorId": "a1",
        "studentId": me.user.username,
        "slotId": early.id,
        "start": first["start"],
        "end": first["end"],
        "mode": "in person",
        "reason": "q",
        "status": "confirmed",
    }
    assert first["start"].endswith(("-07:00", "-08:00"))
