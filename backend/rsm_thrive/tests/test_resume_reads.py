import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _mk(profile, label, current=False):
    return ResumeVersion.objects.create(
        user=profile.user, label=label, summary="s",
        skills=[{"id": "skill-1", "name": "SQL", "source": "manual"}],
        courses=[{"code": "MGTA 453", "title": "BA", "highlight": "h"}],
        experience=[], is_current=current,
    )


def test_versions_newest_first_and_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1")
    v2 = _mk(profile, "v2", current=True)
    client.force_login(profile.user)

    body = client.get("/api/thrive/resume/versions").json()
    assert [v["id"] for v in body] == [f"rv-{v2.pk}", f"rv-{v1.pk}"]
    assert body[0]["isCurrent"] is True and body[1]["isCurrent"] is False
    assert body[0]["skills"][0]["name"] == "SQL"

    current = client.get("/api/thrive/resume/current").json()
    assert current["id"] == f"rv-{v2.pk}"


def test_current_404_when_none(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/resume/current")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_resume"


def test_versions_405_for_other_methods(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.put("/api/thrive/resume/versions", data="{}",
                      content_type="application/json")
    assert resp.status_code == 405
    assert resp.json()["error"]["code"] == "method_not_allowed"
