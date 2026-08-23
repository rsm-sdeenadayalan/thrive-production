import logging

from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import JobPosting
from rsm_thrive.serializers.jobs import serialize_job, serialize_report
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
            "score": round(row["score"], 3),
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
