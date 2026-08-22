import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _mk(profile, label, current=False):
    return ResumeVersion.objects.create(user=profile.user, label=label,
                                        summary="s", is_current=current)


def test_switch_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1", current=True)
    v2 = _mk(profile, "v2")
    client.force_login(profile.user)

    body = client.post(f"/api/thrive/resume/versions/rv-{v2.pk}/current").json()
    assert body["id"] == f"rv-{v2.pk}" and body["isCurrent"] is True
    v1.refresh_from_db()
    assert v1.is_current is False

    # idempotent re-set
    again = client.post(f"/api/thrive/resume/versions/rv-{v2.pk}/current").json()
    assert again["isCurrent"] is True


def test_unknown_version_404_preserves_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1", current=True)
    other = make_student(username="other")
    theirs = _mk(other, "theirs")
    client.force_login(profile.user)
    for bad in (f"rv-{theirs.pk}", "rv-99999", "banana", "rv-²"):
        assert client.post(f"/api/thrive/resume/versions/{bad}/current").status_code == 404
    v1.refresh_from_db()
    assert v1.is_current is True   # never cleared by a failed switch
