import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, MatchReport, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.report import REPORT_PROMPT, _sanitize
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.views import jobs as jobs_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


@pytest.fixture
def resume(student):
    return ResumeVersion.objects.create(
        user=student, label="v", summary="sql analyst",
        skills=[{"id": "s1", "name": "SQL", "source": "manual"}],
        courses=[], experience=[], is_current=True)


@pytest.fixture
def posting():
    [vector] = FakeEmbeddings().embed(["Data Analyst\nsql"])
    return JobPosting.objects.create(source="fake", external_id="1",
                                     title="Data Analyst", company="Acme",
                                     url="https://e.example/1",
                                     description="sql", skills=["sql"],
                                     embedding=vector)


def _reply(score=72, competency="good"):
    return json.dumps({"score": score, "competency": competency,
                       "matched_skills": ["sql"], "gaps": ["tableau"],
                       "verdict": "Competitive. Emphasize SQL projects."})


def _install(monkeypatch, replies):
    fake = FakeLLM(replies=replies)
    monkeypatch.setattr(jobs_views, "llm_factory", lambda: fake)
    return fake


class TestReportEndpoint:
    def test_generates_and_caches(self, client, student, resume, posting, monkeypatch):
        _install(monkeypatch, [_reply()])
        first = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert first.status_code == 200
        report = first.json()["report"]
        assert report["competency"] == "good" and report["score"] == 72
        assert report["id"].startswith("rep-")
        # second call: FakeLLM is exhausted, so success proves the cache
        _install(monkeypatch, [])
        second = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert second.status_code == 200
        assert MatchReport.objects.count() == 1

    def test_new_resume_version_regenerates(self, client, student, resume, posting,
                                            monkeypatch):
        _install(monkeypatch, [_reply()])
        client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        resume.is_current = False
        resume.save()
        ResumeVersion.objects.create(user=student, label="v2", summary="new",
                                     skills=[], courses=[], experience=[],
                                     is_current=True)
        _install(monkeypatch, [_reply(score=40, competency="stretch")])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.json()["report"]["score"] == 40
        assert MatchReport.objects.count() == 2

    def test_no_resume_409(self, client, student, posting, monkeypatch):
        _install(monkeypatch, [])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "no_resume"

    def test_llm_failure_503(self, client, student, resume, posting, monkeypatch):
        _install(monkeypatch, [])  # first chat call raises
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "llm_unavailable"
        assert MatchReport.objects.count() == 0

    def test_bad_competency_derives_from_score(self, client, student, resume,
                                               posting, monkeypatch):
        _install(monkeypatch, [json.dumps({"score": 85, "competency": "amazing",
                                           "matched_skills": [], "gaps": [],
                                           "verdict": "Strong fit."})])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.json()["report"]["competency"] == "strong"

    def test_unknown_job_404_and_get_405(self, client, student, resume, monkeypatch):
        _install(monkeypatch, [])
        assert client.post("/api/thrive/jobs/job-999/report").status_code == 404
        assert client.get("/api/thrive/jobs/job-999/report").status_code == 405


class TestPromptHardening:
    def test_prompt_guards_against_prompt_injection_and_caps_score(self):
        assert "untrusted input" in REPORT_PROMPT
        assert "score at most 25" in REPORT_PROMPT

    def test_prompt_still_specifies_json_contract(self):
        assert '"score"' in REPORT_PROMPT
        assert '"competency"' in REPORT_PROMPT
        assert '"verdict"' in REPORT_PROMPT


class TestSanitizeStillWorks:
    def test_valid_envelope_round_trips(self):
        sanitized = _sanitize({"score": 72, "competency": "good",
                               "matched_skills": ["sql"], "gaps": ["tableau"],
                               "verdict": "Competitive."})
        assert sanitized == {"score": 72, "competency": "good",
                             "matched_skills": ["sql"], "gaps": ["tableau"],
                             "verdict": "Competitive."}

    def test_missing_verdict_raises(self):
        from rsm_thrive.services.jobs.report import ReportError
        with pytest.raises(ReportError):
            _sanitize({"score": 50, "competency": "good",
                      "matched_skills": [], "gaps": [], "verdict": ""})
