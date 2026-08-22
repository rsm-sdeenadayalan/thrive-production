from rsm_thrive.http import api_login_required, json_error, json_ok, BadRequest, parse_body
from rsm_thrive.services.degree import NotConfigured
from rsm_thrive.services.requests import build_prefill
from rsm_thrive.models import CourseRequest
from rsm_thrive.serializers.requests import request_payload


@api_login_required
def prefill(request):
    try:
        return json_ok(build_prefill(request.user.thrive_profile))
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)


VALID_REQUEST_TYPES = {"enroll", "drop", "reduced load", "out of major"}


@api_login_required
def my_requests(request):
    rows = list(CourseRequest.objects.filter(user=request.user))
    rows.sort(key=lambda r: (
        r.submitted_at is not None,                                   # drafts first
        -(r.submitted_at.timestamp() if r.submitted_at else 0),      # newest submitted
        r.pk,                                                         # drafts: creation order
    ))
    return json_ok([request_payload(r) for r in rows])


@api_login_required
def create_request(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    req_type = body.get("type")
    course = body.get("course")
    reason = body.get("reason")
    if req_type not in VALID_REQUEST_TYPES:
        return json_error("bad_request", "type must be a known request type.", 400)
    if not isinstance(course, str) or not course.strip():
        return json_error("bad_request", "course is required.", 400)
    if not isinstance(reason, str) or not reason.strip():
        return json_error("bad_request", "reason is required.", 400)
    try:
        snapshot = build_prefill(request.user.thrive_profile)
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)
    row = CourseRequest.objects.create(
        user=request.user, type=req_type, course=course.strip(),
        reason=reason.strip(), prefill=snapshot,
    )
    return json_ok(request_payload(row), status=201)


def requests_dispatch(request):
    if request.method == "GET":
        return my_requests(request)
    if request.method == "POST":
        return create_request(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
