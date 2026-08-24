import pytest

from rsm_thrive.models import JobPosting, PostingInteraction
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    profile = make_student()
    client.force_login(profile.user)
    return profile.user


@pytest.fixture
def posting():
    [vector] = FakeEmbeddings().embed(["Data Analyst\nsql"])
    return JobPosting.objects.create(source="fake", external_id="1",
                                     title="Data Analyst", company="Acme",
                                     url="https://e.example/1",
                                     description="sql", skills=["sql"],
                                     embedding=vector)


class TestLikeEndpoint:
    def test_toggle_on_then_off(self, client, student, posting):
        first = client.post(f"/api/thrive/jobs/job-{posting.pk}/like")
        assert first.status_code == 200
        assert first.json() == {"jobId": f"job-{posting.pk}", "liked": True,
                                "dismissed": False}

        second = client.post(f"/api/thrive/jobs/job-{posting.pk}/like")
        assert second.status_code == 200
        assert second.json()["liked"] is False
        assert PostingInteraction.objects.count() == 1

    def test_unknown_and_malformed_404(self, client, student):
        for job_id in ("job-99999", "banana"):
            response = client.post(f"/api/thrive/jobs/{job_id}/like")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "unknown_job"

    def test_get_is_405(self, client, student, posting):
        response = client.get(f"/api/thrive/jobs/job-{posting.pk}/like")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"

    def test_requires_login(self, client, posting):
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/like")
        assert response.status_code == 401

    def test_other_users_interaction_untouched(self, client, student, posting):
        other_profile = make_student(username="other")
        PostingInteraction.objects.create(user=other_profile.user, posting=posting,
                                          liked=True)
        client.post(f"/api/thrive/jobs/job-{posting.pk}/like")
        other_row = PostingInteraction.objects.get(user=other_profile.user)
        assert other_row.liked is True
        mine = PostingInteraction.objects.get(user=student)
        assert mine.liked is True


class TestDismissEndpoint:
    def test_toggle_independent_of_like(self, client, student, posting):
        client.post(f"/api/thrive/jobs/job-{posting.pk}/like")
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/dismiss")
        assert response.status_code == 200
        assert response.json() == {"jobId": f"job-{posting.pk}", "liked": True,
                                    "dismissed": True}
        assert PostingInteraction.objects.count() == 1

    def test_unknown_and_malformed_404(self, client, student):
        for job_id in ("job-99999", "banana"):
            response = client.post(f"/api/thrive/jobs/{job_id}/dismiss")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "unknown_job"

    def test_get_is_405(self, client, student, posting):
        response = client.get(f"/api/thrive/jobs/job-{posting.pk}/dismiss")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"

    def test_requires_login(self, client, posting):
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/dismiss")
        assert response.status_code == 401
