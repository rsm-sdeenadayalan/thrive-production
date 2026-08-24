import json

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from rsm_thrive.models import JobPosting, MatchReport, ResumeVersion
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.views import resume as resume_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


def _envelope():
    return json.dumps({
        "summary": "Analytics graduate student with SQL-heavy internships.",
        "skills": ["SQL", "Python", ""],
        "experience": [{"title": "Data Intern", "organization": "Acme",
                        "period": "Summer 2025", "bullets": ["Built dashboards"]}],
    })


def _install(monkeypatch, replies):
    fake = FakeLLM(replies=replies)
    monkeypatch.setattr(resume_views, "llm_factory", lambda: fake)
    return fake


def _upload(client, content=b"%PDF-1.4 x", name="cv.pdf"):
    return client.post("/api/thrive/resume/upload",
                       {"file": SimpleUploadedFile(name, content,
                                                   content_type="application/pdf")})


class TestUpload:
    def test_creates_current_version(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "Jane Doe. SQL intern at Acme. " * 20)
        _install(monkeypatch, [_envelope()])
        response = _upload(client)
        assert response.status_code == 201
        version = ResumeVersion.objects.get(user=student, is_current=True)
        assert [s["name"] for s in version.skills] == ["SQL", "Python"]
        assert version.experience[0]["organization"] == "Acme"

    def test_replaces_previous_current(self, client, student, monkeypatch):
        old = ResumeVersion.objects.create(user=student, label="Uploaded resume",
                                           summary="s", skills=[], courses=[],
                                           experience=[], is_current=True)
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [_envelope()])
        assert _upload(client).status_code == 201
        # The old uploaded version is gone, not just un-currented: only the
        # newest uploaded resume should stick around for job-search scoring.
        assert not ResumeVersion.objects.filter(pk=old.pk).exists()
        assert ResumeVersion.objects.filter(user=student).count() == 1
        current = ResumeVersion.objects.get(user=student, is_current=True)
        assert current.label == "Uploaded resume"

    def test_second_upload_deletes_old_upload_and_its_match_reports(
            self, client, student, monkeypatch):
        old = ResumeVersion.objects.create(user=student, label="Uploaded resume",
                                           summary="s", skills=[], courses=[],
                                           experience=[], is_current=True)
        posting = JobPosting.objects.create(
            source="fake", external_id="1", title="Data Analyst", company="Acme",
            url="https://e.example/1", description="sql", skills=["sql"],
            embedding=[])
        report = MatchReport.objects.create(
            user=student, posting=posting, resume_version=old,
            competency="good", score=72, matched_skills=["sql"], gaps=[],
            verdict="ok")

        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [_envelope()])
        assert _upload(client).status_code == 201

        uploaded = ResumeVersion.objects.filter(user=student,
                                                label="Uploaded resume")
        assert uploaded.count() == 1
        newest = uploaded.get()
        assert newest.is_current is True
        assert newest.pk != old.pk
        assert not MatchReport.objects.filter(pk=report.pk).exists()

    def test_generated_version_survives_upload_uncurrented(
            self, client, student, monkeypatch):
        generated = ResumeVersion.objects.create(
            user=student, label="Living resume v1", summary="s", skills=[],
            courses=[], experience=[], is_current=True)

        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [_envelope()])
        assert _upload(client).status_code == 201

        generated.refresh_from_db()
        assert generated.is_current is False
        assert ResumeVersion.objects.filter(pk=generated.pk).exists()
        assert ResumeVersion.objects.filter(user=student).count() == 2

    def test_non_pdf_400(self, client, student, monkeypatch):
        _install(monkeypatch, [])
        response = _upload(client, content=b"plain text", name="cv.txt")
        assert response.status_code == 400

    def test_unreadable_pdf_400(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text", lambda f: "  ")
        _install(monkeypatch, [])
        response = _upload(client)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unreadable_resume"

    def test_llm_failure_503_and_nothing_created(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [])
        assert _upload(client).status_code == 503
        assert ResumeVersion.objects.count() == 0

    def test_missing_file_400(self, client, student, monkeypatch):
        _install(monkeypatch, [])
        assert client.post("/api/thrive/resume/upload").status_code == 400
