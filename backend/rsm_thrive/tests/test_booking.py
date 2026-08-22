import json

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def _book(client, slot_id, reason="Talk about electives"):
    return client.post(
        "/api/thrive/appointments",
        data=json.dumps({"slotId": slot_id, "reason": reason}),
        content_type="application/json",
    )


def test_booking_happy_path(client):
    me = make_student()
    slot = make_slot(make_advisor(id="a1"))
    client.force_login(me.user)
    resp = _book(client, slot.id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["slotId"] == slot.id and body["status"] == "confirmed"
    assert body["studentId"] == me.user.username
    # and the slot now reads unavailable
    slots = client.get("/api/thrive/advisors/a1/slots").json()
    assert slots[0]["available"] is False


def test_booking_unknown_slot_404(client):
    me = make_student()
    client.force_login(me.user)
    resp = _book(client, "slot-nope")
    assert resp.status_code == 404
    assert resp.json()["error"] == {
        "code": "slot_unknown", "message": "That time is no longer listed."}


def test_booking_taken_slot_409(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    Appointment.objects.create(slot=slot, student=other.user, reason="x")
    client.force_login(me.user)
    resp = _book(client, slot.id)
    assert resp.status_code == 409
    assert resp.json()["error"] == {
        "code": "slot_unavailable", "message": "That time was just taken. Pick another."}


def test_booking_requires_reason_and_truncates(client):
    me = make_student()
    slot = make_slot(make_advisor())
    client.force_login(me.user)
    assert _book(client, slot.id, reason="   ").status_code == 400
    resp = _book(client, slot.id, reason="x" * 600)
    assert resp.status_code == 201
    assert len(resp.json()["reason"]) == 500
