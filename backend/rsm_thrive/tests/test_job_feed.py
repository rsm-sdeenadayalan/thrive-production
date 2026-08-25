import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, MatchReport, PostingInteraction, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.feed import LLM_SCORE_TOP_N, feed_for
from rsm_thrive.services.jobs.search import search_postings
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.testing import make_student
from rsm_thrive.views import jobs as jobs_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    profile = make_student()
    client.force_login(profile.user)
    return profile.user


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


def _reply(score=72, competency="good"):
    return json.dumps({"score": score, "competency": competency,
                       "matched_skills": ["sql"], "gaps": ["tableau"],
                       "verdict": "Competitive. Emphasize SQL projects."})


def _raising_factory(message="LLM backend unavailable in this test."):
    def factory():
        raise RuntimeError(message)
    return factory


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

    def test_no_student_profile_403(self, client):
        user = User.objects.create_user("noprofile", password="pw")
        client.force_login(user)
        response = client.get("/api/thrive/jobs/feed")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "no_profile"

    def test_post_is_405(self, client, student):
        response = client.post("/api/thrive/jobs/feed")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"


class TestFeedForLlmScoring:
    """The results page's opt-in: score the top candidates with the real
    rubric instead of the hybrid-search proxy. See `feed_for`'s
    `score_with_llm` and `_score_top_candidates_with_llm`.
    """

    def test_recommended_is_restricted_to_scored_candidates_and_resorted(self, student):
        _resume(student)
        _posting("1", title="Data Analyst")
        _posting("2", title="Data Analyst II")

        # `_score_top_candidates_with_llm` scores the cheap pre-rank's top
        # slice in ITS OWN order, so ask that same ranking what order the
        # LLM will see the two postings in, then script the FIRST one
        # scored to get the LOWER report score. A correct re-sort must
        # still put the SECOND-scored posting first once the reports are
        # in -- Recommended is the one tab this reordering is visible on.
        cheap_order = [row["posting"].pk
                      for row in search_postings(student, "", limit=200)["results"]]
        fake = FakeLLM(replies=[_reply(score=40, competency="stretch"),
                                _reply(score=90, competency="strong")])

        outcome = feed_for(student, tab="recommended", score_with_llm=True,
                           llm_factory=lambda: fake)

        assert [e["posting"].pk for e in outcome["results"]] == list(reversed(cheap_order))
        assert [e["report_score"] for e in outcome["results"]] == [90, 40]
        assert MatchReport.objects.count() == 2

    def test_recommended_never_backfills_from_outside_the_scored_window(self, student):
        _resume(student)
        for i in range(LLM_SCORE_TOP_N + 1):
            _posting(str(i), title=f"Data Analyst {i}")

        cheap_order = [row["posting"].pk
                      for row in search_postings(student, "", limit=200)["results"]]
        outside_the_window = cheap_order[LLM_SCORE_TOP_N]

        # Every one of the top-N candidates gets knocked down to a REACH
        # score; the 11th-ranked posting's cheap estimate is left completely
        # untouched, and would still beat all ten if Recommended fell back to
        # it -- exactly the bug ("an unverified proxy score outranking an
        # honestly-scored one") this whole feature exists to fix, one rank
        # down. Recommended must drop it, not let it back in.
        fake = FakeLLM(replies=[_reply(score=5, competency="reach")
                               for _ in range(LLM_SCORE_TOP_N)])

        outcome = feed_for(student, tab="recommended", score_with_llm=True,
                           llm_factory=lambda: fake, min_score=0)

        result_pks = [e["posting"].pk for e in outcome["results"]]
        assert outside_the_window not in result_pks
        assert len(result_pks) == LLM_SCORE_TOP_N
        assert all(e["report_score"] == 5 for e in outcome["results"])

    def test_all_and_liked_tabs_are_untouched_by_score_with_llm(self, student):
        """Only Recommended is restricted+resorted by the scoring pass --
        All and Liked still mean "everything matching the search," in the
        cheap pre-rank's own order, same as when `score_with_llm=False`.
        """
        _resume(student)
        for i in range(LLM_SCORE_TOP_N + 1):
            _posting(str(i), title=f"Data Analyst {i}")

        without_llm = feed_for(student, tab="all", score_with_llm=False)
        fake = FakeLLM(replies=[_reply(score=5, competency="reach")
                               for _ in range(LLM_SCORE_TOP_N)])
        with_llm = feed_for(student, tab="all", score_with_llm=True, llm_factory=lambda: fake)

        assert ([e["posting"].pk for e in without_llm["results"]]
                == [e["posting"].pk for e in with_llm["results"]])
        assert with_llm["counts"]["all"] == LLM_SCORE_TOP_N + 1

    def test_cached_report_is_reused_without_calling_the_llm(self, student):
        version = _resume(student)
        posting = _posting("1")
        MatchReport.objects.create(
            user=student, posting=posting, resume_version=version,
            competency="strong", score=95, matched_skills=["sql"], gaps=[],
            verdict="Cached.")
        fake = FakeLLM(replies=[])  # any .chat() call raises: cache must not call it

        outcome = feed_for(student, tab="all", score_with_llm=True,
                           llm_factory=lambda: fake)

        [entry] = outcome["results"]
        assert entry["report_score"] == 95
        assert fake.calls == []
        assert MatchReport.objects.count() == 1

    def test_llm_failure_on_one_posting_falls_back_to_its_estimate(self, student):
        _resume(student)
        overlapping = _posting("1", title="Data Analyst", description="sql python",
                               skills=("sql", "python"))
        fake = FakeLLM(replies=[])  # first (only) chat call raises

        outcome = feed_for(student, tab="all", score_with_llm=True,
                           llm_factory=lambda: fake)

        [entry] = outcome["results"]
        assert entry["report_score"] is None
        assert entry["posting"].pk == overlapping.pk
        assert MatchReport.objects.count() == 0

    def test_llm_entirely_unavailable_still_renders_estimates(self, student):
        _resume(student)
        _posting("1")
        _posting("2")

        outcome = feed_for(student, tab="all", score_with_llm=True,
                           llm_factory=_raising_factory())

        assert len(outcome["results"]) == 2
        assert all(e["report_score"] is None for e in outcome["results"])
        assert MatchReport.objects.count() == 0

    def test_only_scores_the_top_n_candidates(self, student):
        _resume(student)
        for i in range(LLM_SCORE_TOP_N + 3):
            _posting(str(i), title=f"Data Analyst {i}")
        fake = FakeLLM(replies=[_reply(score=80) for _ in range(LLM_SCORE_TOP_N)])

        feed_for(student, tab="all", score_with_llm=True, llm_factory=lambda: fake)

        assert MatchReport.objects.count() == LLM_SCORE_TOP_N
        assert len(fake.calls) == LLM_SCORE_TOP_N

    def test_floor_is_reapplied_against_the_report_score(self, student):
        _resume(student)
        _posting("1", title="Data Analyst", description="sql python",
                skills=("sql", "python"))

        [cheap_row] = search_postings(student, "", limit=200)["results"]
        cheap_score = round(cheap_row["score"] * 100)
        assert cheap_score >= 50, "test premise: the hybrid estimate must clear the floor"

        # The report knocks the same posting below that same floor -- the
        # floor must follow the report's score, not the proxy it replaced.
        fake = FakeLLM(replies=[_reply(score=20, competency="reach")])

        outcome = feed_for(student, tab="all", min_score=50, score_with_llm=True,
                           llm_factory=lambda: fake)

        assert outcome["results"] == []

    def test_no_profile_skips_llm_scoring_entirely(self, student):
        _posting("1")
        fake = FakeLLM(replies=[])

        outcome = feed_for(student, tab="all", score_with_llm=True,
                           llm_factory=lambda: fake)

        assert outcome["profile_available"] is False
        assert fake.calls == []
        assert MatchReport.objects.count() == 0


class TestFeedEndpointLlmScoring:
    def test_score_with_llm_query_param_generates_a_report(self, client, student,
                                                            monkeypatch):
        _resume(student)
        posting = _posting("1")
        fake = FakeLLM(replies=[_reply(score=88, competency="strong")])
        monkeypatch.setattr(jobs_views, "llm_factory", lambda: fake)

        payload = client.get("/api/thrive/jobs/feed?score_with_llm=1").json()

        [entry] = payload["results"]
        assert entry["job"]["id"] == f"job-{posting.pk}"
        assert entry["reportScore"] == 88
        assert entry["competency"] == "strong"

    def test_default_request_never_touches_the_llm(self, client, student, monkeypatch):
        _resume(student)
        _posting("1")
        monkeypatch.setattr(jobs_views, "llm_factory",
                            lambda: (_ for _ in ()).throw(
                                AssertionError("llm_factory should not run")))

        payload = client.get("/api/thrive/jobs/feed").json()

        [entry] = payload["results"]
        assert entry["reportScore"] is None
