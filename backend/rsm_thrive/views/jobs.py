from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import JobPosting
from rsm_thrive.serializers.jobs import serialize_job
from rsm_thrive.services.jobs.search import role_benchmark, search_postings


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
