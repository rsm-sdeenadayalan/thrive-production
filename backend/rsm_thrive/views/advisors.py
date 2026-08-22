from django.db.models import Exists, OuterRef

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Advisor, Appointment, AppointmentSlot
from rsm_thrive.serializers.appointments import advisor_payload, slot_payload


@api_login_required
def advisors(request):
    rows = Advisor.objects.order_by("service", "name", "id")
    return json_ok([advisor_payload(a) for a in rows])


@api_login_required
def advisor_slots(request, advisor_id):
    if not Advisor.objects.filter(pk=advisor_id).exists():
        return json_error("unknown_advisor", f"No advisor {advisor_id}.", 404)
    taken = Appointment.objects.filter(slot=OuterRef("pk"), status="confirmed")
    rows = (AppointmentSlot.objects.filter(advisor_id=advisor_id)
            .annotate(taken=Exists(taken)).order_by("start", "id"))
    return json_ok([slot_payload(s, not s.taken) for s in rows])
