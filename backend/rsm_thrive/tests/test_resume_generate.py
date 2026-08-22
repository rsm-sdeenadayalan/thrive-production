import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import (
    enroll, make_course, make_highlight, make_skill, make_student,
)

pytestmark = pytest.mark.django_db


def _setup(client):
    profile = make_student(goal="Data Scientist")   # program MSBA
    course = make_course(id="c1", code="MGTA 453", title="Business Analytics")
    enroll(profile, course)
    make_highlight("MGTA 453", title="Business Analytics",
                   highlight="Regression at scale")
    make_highlight("MGTA 999")                       # not enrolled: excluded
    for name in ("SQL", "Python", "Causal Inference", "Dashboards", "ML"):
        make_skill(profile, name=name)
    client.force_login(profile.user)
    return profile


def test_generate_first_version(client):
    _setup(client)
    resp = client.post("/api/thrive/resume/versions")
    assert resp.status_code == 201
    body = resp.json()
    version, diff = body["version"], body["diff"]
    assert version["isCurrent"] is True
    assert version["label"] == "Regenerated from Fall 2026 courses"
    assert version["summary"] == (
        "MSBA candidate at UC San Diego working toward a Data Scientist role. "
        "Coursework and projects across Causal Inference, Dashboards, ML, Python, "
        "and 1 more."
    )
    assert version["courses"] == [{"code": "MGTA 453", "title": "Business Analytics",
                                   "highlight": "Regression at scale"}]
    assert version["experience"] == []
    assert sorted(diff["addedSkills"]) == sorted(
        ["SQL", "Python", "Causal Inference", "Dashboards", "ML"])
    assert diff["addedCourses"] == ["MGTA 453 · Business Analytics"]
    assert diff["summaryChanged"] is True


def test_generate_second_version_diffs_and_carries_experience(client):
    profile = _setup(client)
    client.post("/api/thrive/resume/versions")
    first = ResumeVersion.objects.get(user=profile.user, is_current=True)
    first.experience = [{"id": "exp-1", "title": "Analyst", "organization": "Rady",
                         "period": "2026 - present", "bullets": ["did things"]}]
    first.save(update_fields=["experience"])
    make_skill(profile, name="Zsh")

    body = client.post("/api/thrive/resume/versions").json()
    assert body["diff"]["addedSkills"] == ["Zsh"]
    assert body["diff"]["addedCourses"] == []
    assert body["version"]["experience"][0]["title"] == "Analyst"
    assert ResumeVersion.objects.filter(user=profile.user, is_current=True).count() == 1
    assert ResumeVersion.objects.filter(user=profile.user).count() == 2
