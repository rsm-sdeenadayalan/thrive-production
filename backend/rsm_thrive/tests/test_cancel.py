import json

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_cancel_own_appointment_and_rebook(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    client.force_login(me.user)

    resp = client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # idempotent second cancel
    again = client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    assert again.status_code == 200 and again.json()["status"] == "cancelled"

    # slot is free again for someone else
    client.force_login(other.user)
    resp = client.post(
        "/api/thrive/appointments",
        data=json.dumps({"slotId": slot.id, "reason": "mine now"}),
        content_type="application/json",
    )
    assert resp.status_code == 201


def test_cancel_not_yours_or_unknown_404(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    theirs = Appointment.objects.create(slot=slot, student=other.user, reason="r")
    client.force_login(me.user)
    assert client.post(f"/api/thrive/appointments/appt-{theirs.pk}/cancel").status_code == 404
    assert client.post("/api/thrive/appointments/appt-99999/cancel").status_code == 404
    assert client.post("/api/thrive/appointments/banana/cancel").status_code == 404
    assert client.post("/api/thrive/appointments/appt-²/cancel").status_code == 404
