import logging

from django.db.models import Exists, OuterRef

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Advisor, Appointment, AppointmentSlot
from rsm_thrive.serializers.appointments import advisor_payload, slot_payload
from rsm_thrive.services import graph

logger = logging.getLogger(__name__)


@api_login_required
def advisors(request):
    rows = Advisor.objects.order_by("service", "name", "id")
    return json_ok([advisor_payload(a) for a in rows])


def _busy_periods(advisor, rows):
    """Graph busy periods for `advisor` over the slot range, or [] when not
    connected. A Graph failure degrades to unfiltered availability rather
    than breaking this page.
    """
    if not rows or getattr(advisor, "calendar_connection", None) is None:
        return []
    try:
        return graph.get_busy_periods(advisor, rows[0].start, rows[-1].end)
    except graph.GraphError:
        logger.exception("graph busy-period lookup failed")
        return []


def _overlaps_busy(slot, busy_periods) -> bool:
    return any(slot.start < end and slot.end > start for start, end in busy_periods)


@api_login_required
def advisor_slots(request, advisor_id):
    advisor = Advisor.objects.filter(pk=advisor_id).first()
    if advisor is None:
        return json_error("unknown_advisor", f"No advisor {advisor_id}.", 404)
    taken = Appointment.objects.filter(slot=OuterRef("pk"), status="confirmed")
    rows = list(AppointmentSlot.objects.filter(advisor_id=advisor_id)
                .annotate(taken=Exists(taken)).order_by("start", "id"))
    busy = _busy_periods(advisor, rows)
    return json_ok([slot_payload(s, not s.taken and not _overlaps_busy(s, busy))
                    for s in rows])
