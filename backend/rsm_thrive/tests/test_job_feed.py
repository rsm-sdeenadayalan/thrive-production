import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, MatchReport, PostingInteraction, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.feed import feed_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


def _posting(external_id, title="Data Analyst", description="sql python",
             skills=("sql", "python")):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=list(skills), embedding=vector)


def _resume(user, is_current=True, label="v1"):
    return ResumeVersion.objects.create(
        user=user, label=label, summary="sql analyst",
        skills=[{"id": "s1", "name": "SQL", "source": "manual"}],
        courses=[], experience=[], is_current=is_current)


class TestFeedFor:
    def test_empty_query_returns_all_active(self, student):
        _posting("1")
        _posting("2")
        outcome = feed_for(student, query="")
        assert len(outcome["results"]) == 2
        assert outcome["profile_available"] is False

    def test_dismissed_absent_from_recommended_but_present_in_all_and_counted(self, student):
        dismissed_posting = _posting("1")
        _posting("2")
        PostingInteraction.objects.create(
            user=student, posting=dismissed_posting, dismissed=True)

        recommended = feed_for(student, tab="recommended")
        all_tab = feed_for(student, tab="all")

        rec_ids = {e["posting"].pk for e in recommended["results"]}
        all_ids = {e["posting"].pk for e in all_tab["results"]}
        assert dismissed_posting.pk not in rec_ids
        assert dismissed_posting.pk in all_ids
        assert recommended["counts"] == {"recommended": 1, "liked": 0, "all": 2}

    def test_liked_tab_filters_to_liked_only(self, student):
        liked_posting = _posting("1")
        _posting("2")
        PostingInteraction.objects.create(user=student, posting=liked_posting, liked=True)

        outcome = feed_for(student, tab="liked")
        assert [e["posting"].pk for e in outcome["results"]] == [liked_posting.pk]
        assert outcome["counts"]["liked"] == 1

    def test_counts_are_independent_of_selected_tab(self, student):
        liked_posting = _posting("1")
        dismissed_posting = _posting("2")
        _posting("3")
        PostingInteraction.objects.create(user=student, posting=liked_posting, liked=True)
        PostingInteraction.objects.create(user=student, posting=dismissed_posting,
                                          dismissed=True)

        expected_counts = {"recommended": 2, "liked": 1, "all": 3}
        for tab in ("recommended", "liked", "all"):
            assert feed_for(student, tab=tab)["counts"] == expected_counts

    def test_unknown_tab_defaults_to_recommended(self, student):
        dismissed_posting = _posting("1")
        _posting("2")
        PostingInteraction.objects.create(
            user=student, posting=dismissed_posting, dismissed=True)
        outcome = feed_for(student, tab="bogus")
        assert len(outcome["results"]) == 1

    def test_min_score_uses_report_score_when_cached(self, student):
        _resume(student)
        posting = _posting("1")
        version = ResumeVersion.objects.get(user=student, is_current=True)
        MatchReport.objects.create(
            user=student, posting=posting, resume_version=version,
            competency="reach", score=10, matched_skills=[], gaps=[], verdict="v")

        outcome = feed_for(student, tab="all", min_score=50)
        assert outcome["results"] == []

        [entry] = feed_for(student, tab="all", min_score=0)["results"]
        assert entry["report_score"] == 10
        assert entry["competency"] == "reach"

    def test_min_score_falls_back_to_hybrid_score_without_report(self, student):
        _resume(student)
        overlapping = _posting("1", title="Data Analyst", description="sql python",
                               skills=("sql", "python"))
        _posting("2", title="Chef", description="cooking", skills=())

        outcome = feed_for(student, tab="all", min_score=1)
        ids = [e["posting"].external_id for e in outcome["results"]]
        assert ids == [overlapping.external_id]

    def test_report_overlay_only_for_current_resume_version(self, student):
        old_version = _resume(student, is_current=True, label="old")
        posting = _posting("1")
        MatchReport.objects.create(
            user=student, posting=posting, resume_version=old_version,
            competency="strong", score=90, matched_skills=["sql"], gaps=[], verdict="v")

        old_version.is_current = False
        old_version.save()
        _resume(student, is_current=True, label="new")

        [entry] = feed_for(student, tab="all")["results"]
        assert entry["report_score"] is None
        assert entry["competency"] is None


class TestFeedEndpoint:
    def test_shape_and_camel_case(self, client, student):
        _resume(student)
        posting = _posting("1")
        version = ResumeVersion.objects.get(user=student, is_current=True)
        MatchReport.objects.create(
            user=student, posting=posting, resume_version=version,
            competency="good", score=65, matched_skills=["sql"], gaps=["tableau"],
            verdict="v")

        payload = client.get("/api/thrive/jobs/feed").json()
        assert payload["profileAvailable"] is True
        assert payload["counts"] == {"recommended": 1, "liked": 0, "all": 1}
        [entry] = payload["results"]
        assert entry["job"]["id"] == f"job-{posting.pk}"
        assert entry["job"]["url"] == posting.url
        assert entry["score"] > 0
        assert entry["reportScore"] == 65
        assert entry["competency"] == "good"
        # matched/missing skills come from the stage-1 search overlap, not the
        # cached LLM report, so they reflect the resume's one "sql" skill
        # against the posting's default ("sql", "python") skill list.
        assert entry["matchedSkills"] == ["sql"]
        assert entry["missingSkills"] == ["python"]
        assert entry["liked"] is False
        assert entry["dismissed"] is False

    def test_empty_query_returns_results(self, client, student):
        _posting("1")
        _posting("2")
        payload = client.get("/api/thrive/jobs/feed").json()
        assert len(payload["results"]) == 2

    def test_dismissed_excluded_from_recommended_tab(self, client, student):
        posting = _posting("1")
        _posting("2")
        PostingInteraction.objects.create(user=student, posting=posting, dismissed=True)

        recommended = client.get("/api/thrive/jobs/feed?tab=recommended").json()
        all_tab = client.get("/api/thrive/jobs/feed?tab=all").json()
        assert posting.pk not in {int(e["job"]["id"].removeprefix("job-"))
                                  for e in recommended["results"]}
        assert posting.pk in {int(e["job"]["id"].removeprefix("job-"))
                              for e in all_tab["results"]}
        assert recommended["counts"] == all_tab["counts"]

    def test_invalid_min_score_treated_as_zero(self, client, student):
        _posting("1")
        payload = client.get("/api/thrive/jobs/feed?min_score=not-a-number").json()
        assert len(payload["results"]) == 1
        payload = client.get("/api/thrive/jobs/feed?min_score=999").json()
        assert len(payload["results"]) == 1
        payload = client.get("/api/thrive/jobs/feed?min_score=-5").json()
        assert len(payload["results"]) == 1

    def test_requires_login(self, client):
        assert client.get("/api/thrive/jobs/feed").status_code == 401

    def test_post_is_405(self, client, student):
        response = client.post("/api/thrive/jobs/feed")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"
