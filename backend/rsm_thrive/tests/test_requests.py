import datetime as dt
import json

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_course_request, make_requirement, make_student

pytestmark = pytest.mark.django_db


def _post(client, body):
    return client.post("/api/thrive/requests", data=json.dumps(body),
                       content_type="application/json")


def test_create_request_freezes_prefill(client):
    profile = make_student()
    make_requirement("11 month")
    client.force_login(profile.user)
    resp = _post(client, {"type": "reduced load", "course": "  Term-wide  ",
                          "reason": " health "})
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "reduced load"
    assert body["course"] == "Term-wide" and body["reason"] == "health"
    assert body["status"] == "draft" and body["submittedAt"] is None
    assert body["prefill"]["track"] == "11 month"
    assert body["prefill"]["currentCourses"] == []


def test_create_request_validation(client):
    profile = make_student()
    make_requirement("11 month")
    client.force_login(profile.user)
    assert _post(client, {"type": "audit", "course": "x", "reason": "y"}).status_code == 400
    assert _post(client, {"type": "drop", "course": "  ", "reason": "y"}).status_code == 400
    assert _post(client, {"type": "drop", "course": "x", "reason": None}).status_code == 400
    assert _post(client, {"type": ["enroll"], "course": "x", "reason": "y"}).status_code == 400


def test_list_drafts_first_then_newest_submitted(client):
    profile = make_student()
    now = timezone.now()
    old = make_course_request(profile, status="submitted",
                              submitted_at=now - dt.timedelta(days=2))
    new = make_course_request(profile, status="submitted",
                              submitted_at=now - dt.timedelta(days=1))
    d1 = make_course_request(profile)   # drafts keep creation order
    d2 = make_course_request(profile)
    other = make_student(username="other")
    make_course_request(other)          # not mine

    client.force_login(profile.user)
    ids = [r["id"] for r in client.get("/api/thrive/requests").json()]
    assert ids == [f"req-{d1.pk}", f"req-{d2.pk}", f"req-{new.pk}", f"req-{old.pk}"]


def test_create_request_503_when_not_configured(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = _post(client, {"type": "drop", "course": "MGTA 453", "reason": "health"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "not_configured"


def test_requests_405_for_other_methods(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.put("/api/thrive/requests", data="{}",
                      content_type="application/json")
    assert resp.status_code == 405
    assert resp.json()["error"]["code"] == "method_not_allowed"
    resp = client.delete("/api/thrive/requests")
    assert resp.status_code == 405
    assert resp.json()["error"]["code"] == "method_not_allowed"
