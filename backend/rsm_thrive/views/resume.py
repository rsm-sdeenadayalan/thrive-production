import logging

from django.db import transaction
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok, profile_required
from rsm_thrive.models import ResumeVersion, Skill
from rsm_thrive.serializers.resume import skill_payload, version_payload
from rsm_thrive.services.jobs.resume_upload import extract_profile
from rsm_thrive.services.llm import get_llm
from rsm_thrive.services.resume import generate_version

logger = logging.getLogger("rsm_thrive.resume")

# Module-level seam: tests monkeypatch this with a FakeLLM factory.
llm_factory = get_llm

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIN_TEXT_CHARS = 200


def extract_uploaded_text(file) -> str:
    """Wrap pypdf over the uploaded stream; a named seam so tests can
    monkeypatch text extraction instead of generating text-bearing PDFs."""
    from pypdf import PdfReader

    reader = PdfReader(file)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


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
@profile_required
def generate_version_view(request):
    version, diff = generate_version(request.thrive_profile)
    return json_ok({"version": version_payload(version), "diff": diff}, status=201)


@api_login_required
@require_http_methods(["POST"])
def resume_upload(request):
    file = request.FILES.get("file")
    if file is None:
        return json_error("bad_request", "No file uploaded.", 400)

    name = (file.name or "").lower()
    magic = file.read(4)
    file.seek(0)
    if not name.endswith(".pdf") or magic != b"%PDF":
        return json_error("bad_request",
                          "Only PDF resumes are supported right now.", 400)

    if file.size > MAX_UPLOAD_BYTES:
        return json_error("too_large", "Resume file is too large (5MB max).", 400)

    text = extract_uploaded_text(file)
    if len(text.strip()) < MIN_TEXT_CHARS:
        return json_error("unreadable_resume",
                          "Could not extract enough text from this PDF — it "
                          "may be a scanned image.", 400)

    try:
        profile = extract_profile(llm_factory(), text)
    except Exception:  # UploadError and any LLM/network failure alike: fail honest, not silent.
        logger.exception("resume profile extraction failed")
        return json_error("llm_unavailable",
                          "The resume extraction service is unavailable right now.",
                          503)

    skills_payload = [{"id": f"up-{i + 1}", "name": s, "source": "manual"}
                      for i, s in enumerate(profile["skills"])]
    experience_payload = [{"id": f"exp-up-{i + 1}", **entry}
                          for i, entry in enumerate(profile["experience"])]

    with transaction.atomic():
        ResumeVersion.objects.filter(user=request.user, is_current=True).update(
            is_current=False)
        version = ResumeVersion.objects.create(
            user=request.user,
            label="Uploaded resume",
            summary=profile["summary"],
            skills=skills_payload,
            courses=[],
            experience=experience_payload,
            is_current=True,
        )
        # Only one uploaded resume should ever be live for job-search context;
        # drop older uploads (and their cascade-deleted MatchReports) but leave
        # generated (living-resume) versions untouched.
        ResumeVersion.objects.filter(
            user=request.user, label="Uploaded resume",
        ).exclude(pk=version.pk).delete()
    return json_ok(version_payload(version), status=201)


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
