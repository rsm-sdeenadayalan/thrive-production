from rsm_thrive.services import skill_match
from rsm_thrive.services.grounded_course_advisor.advisor import (
    MAX_RESULTS,
    _render,
    is_industry_course_question,
)


def _course(code, **fields):
    base = {"code": code, "id": code, "title": code, "units": 4,
            "is_core": False, "skills": [], "topics": [], "tools": [],
            "description": ""}
    base.update(fields)
    return base


def _rank(requirements, catalog, field=None):
    """What the advisor now does: flatten the web's answer, then match."""
    wanted = [value for key in ("skills", "tools", "topics")
              for value in requirements.get(key, [])]
    return skill_match.rank(wanted, domain=field, catalog=catalog)


def _body(requirements, catalog, field=None):
    wanted = [value for key in ("skills", "tools", "topics")
              for value in requirements.get(key, [])]
    fits = skill_match.rank(wanted, domain=field, catalog=catalog)
    cover = skill_match.coverage(wanted, fits, catalog=catalog)
    return _render(requirements, fits, cover, field)


def test_a_course_needs_more_than_one_match_and_the_core_is_excluded():
    catalog = [
        _course("MGTA 1", title="Analytics", skills=["predictive modeling"],
                topics=["optimization"]),
        _course("MGTA 2", title="One Match", skills=["optimization"]),
        _course("MGTA 3", title="Core Match", is_core=True,
                skills=["predictive modeling"], topics=["optimization"]),
    ]
    fits = _rank({"skills": ["predictive modeling"], "tools": [],
                  "topics": ["optimization"]}, catalog)
    assert [fit.course["code"] for fit in fits] == ["MGTA 1"]


class TestShortRequirementsAreNotFreeMatches:
    """Substring matching made one-and-two letter requirements match nearly
    everything: measured against the real catalog, "r" appeared inside some word
    of all 31 courses, "ai" in 14, "bi" in 11."""

    def test_r_does_not_match_a_course_that_never_lists_it(self):
        # "r" is inside "training" and "architectures". It is not a tool here.
        deep_learning = _course(
            "CSE 251B", tools=["Python", "PyTorch"],
            skills=["building and training deep neural networks",
                    "modern architectures (CNNs, transformers)"])
        fits = _rank({"skills": ["r"], "tools": ["python"], "topics": []},
                     [deep_learning])
        assert fits == [], "matched on the letter r inside other words"

    def test_r_still_matches_a_course_that_does_list_it(self):
        forecasting = _course("MGTF 405", title="Business Forecasting",
                              tools=["R", "Python"], skills=["forecasting"])
        fits = _rank({"skills": ["forecasting"], "tools": ["r", "python"],
                      "topics": []}, [forecasting])
        assert [fit.course["code"] for fit in fits] == ["MGTF 405"]

    def test_ai_does_not_match_supply_chain(self):
        supply = _course("MGTA 456", title="Supply Chain Analytics",
                         skills=["forecasting"], topics=["supply chain"])
        fits = _rank({"skills": ["ai", "forecasting"], "tools": [],
                      "topics": ["supply chain"]}, [supply])
        assert fits, "the two real requirements should still match"
        assert "ai" not in fits[0].covered, "'ai' matched inside 'chain'"

    def test_a_multi_word_requirement_still_matches(self):
        course = _course("MGTA 457", title="Business Intelligence Systems",
                         skills=["data visualization"], tools=["Tableau"])
        fits = _rank({"skills": ["data visualization"], "tools": ["tableau"],
                      "topics": []}, [course])
        assert [fit.course["code"] for fit in fits] == ["MGTA 457"]


class TestAWordInsideAnotherWordIsNotAMatch:
    """The shared-stem rule's own failure mode, and the one that mattered most:
    "tableau" and "table" share five characters, so a course teaching SQL
    common TABLE expressions was credited with teaching Tableau."""

    def test_tableau_does_not_match_common_table_expressions(self):
        sql = _course("MGTA 464", title="SQL and ETL",
                      topics=["common table expressions"], skills=["sql querying"])
        fits = _rank({"skills": [], "tools": ["tableau"], "topics": []}, [sql])
        assert fits == []

    def test_healthcare_does_not_match_health(self):
        marketing = _course("MGTA 495", title="Special Topics: Marketing Analytics",
                            skills=["consumer health surveys"], tools=["R"])
        fits = _rank({"skills": [], "tools": ["r"], "topics": []},
                     [marketing], field="healthcare")
        assert not any(fit.domain for fit in fits)

    def test_an_ordinary_inflection_still_matches(self):
        course = _course("MGTF 405", title="Business Forecasting",
                         skills=["building forecasting models"],
                         topics=["demand forecasts"])
        fits = _rank({"skills": ["forecast"], "tools": [],
                      "topics": ["forecasting models"]}, [course])
        assert fits and fits[0].course["code"] == "MGTF 405"


class TestAGenericRequirementCannotCarryARecommendation:
    """The aerospace failure. Every requirement used to be worth the same, so
    three of four results were carried by "python" -- a word describing half
    this catalog, which tells a student nothing about which course to take."""

    CATALOG = [_course(f"MGTA {n}", title=f"Thing {n}", tools=["Python"],
                       skills=["general analysis"])
               for n in range(6)] + [
        _course("MGTA 9", title="Reliability Engineering",
                skills=["reliability analysis"], tools=["Python"]),
    ]

    def test_a_requirement_the_whole_pool_meets_is_worth_nothing(self):
        weights = skill_match.discriminations(
            ["python", "reliability analysis"], catalog=self.CATALOG)
        assert weights["python"] == 0.0
        assert weights["reliability analysis"] > 1.0

    def test_the_course_that_meets_the_rare_requirement_leads(self):
        fits = _rank({"skills": ["reliability analysis"], "tools": ["python"],
                      "topics": []}, self.CATALOG)
        assert fits[0].course["code"] == "MGTA 9"

    def test_tooling_alone_is_not_a_recommendation(self):
        """A course matched only on the software it uses is not a course
        recommended for the field."""
        fits = _rank({"skills": [], "tools": ["python", "excel"], "topics": []},
                     [_course("MGTA 1", tools=["Python", "Excel"]),
                      _course("MGTA 2", tools=["Python", "Excel"],
                              skills=["excel modelling"])])
        assert [fit.course["code"] for fit in fits] == ["MGTA 2"]


class TestTheAnswerSaysWhatIsMissing:
    """Three courses with no caveat reads as "these will get you there"."""

    THIN = {"skills": ["systems engineering", "reliability analysis",
                       "predictive maintenance"],
            "tools": ["python"], "topics": [], "summary": ""}
    CATALOG = [_course("MGTA 1", title="Analytics", tools=["Python"],
                       skills=["predictive maintenance scheduling"],
                       topics=["python programming"])]

    def test_thin_coverage_leads_with_the_caveat(self):
        body = _body(self.THIN, self.CATALOG, "aerospace")
        assert "not a route into that field" in body
        assert "systems engineering" in body, "and it names what is missing"

    def test_what_is_unmet_is_listed_even_when_coverage_is_good(self):
        good = {"skills": ["predictive maintenance", "sql"], "tools": [],
                "topics": [], "summary": ""}
        catalog = [_course("MGTA 1", skills=["predictive maintenance scheduling"],
                           topics=["sql querying"]),
                   _course("MGTA 2", skills=["reliability analysis"])]
        body = _body(good, catalog)
        assert "Not covered by anything here" not in body or "sql" not in body


class TestTheDisclaimerFitsTheQuestion:
    """It named one industry as a literal, whatever had been asked -- a
    healthcare question closed with 'not a guarantee of aerospace employment'."""

    def test_no_industry_is_hardcoded(self):
        body = _body({"skills": ["sql querying"], "tools": ["tableau"],
                      "topics": [], "summary": ""},
                     [_course("MGTA 464", title="SQL and ETL",
                              skills=["sql querying"], tools=["Tableau"]),
                      _course("MGTA 2", title="Other")])
        assert "aerospace" not in body.lower()

    def test_the_no_match_reply_recommends_nothing(self):
        body = _body({"skills": [], "tools": [], "topics": [], "summary": ""},
                     [_course("MGTA 1", title="Nothing Relevant")])
        assert "won't name a course without a catalog match" in body
        assert "MGTA" not in body


class TestTheSearchIsVisibleInTheAnswer:
    """The lookup returns a one-line read on the field. It was parsed and
    discarded, so a student saw a list of skills with nothing saying where
    they came from."""

    SUMMARY = "Healthcare analytics teams work on claims and clinical data."
    CATALOG = [_course("MGTA 464", title="SQL and ETL", skills=["sql querying"],
                       tools=["Tableau"]),
               _course("MGTA 2", title="Unrelated", skills=["poetry"])]

    def _requirements(self, summary):
        return {"summary": summary, "skills": ["sql querying"],
                "tools": ["tableau"], "topics": []}

    def test_the_summary_leads_the_answer(self):
        body = _body(self._requirements(self.SUMMARY), self.CATALOG)
        assert body.startswith(self.SUMMARY)
        assert "MGTA 464" in body, "and the matches still follow"

    def test_the_refusal_says_what_the_field_wants_before_declining(self):
        body = _body(self._requirements(self.SUMMARY),
                     [_course("MGTA 2", title="Unrelated", skills=["poetry"])])
        assert self.SUMMARY in body
        assert "won't name a course without a catalog match" in body

    def test_a_missing_summary_leaves_no_blank_gap(self):
        for catalog in (self.CATALOG, [_course("MGTA 2", skills=["poetry"])]):
            body = _body(self._requirements(""), catalog)
            assert not body.startswith(("\n", " ")), repr(body[:20])
            assert "\n\n\n" not in body


from rsm_thrive.services.grounded_course_advisor.advisor import _target_field

_HEALTHCARE = {
    "skills": ["sql querying", "hipaa compliance"],
    "tools": ["sql", "tableau"],
    "topics": ["health informatics", "population health"],
    "summary": "",
}


class TestTheFieldTheStudentNamed:
    """Extraction has to survive the words around it. The pattern can match on
    several prepositions in one question, and since the field is matched whole
    -- every token present -- a single stray word credits nothing at all."""

    def test_a_pronoun_and_verb_are_not_part_of_the_field(self):
        # Matches at "help" (capturing "me work in healthcare analytics") and at
        # "in". The shorter, meaningful one wins.
        assert _target_field(
            "Which electives would help me work in healthcare analytics?"
        ) == "healthcare analytics"

    def test_a_trailing_program_mention_is_not_the_field(self):
        assert _target_field(
            "What electives can I take to assist in the aerospace field "
            "in the MSBA program?") == "aerospace"

    def test_a_question_naming_no_field_yields_none(self):
        assert _target_field("What electives are offered in the MSBA?") is None


class TestACourseAboutTheFieldAppears:
    """The catalog's own Healthcare Analytics course matches NONE of the two
    dozen requirements a healthcare search returns -- it teaches ICER and Markov
    cohorts against postings wanting SQL and Tableau. Under a skills-only
    threshold the one course named for the field was the one a student asking
    about it never saw."""

    CATALOG = [
        _course("MGTA 495", title="Special Topics: Healthcare Analytics",
                skills=["cost-effectiveness evaluation under uncertainty"],
                topics=["ICER", "Markov cohort models"], tools=["TreeAge Pro"]),
        _course("MGTA 464", title="SQL and ETL", tools=["SQL", "Tableau"],
                skills=["sql querying"]),
    ]

    def test_it_appears_on_the_field_alone_with_no_skill_overlap(self):
        fits = _rank(_HEALTHCARE, self.CATALOG, "healthcare analytics")
        assert "MGTA 495" in [fit.course["code"] for fit in fits], \
            "the course named for the field was dropped"

    def test_and_it_leads_even_though_another_course_scores_higher(self):
        fits = _rank(_HEALTHCARE, self.CATALOG, "healthcare analytics")
        assert fits[0].course["code"] == "MGTA 495"
        assert fits[0].domain

    def test_the_reply_says_why_it_is_there(self):
        body = _body(_HEALTHCARE, self.CATALOG, "healthcare analytics")
        assert "directly about this field" in body

    def test_without_a_field_it_is_excluded_as_before(self):
        fits = _rank(_HEALTHCARE, self.CATALOG)
        assert [fit.course["code"] for fit in fits] == ["MGTA 464"], \
            "no field means the ordinary threshold applies"


class TestAFieldThatNamesNothingIsIgnored:
    """A "field" fitting most of the catalog is not identifying a field.
    Admitting every course on that basis is worse than admitting none."""

    def _catalog(self):
        return [_course(f"MGTA {n}", title=f"Thing {n} Analytics",
                        skills=["sql querying"], tools=["SQL", "Tableau"])
                for n in range(MAX_RESULTS + 2)]

    def test_a_generic_field_credits_nobody(self):
        fits = _rank(_HEALTHCARE, self._catalog(), "analytics")
        assert not any(fit.domain for fit in fits), \
            "'analytics' credited courses it does not identify"

    def test_a_specific_field_still_credits(self):
        catalog = self._catalog()
        catalog.append(_course("MGTA 495",
                               title="Special Topics: Healthcare Analytics"))
        fits = _rank(_HEALTHCARE, catalog, "healthcare analytics")
        assert fits[0].course["code"] == "MGTA 495" and fits[0].domain


import json as _json

import pytest as _pytest

from rsm_thrive.services import role_lookup
from rsm_thrive.services.grounded_course_advisor.advisor import _requirements


class _RecordingLLM:
    """Distinguishes `chat` from `search_chat`, which `FakeLLM` cannot.

    `FakeLLM` inherits the base `LLM.search_chat`, and the base delegates to
    `chat`. So a caller switched from `search_chat` to `chat` -- an easy thing
    to do while trimming latency -- keeps every existing test green while
    silently giving up the web grounding it was built on.
    """

    def __init__(self, reply):
        self._reply = reply
        self.used = []

    def chat(self, system, messages, json_mode=False):
        self.used.append("chat")
        return self._reply

    def search_chat(self, system, messages, json_mode=False, sources_out=None,
                    search_query=None):
        # `sources_out` is accepted and ignored: this double stands in for a
        # backend, and what a real one puts there is `websearch`'s business,
        # tested in `test_websearch.py`.
        self.used.append("search_chat")
        return self._reply


class TestTheGroundingIsActuallyRequested:
    """Both callers promise an answer grounded in current postings. Neither had
    a test that they ask for the web at all."""

    REQUIREMENTS = _json.dumps({
        "summary": "s", "skills": ["sql"], "tools": ["python"], "topics": ["ehr"]})

    def test_the_advisor_searches_rather_than_recalling(self):
        llm = _RecordingLLM(self.REQUIREMENTS)
        assert _requirements(llm, "electives for healthcare") is not None
        assert llm.used == ["search_chat"], \
            "the advisor answered from training memory, not the web"

    def test_role_lookup_searches_rather_than_recalling(self):
        llm = _RecordingLLM(_json.dumps({
            "known": True, "role": "data scientist", "summary": "s",
            "skills": ["sql"], "tools": ["python"], "topics": ["ml"]}))
        assert role_lookup.skills_for_role(llm, "data scientist") is not None
        assert llm.used == ["search_chat"]

    def test_a_backend_that_cannot_search_still_answers(self):
        # The documented fallback: LLM.search_chat delegates to chat, so a
        # backend without web access degrades instead of failing.
        from rsm_thrive.services.llm import FakeLLM

        fake = FakeLLM(replies=[self.REQUIREMENTS])
        assert _requirements(fake, "electives for healthcare") is not None


from rsm_thrive.services.grounded_course_advisor import advisor as _advisor


class _CountingLLM:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0

    def search_chat(self, system, messages, json_mode=False, sources_out=None,
                    search_query=None):
        self.calls += 1
        if not self._replies:
            raise RuntimeError("exhausted")
        return self._replies.pop(0)

    chat = search_chat


@_pytest.fixture(autouse=True)
def _cold_cache():
    _advisor.reset_requirements_cache()
    yield
    _advisor.reset_requirements_cache()


class TestAFieldIsLookedUpOnceNotEveryTurn:
    """Measured on the live backend: 8.3s per lookup, of which the web search is
    3.4s. Re-running it for every student who asks about healthcare buys the
    same answer at full price."""

    PAYLOAD = _json.dumps({"summary": "s", "skills": ["sql"],
                           "tools": ["python"], "topics": ["ehr"]})

    def test_the_same_field_is_not_searched_twice(self):
        llm = _CountingLLM([self.PAYLOAD])
        q = "electives for healthcare analytics"
        assert _advisor._cached_requirements(llm, q, "healthcare analytics")
        assert _advisor._cached_requirements(llm, q, "healthcare analytics")
        assert llm.calls == 1

    def test_a_differently_worded_question_shares_the_lookup(self):
        # Keyed on the field, not the question: these are the same question
        # about the same industry.
        llm = _CountingLLM([self.PAYLOAD])
        _advisor._cached_requirements(
            llm, "electives for healthcare analytics", "healthcare analytics")
        _advisor._cached_requirements(
            llm, "which electives would help me work in healthcare analytics?",
            "healthcare analytics")
        assert llm.calls == 1

    def test_a_different_field_is_looked_up_on_its_own(self):
        llm = _CountingLLM([self.PAYLOAD, self.PAYLOAD])
        _advisor._cached_requirements(llm, "q", "healthcare analytics")
        _advisor._cached_requirements(llm, "q", "supply chain")
        assert llm.calls == 2

    def test_a_stale_entry_is_looked_up_again(self):
        llm = _CountingLLM([self.PAYLOAD, self.PAYLOAD])
        _advisor._cached_requirements(llm, "q", "healthcare analytics")
        # Age the stored entry rather than patching the clock: `_advisor.time`
        # IS the stdlib module, so a lambda calling through it recurses.
        stamp, value = _advisor._CACHE["healthcare analytics"]
        _advisor._CACHE["healthcare analytics"] = (
            stamp - _advisor._CACHE_TTL_SECONDS - 1, value)
        _advisor._cached_requirements(llm, "q", "healthcare analytics")
        assert llm.calls == 2, "a day-old answer was served as current"

    def test_a_failed_lookup_is_not_cached(self):
        # Caching a failure would mean one bad turn poisons the field for a day.
        llm = _CountingLLM(["not json at all", self.PAYLOAD])
        assert _advisor._cached_requirements(llm, "q", "healthcare analytics") is None
        assert _advisor._cached_requirements(llm, "q", "healthcare analytics")
        assert llm.calls == 2

    def test_the_cache_cannot_grow_without_bound(self):
        # The key comes from student text, so typos each make an entry.
        llm = _CountingLLM([self.PAYLOAD] * (_advisor._CACHE_MAX_FIELDS + 10))
        for n in range(_advisor._CACHE_MAX_FIELDS + 10):
            _advisor._cached_requirements(llm, "q", f"field {n}")
        assert len(_advisor._CACHE) <= _advisor._CACHE_MAX_FIELDS
