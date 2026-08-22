from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.services.degree import degree_progress, program_timeline


@api_login_required
def timeline(request):
    return json_ok(program_timeline(request.user.thrive_profile, timezone.localdate()))


@api_login_required
def progress(request):
    return json_ok(degree_progress(request.user.thrive_profile))
