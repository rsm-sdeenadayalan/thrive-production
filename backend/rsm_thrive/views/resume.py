from django.db import transaction
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import ResumeVersion, Skill
from rsm_thrive.serializers.resume import skill_payload, version_payload
from rsm_thrive.services.resume import generate_version


@api_login_required
def skills(request):
    rows = Skill.objects.filter(user=request.user).order_by("name", "pk")
    return json_ok([skill_payload(s) for s in rows])


@api_login_required
def resume_versions(request):
    rows = (ResumeVersion.objects.filter(user=request.user)
            .order_by("-created_at", "-pk"))
    return json_ok([version_payload(v) for v in rows])


@api_login_required
def resume_current(request):
    row = ResumeVersion.objects.filter(user=request.user, is_current=True).first()
    if row is None:
        return json_error("no_resume", "No resume versions yet.", 404)
    return json_ok(version_payload(row))


@api_login_required
def generate_version_view(request):
    version, diff = generate_version(request.user.thrive_profile)
    return json_ok({"version": version_payload(version), "diff": diff}, status=201)


def resume_versions_dispatch(request):
    if request.method == "GET":
        return resume_versions(request)
    if request.method == "POST":
        return generate_version_view(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)


def _own_version(user, version_id):
    if not version_id.startswith("rv-"):
        return None
    pk = version_id.removeprefix("rv-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return ResumeVersion.objects.filter(pk=pk, user=user).first()


@api_login_required
@require_http_methods(["POST"])
def set_current_version(request, version_id):
    with transaction.atomic():
        target = _own_version(request.user, version_id)
        if target is None:
            return json_error("unknown_version", f"No version {version_id}.", 404)
        ResumeVersion.objects.filter(user=request.user, is_current=True).update(
            is_current=False)
        target.is_current = True
        target.save(update_fields=["is_current"])
    return json_ok(version_payload(target))
