from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command

from rsm_thrive.models import Appointment, AppointmentNotification
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_retry_failed_email_succeeds_and_updates_row(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="in person")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    row = AppointmentNotification.objects.create(
        appointment=appt, kind="email_request", status="failed", detail="smtp down")

    out = StringIO()
    call_command("retry_notifications", stdout=out)

    row.refresh_from_db()
    assert row.status == "sent" and row.attempts == 2
    assert AppointmentNotification.objects.count() == 1  # no duplicate rows
    assert len(mail.outbox) == 1
    assert "retried 1" in out.getvalue()


def test_retry_skips_sent_and_skipped_rows(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    AppointmentNotification.objects.create(appointment=appt, kind="zoom",
                                           status="skipped", detail="no creds")
    out = StringIO()
    call_command("retry_notifications", stdout=out)
    assert "retried 0" in out.getvalue()
    assert len(mail.outbox) == 0
