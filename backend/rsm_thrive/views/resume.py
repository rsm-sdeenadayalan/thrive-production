from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import ResumeVersion, Skill
from rsm_thrive.serializers.resume import skill_payload, version_payload


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


def resume_versions_dispatch(request):
    if request.method == "GET":
        return resume_versions(request)
    if request.method == "POST":
        return json_error("method_not_allowed", "Use GET or POST.", 405)  # replaced by generate in the next task
    return json_error("method_not_allowed", "Use GET or POST.", 405)
