"""RFC 5545 invites for appointment emails. Pure text building, no I/O."""
import datetime as dt

from django.conf import settings


def _utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def build_ics(appointment, method: str) -> str:
    if method not in ("REQUEST", "CANCEL"):
        raise ValueError(f"Unsupported ICS method {method!r}")
    slot = appointment.slot
    advisor = slot.advisor
    location = (appointment.zoom_join_url
                if slot.mode == "zoom" and appointment.zoom_join_url
                else advisor.location)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//THRIVE//Rady MSBA//EN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:thrive-appt-{appointment.pk}@thrive.rady.ucsd.edu",
        f"DTSTAMP:{_utc(dt.datetime.now(dt.timezone.utc))}",
        f"DTSTART:{_utc(slot.start)}",
        f"DTEND:{_utc(slot.end)}",
        f"SUMMARY:{_escape(f'THRIVE: {advisor.name} — {advisor.service}')}",
        f"LOCATION:{_escape(location)}",
        f"ORGANIZER:mailto:{settings.DEFAULT_FROM_EMAIL}",
        f"ATTENDEE:mailto:{appointment.student.email}",
        f"ATTENDEE:mailto:{advisor.email}",
        f"SEQUENCE:{1 if method == 'CANCEL' else 0}",
    ]
    if method == "CANCEL":
        lines.append("STATUS:CANCELLED")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"
