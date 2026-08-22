from django.db import IntegrityError, transaction

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import Appointment, AppointmentSlot
from rsm_thrive.serializers.appointments import appointment_payload

REASON_MAX = 500


@api_login_required
def my_appointments(request):
    rows = (Appointment.objects.filter(student=request.user, status="confirmed")
            .select_related("slot", "student").order_by("slot__start", "pk"))
    return json_ok([appointment_payload(a) for a in rows])


@api_login_required
def book_appointment(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    slot_id = body.get("slotId")
    reason = (body.get("reason") or "")
    if not isinstance(reason, str) or not reason.strip():
        return json_error("bad_request", "reason is required.", 400)
    slot = AppointmentSlot.objects.filter(pk=slot_id).first() if slot_id else None
    if slot is None:
        return json_error("slot_unknown", "That time is no longer listed.", 404)
    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                slot=slot, student=request.user, reason=reason.strip()[:REASON_MAX],
            )
    except IntegrityError:
        return json_error("slot_unavailable",
                          "That time was just taken. Pick another.", 409)
    return json_ok(appointment_payload(appointment), status=201)


def appointments_dispatch(request):
    if request.method == "GET":
        return my_appointments(request)
    if request.method == "POST":
        return book_appointment(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
