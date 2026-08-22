import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_course_request, make_student

pytestmark = pytest.mark.django_db


def test_submit_draft_then_idempotent(client):
    profile = make_student()
    req = make_course_request(profile)
    client.force_login(profile.user)

    first = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert first["status"] == "submitted" and first["submittedAt"] is not None

    second = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert second == first  # unchanged, not re-stamped


def test_submit_never_demotes_approved(client):
    profile = make_student()
    stamp = timezone.now() - dt.timedelta(days=3)
    req = make_course_request(profile, status="approved", submitted_at=stamp)
    client.force_login(profile.user)
    body = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert body["status"] == "approved"


def test_submit_unknown_and_malformed_404(client):
    profile = make_student()
    other = make_student(username="other")
    theirs = make_course_request(other)
    client.force_login(profile.user)
    for bad in (f"req-{theirs.pk}", "req-99999", "banana", "req-²"):
        assert client.post(f"/api/thrive/requests/{bad}/submit").status_code == 404


def test_tss_connect_roundtrip(client):
    profile = make_student()
    client.force_login(profile.user)
    assert client.get("/api/thrive/tss").json() == {"connected": False}
    assert client.post("/api/thrive/tss/connect").json() == {"connected": True}
    assert client.get("/api/thrive/tss").json() == {"connected": True}
    from rsm_thrive.models import StudentProfile
    assert StudentProfile.objects.get(user=profile.user).tss_connected is True
