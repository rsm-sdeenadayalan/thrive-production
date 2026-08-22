from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.services.degree import NotConfigured
from rsm_thrive.services.requests import build_prefill


@api_login_required
def prefill(request):
    try:
        return json_ok(build_prefill(request.user.thrive_profile))
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)
