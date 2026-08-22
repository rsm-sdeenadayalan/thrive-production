from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Appointment
from rsm_thrive.serializers.appointments import appointment_payload


@api_login_required
def my_appointments(request):
    rows = (Appointment.objects.filter(student=request.user, status="confirmed")
            .select_related("slot", "student").order_by("slot__start", "pk"))
    return json_ok([appointment_payload(a) for a in rows])


def appointments_dispatch(request):
    if request.method == "GET":
        return my_appointments(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
