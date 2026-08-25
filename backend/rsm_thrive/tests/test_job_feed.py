import json
import threading

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
             skills=("sql", "python"), location=""):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=list(skills), embedding=vector, location=location)


class TitleKeyedLLM:
    """A thread-safe stub keyed by the posting TITLE embedded in the user
    message, rather than by call order.

    `_score_top_candidates_with_llm` now scores candidates concurrently
    (see `report.generate_reports_concurrently`), so which posting's LLM
    call happens first is no longer deterministic -- a test that needs a
    SPECIFIC posting to get a SPECIFIC scripted score cannot rely on
    `FakeLLM`'s call-order queue and has to key off content instead.
    """

    def __init__(self, replies_by_title: dict):
        self._replies_by_title = dict(replies_by_title)
        self.calls = []
        self._lock = threading.Lock()

    def chat(self, system, messages, json_mode=False):
        with self._lock:
            self.calls.append((system, messages, json_mode))
        content = messages[0]["content"]
        for title, reply in self._replies_by_title.items():
            if f"Title: {title}\n" in content:
                return reply
        raise AssertionError(f"no scripted reply for this posting's title: {content[:200]!r}")


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
        one = _posting("1", title="Data Analyst")
        two = _posting("2", title="Data Analyst II")

        # Scoring now runs concurrently (see `report.generate_reports_concurrently`),
        # so which posting's LLM call happens first is not deterministic --
        # script by TITLE instead of call order, and give the FIRST-ranked
        # cheap-pre-rank posting the LOWER report score. A correct re-sort
        # must still put the SECOND-ranked posting first once the reports
        # are in -- Recommended is the one tab this reordering is visible on.
        fake = TitleKeyedLLM({
            one.title: _reply(score=40, competency="stretch"),
            two.title: _reply(score=90, competency="strong"),
        })

        outcome = feed_for(student, tab="recommended", score_with_llm=True,
                           llm_factory=lambda: fake)

        assert [e["posting"].pk for e in outcome["results"]] == [two.pk, one.pk]
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

    def test_scoring_window_is_wider_than_the_displayed_shortlist(self):
        # `jobs.ts`'s `targetResults` caps the results page's SHOWN list to
        # 10 -- this window has to stay strictly wider than that cap, or a
        # strong posting sitting just past #10 in the cheap pre-rank (the
        # reported bug) can never surface even after this fix.
        assert LLM_SCORE_TOP_N > 10

    def test_scoring_runs_concurrently_not_serially(self, student):
        """A wall-clock proof, not just a call count: `LLM_SCORE_TOP_N`
        candidates each scored by an LLM stub that sleeps must finish in
        roughly ONE sleep's worth of time, not `LLM_SCORE_TOP_N` of them --
        otherwise widening the window (10 -> 24) would make every fresh
        search noticeably slower, which is the whole reason the scoring
        pass was parallelized alongside the widening.
        """
        import time

        _resume(student)
        for i in range(LLM_SCORE_TOP_N):
            _posting(str(i), title=f"Data Analyst {i}")

        sleep_seconds = 0.2

        class SleepyLLM:
            def __init__(self):
                self.calls = 0
                self._lock = threading.Lock()

            def chat(self, system, messages, json_mode=False):
                with self._lock:
                    self.calls += 1
                time.sleep(sleep_seconds)
                return _reply(score=70)

        fake = SleepyLLM()
        started = time.monotonic()
        feed_for(student, tab="all", score_with_llm=True, llm_factory=lambda: fake)
        elapsed = time.monotonic() - started

        assert fake.calls == LLM_SCORE_TOP_N
        # Serial would take LLM_SCORE_TOP_N * sleep_seconds (4.8s here).
        # Bounded to 8 workers, the real minimum is ceil(24/8) = 3 sleeps;
        # generous slack keeps this stable on a loaded CI box while still
        # failing hard if scoring regresses to fully serial.
        assert elapsed < sleep_seconds * (LLM_SCORE_TOP_N / 2)


class TestFeedForRegionFilter:
    """`region` (see `services/jobs/region.py`) narrows the candidate pool
    BEFORE the LLM-scoring window is chosen -- filtering to a region scores
    postings from that region, not the global top-N filtered down to
    whatever survives. See `feed_for`'s `region` param.
    """

    def test_filters_to_the_requested_region(self, student):
        sd = _posting("1", title="Data Analyst", location="San Diego, CA")
        _posting("2", title="Data Analyst", location="Tokyo, Japan")

        outcome = feed_for(student, tab="all", region="san_diego")

        assert [e["posting"].pk for e in outcome["results"]] == [sd.pk]
        assert outcome["counts"]["all"] == 1

    def test_no_region_shows_everything(self, student):
        _posting("1", location="San Diego, CA")
        _posting("2", location="Tokyo, Japan")

        outcome = feed_for(student, tab="all", region="")

        assert len(outcome["results"]) == 2

    def test_unrecognized_region_value_is_treated_as_no_filter(self, student):
        _posting("1", location="San Diego, CA")
        _posting("2", location="Tokyo, Japan")

        outcome = feed_for(student, tab="all", region="mars")

        assert len(outcome["results"]) == 2

    def test_region_filter_applies_before_the_llm_scoring_window(self, student):
        """The regression this test guards against: filtering AFTER slicing
        the top-N cheap-rank candidates would score the global top N and
        then filter it down to (often) nothing. Filtering first means a
        region with fewer than N matching postings still gets every one of
        them scored.
        """
        _resume(student)
        remote_postings = [
            _posting(f"remote-{i}", title=f"Data Analyst {i}", location="Remote")
            for i in range(3)
        ]
        # Plenty of non-remote postings that would fill the scoring window
        # if the filter ran after slicing instead of before.
        for i in range(LLM_SCORE_TOP_N):
            _posting(f"office-{i}", title=f"Data Analyst {i}", location="Tokyo, Japan")

        fake = FakeLLM(replies=[_reply(score=70) for _ in remote_postings])

        outcome = feed_for(student, tab="recommended", region="remote",
                           score_with_llm=True, llm_factory=lambda: fake)

        result_pks = {e["posting"].pk for e in outcome["results"]}
        assert result_pks == {p.pk for p in remote_postings}
        assert MatchReport.objects.count() == len(remote_postings)

    def test_region_filter_applies_to_all_and_liked_tabs_too(self, student):
        _posting("1", location="San Diego, CA")
        _posting("2", location="Tokyo, Japan")

        all_tab = feed_for(student, tab="all", region="san_diego")
        liked_tab = feed_for(student, tab="liked", region="san_diego")

        assert all_tab["counts"]["all"] == 1
        assert all_tab["counts"] == liked_tab["counts"]

    def test_region_with_no_matches_returns_an_empty_but_honest_result(self, student):
        _posting("1", location="Tokyo, Japan")

        outcome = feed_for(student, tab="all", region="san_diego")

        assert outcome["results"] == []
        assert outcome["counts"] == {"recommended": 0, "liked": 0, "all": 0}


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


class TestFeedEndpointRegion:
    def test_region_query_param_filters_results(self, client, student):
        sd = _posting("1", location="San Diego, CA")
        _posting("2", location="Tokyo, Japan")

        payload = client.get("/api/thrive/jobs/feed?tab=all&region=san_diego").json()

        [entry] = payload["results"]
        assert entry["job"]["id"] == f"job-{sd.pk}"
        assert payload["counts"]["all"] == 1

    def test_no_region_param_is_the_same_as_all_regions(self, client, student):
        _posting("1", location="San Diego, CA")
        _posting("2", location="Tokyo, Japan")

        payload = client.get("/api/thrive/jobs/feed?tab=all").json()

        assert len(payload["results"]) == 2
