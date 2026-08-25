import logging

from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok, profile_required
from rsm_thrive.models import JobPosting, PostingInteraction
from rsm_thrive.serializers.jobs import serialize_job, serialize_report
from rsm_thrive.services.jobs.feed import feed_for
from rsm_thrive.services.jobs.report import generate_report
from rsm_thrive.services.jobs.search import profile_of, role_benchmark, search_postings
from rsm_thrive.services.llm import get_llm

logger = logging.getLogger("rsm_thrive.jobs")

# Module-level seam: tests monkeypatch this with a FakeLLM factory.
llm_factory = get_llm


def _own_posting(job_id):
    if not job_id.startswith("job-"):
        return None
    pk = job_id.removeprefix("job-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return JobPosting.objects.filter(pk=pk).first()


@api_login_required
@require_http_methods(["GET"])
def jobs_search(request):
    query = request.GET.get("q", "")
    outcome = search_postings(request.user, query)
    results = [
        {
            "job": serialize_job(row["posting"]),
            "score": round(row["score"] * 100),
            "matchedSkills": row["matched_skills"],
            "missingSkills": row["missing_skills"],
        }
        for row in outcome["results"]
    ]
    return json_ok({
        "query": query,
        "profileAvailable": outcome["profile_available"],
        "benchmark": outcome["benchmark"],
        "results": results,
    })


def _parse_min_score(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    if value < 0 or value > 100:
        return 0
    return value


@api_login_required
@profile_required
def jobs_feed(request):
    if request.method != "GET":
        return json_error("method_not_allowed", "Use GET.", 405)
    score_with_llm = request.GET.get("score_with_llm") in ("1", "true")
    outcome = feed_for(
        request.user,
        query=request.GET.get("q", ""),
        tab=request.GET.get("tab", "recommended"),
        min_score=_parse_min_score(request.GET.get("min_score")),
        score_with_llm=score_with_llm,
        llm_factory=llm_factory if score_with_llm else None,
    )
    results = [
        {
            "job": serialize_job(entry["posting"]),
            "score": entry["score"],
            "reportScore": entry["report_score"],
            "competency": entry["competency"],
            "matchedSkills": entry["matched_skills"],
            "missingSkills": entry["missing_skills"],
            "liked": entry["liked"],
            "dismissed": entry["dismissed"],
        }
        for entry in outcome["results"]
    ]
    return json_ok({
        "results": results,
        "counts": outcome["counts"],
        "profileAvailable": outcome["profile_available"],
    })


@api_login_required
@require_http_methods(["GET"])
def job_detail(request, job_id):
    posting = _own_posting(job_id)
    if posting is None:
        return json_error("unknown_job", f"No job {job_id}.", 404)
    return json_ok({
        "job": serialize_job(posting, full=True),
        "benchmark": role_benchmark(posting.title),
    })


@api_login_required
@require_http_methods(["POST"])
def job_report(request, job_id):
    posting = _own_posting(job_id)
    if posting is None:
        return json_error("unknown_job", f"No job {job_id}.", 404)
    if profile_of(request.user) is None:
        return json_error("no_resume", "Upload or build a resume first.", 409)
    try:
        report = generate_report(llm_factory(), request.user, posting)
    except Exception:  # ReportError and any LLM/network failure alike: fail honest, not silent.
        logger.exception("match report generation failed (job=%s)", job_id)
        return json_error("llm_unavailable",
                          "The match report service is unavailable right now.", 503)
    return json_ok({"report": serialize_report(report)})


def _toggle_interaction(request, job_id, field):
    if request.method != "POST":
        return json_error("method_not_allowed", "Use POST.", 405)
    posting = _own_posting(job_id)
    if posting is None:
        return json_error("unknown_job", f"No job {job_id}.", 404)
    interaction, _created = PostingInteraction.objects.get_or_create(
        user=request.user, posting=posting)
    setattr(interaction, field, not getattr(interaction, field))
    interaction.save(update_fields=[field, "updated_at"])
    return json_ok({
        "jobId": job_id,
        "liked": interaction.liked,
        "dismissed": interaction.dismissed,
    })


@api_login_required
@profile_required
def job_like(request, job_id):
    return _toggle_interaction(request, job_id, "liked")


@api_login_required
@profile_required
def job_dismiss(request, job_id):
    return _toggle_interaction(request, job_id, "dismissed")
