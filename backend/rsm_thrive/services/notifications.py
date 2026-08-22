"""Appointment side effects: Zoom + ICS emails, audited, never fatal.

Runs in-request for now; when the Celery queue exists on the server (F5),
each dispatch_* becomes a task body and the call sites gain .delay().
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from rsm_thrive.models import AppointmentNotification
from rsm_thrive.services.ics import build_ics
from rsm_thrive.services.zoom import get_zoom_client

logger = logging.getLogger(__name__)


def _record(appointment, kind, status, detail=""):
    AppointmentNotification.objects.create(
        appointment=appointment, kind=kind, status=status, detail=detail[:2000],
    )


def _send_invite(appointment, method, kind):
    slot = appointment.slot
    advisor = slot.advisor
    verb = "confirmed" if method == "REQUEST" else "cancelled"
    local = timezone.localtime(slot.start).strftime("%A %b %-d, %-I:%M %p")
    try:
        message = EmailMessage(
            subject=f"THRIVE: appointment {verb} — {advisor.name}",
            body=(f"Your appointment with {advisor.name} on {local} is {verb}.\n"
                  f"Reason: {appointment.reason}\n"),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[appointment.student.email, advisor.email],
        )
        message.attach("invite.ics", build_ics(appointment, method),
                       f"text/calendar; method={method}; charset=UTF-8")
        message.send()
        _record(appointment, kind, "sent")
    except Exception as exc:  # audited, never fatal
        logger.exception("appointment email failed")
        _record(appointment, kind, "failed", str(exc))


def _create_zoom(appointment):
    slot = appointment.slot
    try:
        client = get_zoom_client()
        if client is None:
            _record(appointment, "zoom", "skipped", "no zoom credentials configured")
            return
        duration = max(1, int((slot.end - slot.start).total_seconds() // 60))
        url = client.create_meeting(
            f"THRIVE advising: {slot.advisor.name}", slot.start, duration)
        appointment.zoom_join_url = url
        appointment.save(update_fields=["zoom_join_url"])
        _record(appointment, "zoom", "sent", url)
    except Exception as exc:  # audited, never fatal
        logger.exception("zoom meeting creation failed")
        try:
            _record(appointment, "zoom", "failed", str(exc))
        except Exception:
            logger.exception("could not record zoom failure")


def dispatch_booking_side_effects(appointment) -> None:
    if appointment.slot.mode == "zoom":
        _create_zoom(appointment)
    _send_invite(appointment, "REQUEST", "email_request")


def dispatch_cancel_side_effects(appointment) -> None:
    _send_invite(appointment, "CANCEL", "email_cancel")
