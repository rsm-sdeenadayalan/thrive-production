"""Advisor Outlook calendar OAuth connect/callback (MS Graph, optional)."""
from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error
from rsm_thrive.models import Advisor, AdvisorCalendarConnection
from rsm_thrive.services import graph
from rsm_thrive.views.traces import staff_required


def _frontend_redirect(path: str) -> HttpResponseRedirect:
    origin = settings.THRIVE_FRONTEND_ORIGINS[0] if settings.THRIVE_FRONTEND_ORIGINS else ""
    return HttpResponseRedirect(f"{origin}{path}")


@api_login_required
@staff_required
@require_http_methods(["GET"])
def connect(request, advisor_id):
    if not graph.graph_enabled():
        return json_error("graph_disabled", "MS Graph is not configured.", 400)
    if not Advisor.objects.filter(pk=advisor_id).exists():
        return json_error("unknown_advisor", f"No advisor {advisor_id}.", 404)
    state = graph.sign_state(advisor_id)
    return HttpResponseRedirect(graph.build_auth_url(advisor_id, state))


@api_login_required
@staff_required
@require_http_methods(["GET"])
def callback(request):
    if not graph.graph_enabled():
        return json_error("graph_disabled", "MS Graph is not configured.", 400)
    advisor_id = graph.verify_state(request.GET.get("state", ""))
    if advisor_id is None:
        return json_error("invalid_state", "That connect link expired. Try again.", 400)
    advisor = Advisor.objects.filter(pk=advisor_id).first()
    if advisor is None:
        return json_error("unknown_advisor", f"No advisor {advisor_id}.", 404)
    code = request.GET.get("code", "")
    try:
        tokens = graph.exchange_code(code)
    except graph.GraphError as exc:
        return json_error("graph_exchange_failed", str(exc), 502)
    AdvisorCalendarConnection.objects.update_or_create(
        advisor=advisor,
        defaults={
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": tokens["expires_at"],
            "account_email": tokens["account_email"],
        },
    )
    return _frontend_redirect("/advisors?connected=1")
