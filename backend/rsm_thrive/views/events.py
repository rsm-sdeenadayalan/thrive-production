from django.db.models import Q
from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Event
from rsm_thrive.serializers.events import event_payload


@api_login_required
def events(request):
    now = timezone.now()
    rows = (
        Event.objects
        .filter(Q(end__isnull=False, end__gte=now) | Q(end__isnull=True, start__gte=now))
        .order_by("start", "id")
    )
    goal = request.user.thrive_profile.goal
    return json_ok([event_payload(e, goal) for e in rows])
