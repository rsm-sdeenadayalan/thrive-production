from django.utils import timezone

from rsm_thrive.http import api_login_required, json_error, json_ok, profile_required
from rsm_thrive.services.degree import NotConfigured, degree_progress, program_timeline


@api_login_required
@profile_required
def timeline(request):
    try:
        return json_ok(program_timeline(request.thrive_profile, timezone.localdate()))
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)


@api_login_required
@profile_required
def progress(request):
    try:
        return json_ok(degree_progress(request.thrive_profile))
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)
