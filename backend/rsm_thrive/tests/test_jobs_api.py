import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


def _posting(external_id="1", title="Data Analyst", description="sql python",
             skills=("sql", "python")):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=list(skills), embedding=vector)


class TestSearchEndpoint:
    def test_shape_and_camel_case(self, client, student):
        ResumeVersion.objects.create(user=student, label="v", summary="sql person",
                                     skills=[{"id": "s1", "name": "SQL",
                                              "source": "manual"}],
                                     courses=[], experience=[], is_current=True)
        _posting()
        payload = client.get("/api/thrive/jobs?q=analyst").json()
        assert payload["profileAvailable"] is True
        assert payload["benchmark"]["sampleSize"] == 1
        [entry] = payload["results"]
        assert entry["job"]["id"].startswith("job-")
        assert entry["matchedSkills"] == ["sql"]
        assert "description" not in entry["job"] and "snippet" in entry["job"]

    def test_requires_login(self, client):
        assert client.get("/api/thrive/jobs").status_code in (401, 403)

    def test_post_is_405(self, client, student):
        assert client.post("/api/thrive/jobs").status_code == 405


class TestDetailEndpoint:
    def test_full_description_and_benchmark(self, client, student):
        posting = _posting(description="long description " * 30)
        payload = client.get(f"/api/thrive/jobs/job-{posting.pk}").json()
        assert payload["job"]["description"].startswith("long description")
        assert payload["benchmark"]["sampleSize"] == 1

    def test_unknown_and_malformed_404(self, client, student):
        for job_id in ("job-99999", "banana", "job-๑๒"):
            response = client.get(f"/api/thrive/jobs/{job_id}")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "unknown_job"
