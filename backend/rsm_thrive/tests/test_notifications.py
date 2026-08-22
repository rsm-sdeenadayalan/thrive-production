import json
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.mail import EmailMessage

from rsm_thrive.models import Appointment, AppointmentNotification
from rsm_thrive.services.zoom import FakeZoomClient, ZoomError
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def _book(client, slot):
    return client.post("/api/thrive/appointments",
                       data=json.dumps({"slotId": slot.id, "reason": "r"}),
                       content_type="application/json")


def test_booking_fires_zoom_and_email(client):
    me = make_student()
    adv = make_advisor(email="casey@ucsd.edu")
    slot = make_slot(adv, mode="zoom")
    client.force_login(me.user)
    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=FakeZoomClient()):
        assert _book(client, slot).status_code == 201

    appt = Appointment.objects.get()
    assert appt.zoom_join_url.startswith("https://ucsd.zoom.us/j/fake-")
    kinds = {n.kind: n.status for n in appt.notifications.all()}
    assert kinds == {"zoom": "sent", "email_request": "sent"}
    [msg] = mail.outbox
    assert msg.subject == f"THRIVE: appointment confirmed — {adv.name}"
    assert set(msg.to) == {"ada@ucsd.edu", "casey@ucsd.edu"}
    name, content, mimetype = msg.attachments[0]
    assert name == "invite.ics" and "METHOD:REQUEST" in content
    assert mimetype.startswith("text/calendar")


def test_zoom_missing_credentials_is_skipped_not_fatal(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    client.force_login(me.user)
    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=None):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    assert appt.notifications.get(kind="zoom").status == "skipped"
    assert appt.notifications.get(kind="email_request").status == "sent"


def test_zoom_failure_recorded_booking_survives(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    client.force_login(me.user)

    class BoomClient:
        def create_meeting(self, *a, **kw):
            raise ZoomError("zoom down")

    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=BoomClient()):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    zoom_row = appt.notifications.get(kind="zoom")
    assert zoom_row.status == "failed" and "zoom down" in zoom_row.detail


def test_zoom_non_zoom_error_still_never_fails_booking(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    client.force_login(me.user)

    class BoomClient:
        def create_meeting(self, *a, **kw):
            raise RuntimeError("boom")

    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=BoomClient()):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    zoom_row = appt.notifications.get(kind="zoom")
    assert zoom_row.status == "failed" and "boom" in zoom_row.detail


def test_in_person_booking_skips_zoom_entirely(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="in person")
    client.force_login(me.user)
    assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    assert not appt.notifications.filter(kind="zoom").exists()
    assert appt.notifications.get(kind="email_request").status == "sent"


def test_email_send_failure_recorded_booking_survives(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="in person")
    client.force_login(me.user)
    with patch.object(EmailMessage, "send", side_effect=RuntimeError("smtp down")):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    row = appt.notifications.get(kind="email_request")
    assert row.status == "failed" and "smtp down" in row.detail
    assert len(mail.outbox) == 0


def test_cancel_fires_cancel_email_once(client):
    me = make_student()
    adv = make_advisor()
    slot = make_slot(adv, mode="in person")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    client.force_login(me.user)
    client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")  # idempotent
    assert appt.notifications.filter(kind="email_cancel").count() == 1
    [msg] = mail.outbox
    assert "cancelled" in msg.subject
    assert "METHOD:CANCEL" in msg.attachments[0][1]
