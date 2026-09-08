"""Careers the catalog curates no bundle for.

`careers.json` holds fourteen. A student can name anything: "esports analyst",
"aerospace engineer", "sports scientist", "climate risk modeller". The web
lookup describes the job, `skill_match` decides which of OUR courses teach it,
and the model never picks a course — that part already worked.

What did not: the answer was a dead end. Measured live, "esports analyst"
produced a good grounded list of four courses and then, on the very next turn,
asked the student what they were aiming for — the career they had just named —
and no plan of study was ever reached. An uncurated career is still a career.

The second defect here was a lie rather than a gap. "Aerospace engineer" names
a JOB; the classifier called it an industry because "aerospace" is a field
word; `is_industry_course_question` then declined to run at all (no catalog
word in the question), and the reply came back in 1.8 seconds saying "I
searched for what that field currently asks for" — a claim about a search that
had not happened.
"""

import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import Conversation
from rsm_thrive.services import orchestrator, planner, router
from rsm_thrive.services.grounded_course_advisor import advisor
from rsm_thrive.services.llm import FakeLLM

pytestmark = pytest.mark.django_db

UNCURATED = ["esports analyst", "aerospace engineer", "sports scientist",
             "climate risk modeller", "wildlife biologist", "sommelier",
             "esports analsyt", "airscpae engineer"]


@pytest.fixture
def user():
    return User.objects.create_user("stu")


@pytest.fixture
def conversation(user):
    return Conversation.objects.create(user=user, destination="courses",
                                        title="planning")


def job(role, skills, tools=(), topics=()):
    return json.dumps({"known": True, "role": role, "summary": f"{role} work.",
                       "skills": list(skills), "tools": list(tools),
                       "topics": list(topics)})


NOT_A_JOB = json.dumps({"known": False, "role": "", "summary": "",
                        "skills": [], "tools": [], "topics": []})

# A job this catalog genuinely serves some of.
SERVED = job("esports analyst",
             ["sql", "dashboards", "data storytelling", "experiment design",
              "statistical analysis"], tools=["tableau", "python"])
# A job it does not.
UNSERVED = job("sommelier", ["viticulture", "oenology", "wine pairing"],
               topics=["wine regions"])


class TestTheyDoNotFuzzyMatchACuratedRole:
    """A character of slop must not turn someone else's career into one of
    ours. "sports scientist" and "data scientist" share a word."""

    @pytest.mark.parametrize("said", UNCURATED)
    def test_none_of_them_resolve_to_a_curated_id(self, said):
        assert router.role_match(said) == ("", False), said

    def test_specifically_not_data_scientist(self):
        for said in ("sports scientist", "esports analyst", "sport scientist"):
            assert router.matched_role(said) != "data-scientist", said

    def test_but_a_real_typo_of_a_curated_one_still_does(self):
        """The line between the two: "data scienist" is a misspelling of a
        curated title, "sports scientist" is a different job."""
        assert router.matched_role("data scienist") == "data-scientist"


class TestTheGoalIsRemembered:
    """The dead end. The reply was good and the conversation could not
    continue from it."""

    def _named(self, conversation, role_json=SERVED):
        return orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.9, "role": "esports analyst"}',
                     role_json, "Here is what the catalog offers…"]),
            conversation, "I want to be an esports analyst", [])

    def test_it_stores_the_career_in_the_students_own_words(self, conversation):
        self._named(conversation)
        answers = planner.load_session_intake(conversation)
        assert answers["unmatched_goal"] == "esports analyst"
        assert answers["goal_courses"], "the matched courses were not kept"

    def test_it_asks_for_the_track_rather_than_stopping(self, conversation):
        reply = self._named(conversation)
        assert "11-month" in reply.body and "17-month" in reply.body
        assert "build the whole plan of study" in reply.body

    def test_the_next_turn_does_not_re_ask_the_career(self, conversation):
        self._named(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation, "11 month", [])
        assert "What are you aiming for" not in reply.body
        assert "starting from technically" in reply.body, "it moved on"

    def test_and_the_flow_reaches_a_real_plan(self, conversation):
        self._named(conversation)
        orchestrator.answer(FakeLLM([]), conversation, "11 month", [])
        orchestrator.answer(FakeLLM([]), conversation, "skip", [])
        reply = orchestrator.answer(FakeLLM([]), conversation, "moderate", [])
        assert "MSBA plan of study — esports analyst" in reply.body
        assert "50 units" in reply.body

    def test_the_plan_is_legal_and_built_around_what_was_matched(self, conversation):
        self._named(conversation)
        answers = planner.load_session_intake(conversation)
        answers = {**answers, "track": "11 month", "workload": "moderate",
                   **{f"skill_{a['key']}": 3 for a in planner.SKILL_AREAS}}
        pinned = planner.selections_for_courses(answers, answers["goal_courses"])
        plan = planner.build_for(answers, frozenset(), pinned)
        assert plan["totals"]["total"] == planner.TOTAL_UNITS
        assert plan["unfilled"] == []
        placed = planner.elective_codes(plan)
        catalog = {c["id"]: c for c in planner.load_catalog()}
        pinnable = [cid for cid in answers["goal_courses"]
                    if not catalog[cid]["is_core"]]
        assert any(catalog[cid]["code"] in placed for cid in pinnable), \
            "none of the matched courses reached the plan"

    def test_a_job_the_catalog_cannot_serve_still_refuses(self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.9, "role": "sommelier"}',
                     UNSERVED]),
            conversation, "I want to be a sommelier", [])
        assert reply.refused is True
        assert "MGTA" not in reply.body and "CSE" not in reply.body
        assert "advising" in reply.body.lower()
        assert not planner.load_session_intake(conversation).get("unmatched_goal")

    def test_something_that_is_not_a_job_is_not_stored_as_one(self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.9, "role": "banana"}',
                     NOT_A_JOB]),
            conversation, "banana", [])
        assert reply.refused is True
        assert not planner.load_session_intake(conversation).get("unmatched_goal")


class TestAJobIsNotAnIndustry:
    """"Aerospace engineer" came back in 1.8s claiming a search it never ran."""

    def test_the_industry_lookup_genuinely_declines_such_a_question(self):
        assert not advisor.is_industry_course_question("aerospace engineer")
        assert advisor.is_industry_course_question(
            "what electives help me work in the aerospace industry?")

    def test_it_falls_through_to_the_role_path_instead_of_refusing(
            self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "industry", "confidence": 0.9, "industry": "aerospace"}',
                     job("aerospace engineer",
                         ["systems engineering", "statistical analysis",
                          "sql", "data storytelling", "forecasting"],
                         tools=["python"]),
                     "Here is what the catalog offers…"]),
            conversation, "aerospace engineer", [])
        assert not reply.refused
        assert "I searched for what that field currently asks for" not in reply.body
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "aerospace engineer"

    def test_and_a_field_nothing_serves_still_refuses_honestly(self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "industry", "confidence": 0.9, "industry": "wine"}',
                     UNSERVED]),
            conversation, "sommelier", [])
        assert reply.refused is True
        assert "MGTA" not in reply.body

    def test_a_real_industry_question_still_goes_to_the_industry_path(
            self, conversation, monkeypatch):
        from rsm_thrive.services import orchestrator as orch

        monkeypatch.setattr(
            orch, "recommend_for_question",
            lambda llm, q: ("- **MGTA 464 — SQL** (2 units): matches sql.",
                            ["MGTA 464"]))
        reply = orch.answer(
            FakeLLM(['{"route": "industry", "confidence": 0.9, "industry": "healthcare"}']),
            conversation, "which electives help me work in healthcare?", [])
        assert reply.route == router.INDUSTRY
        assert "MGTA 464" in reply.body


class TestPinningWhatWasMatched:
    ANSWERS = {"track": "11 month", "unmatched_goal": "esports analyst",
               "workload": "moderate",
               **{f"skill_{a['key']}": 3 for a in planner.SKILL_AREAS}}

    def test_an_uncurated_goal_completes_the_intake(self):
        """A student who says "esports analyst" HAS told us what they are
        aiming for. Treating that as "no goal" is what left them answering the
        question they had just answered."""
        assert planner.next_intake_step(self.ANSWERS) is None

    def test_a_course_is_only_pinned_where_it_legally_fits(self):
        catalog = {c["id"]: c for c in planner.load_catalog()}
        selections = planner.selections_for_courses(
            self.ANSWERS, [c["id"] for c in planner.load_catalog()[:20]])
        skeleton = planner.effective_skeleton(self.ANSWERS)
        by_key = {q["key"]: q for q in skeleton}
        for quarter_key, slots in selections.items():
            quarter = by_key[quarter_key]
            for index, course_id in slots.items():
                slot = quarter["slots"][int(index)]
                assert slot["kind"] == "elective"
                assert catalog[course_id]["units"] == slot["units"]
                seasons = {o["season"] for o in catalog[course_id]["offerings"]}
                assert quarter["season"] in seasons

    def test_nothing_is_pinned_twice(self):
        selections = planner.selections_for_courses(
            self.ANSWERS, [c["id"] for c in planner.load_catalog()])
        placed = [cid for slots in selections.values() for cid in slots.values()]
        assert len(placed) == len(set(placed))

    @pytest.mark.parametrize("junk", [
        [], None, ["nope"], ["MGTA 451"], ["MGTA 999", "MGTA 464"],
        [c["id"] for c in planner.load_catalog()],
    ])
    def test_no_set_of_courses_can_break_the_plan(self, junk):
        """`goal_courses` comes from a web-driven match. A core course, a
        stale id or the whole catalog must all still produce a legal plan."""
        pinned = planner.selections_for_courses(self.ANSWERS, junk)
        plan = planner.build_for(self.ANSWERS, frozenset(), pinned)
        assert plan["totals"]["total"] == planner.TOTAL_UNITS, junk
        assert plan["unfilled"] == [], junk

    def test_a_core_course_is_never_pinned_into_an_elective_slot(self):
        core = [c["id"] for c in planner.load_catalog() if c["is_core"]]
        assert planner.selections_for_courses(self.ANSWERS, core) == {}

    def test_a_course_already_taken_is_not_pinned(self):
        taken = {"MGTA 457"}
        selections = planner.selections_for_courses(
            self.ANSWERS, ["MGTA 457", "MGTA 464"], taken)
        assert "MGTA 457" not in [cid for slots in selections.values()
                                  for cid in slots.values()]

    def test_the_placement_is_deterministic(self):
        courses = ["MGTA 457", "MGTA 464", "MGT 451", "MGTA 463"]
        first = planner.selections_for_courses(self.ANSWERS, courses)
        assert first == planner.selections_for_courses(self.ANSWERS, courses)


class TestItDoesNotInventTheJob:
    """"What about something in esports" came back as a full recommendation
    for **esports operations coordinator** — a job title the student had not
    said, followed by a list of "your target requirements" they had never
    given. The recommendation was good and it was for somebody else's career.
    """

    # Every turn starts with `router.classify`, so a scripted run needs the
    # classifier's reply before the lookup's.
    ROUTE_ROLE = ('{"route": "role", "confidence": 0.8, "role": "esports", '
                  '"industry": "esports"}')

    VAGUE = [ROUTE_ROLE,
             job("esports operations coordinator",
                 ["team logistics", "event planning", "sql"]),
             "Here is what the catalog offers…"]

    def test_the_head_noun_is_what_decides(self):
        """The job FUNCTION is what gets invented. A misspelled domain word is
        not the same thing, and neither is a spelling variant."""
        f = orchestrator.invented_job_function
        assert f("what about something in esports",
                 "esports operations coordinator") == "coordinator"
        assert f("I want to work in healthcare", "clinical data analyst") == "analyst"
        assert f("airscpae engineer", "aerospace engineer") == ""
        assert f("climate risk modeller", "climate risk modeler") == ""
        assert f("wildlife biologist", "wildlife biologist") == ""
        assert f("actuary", "actuary") == ""

    def test_it_asks_instead_of_recommending(self, conversation):
        reply = orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                                    "what about something in esports", [])
        assert "what kind of work do you want to do in it" in reply.body
        assert "my reading rather than something you said" in reply.body
        assert "MGTA" not in reply.body, "it recommended before asking"

    def test_the_guess_is_offered_not_asserted(self, conversation):
        reply = orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                                    "what about something in esports", [])
        assert "esports operations coordinator" in reply.body
        assert "I could read that as" in reply.body

    def test_nothing_is_stored_as_the_goal_yet(self, conversation):
        orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                            "what about something in esports", [])
        answers = planner.load_session_intake(conversation)
        assert not answers.get("unmatched_goal"), "committed to an invented job"
        assert answers.get("suggested_goal") == "esports operations coordinator"

    def test_accepting_the_guess_proceeds_with_it(self, conversation):
        orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                            "what about something in esports", [])
        # No classifier reply: a turn answering the question we just asked goes
        # straight back to that question, which also saves the round trip.
        reply = orchestrator.answer(
            FakeLLM([job("esports operations coordinator",
                         ["team logistics", "sql", "dashboards", "forecasting"]),
                     "Here is what the catalog offers…"]),
            conversation, "yes", [])
        assert not reply.refused
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "esports operations coordinator"

    def test_answering_with_a_real_title_keeps_the_students_words(self, conversation):
        """The same invention, one turn later: a student who answered with
        "esports analyst" was told "I don't have a set recommendation ready for
        DATA ANALYST" — after they had explicitly said what they meant."""
        orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                            "what about something in esports", [])
        reply = orchestrator.answer(
            FakeLLM([job("data analyst",          # the model renames it again
                         ["sql", "dashboards", "statistical analysis",
                          "data storytelling"]),
                     "Here is what the catalog offers…"]),
            conversation, "esports analyst", [])
        assert "esports analyst" in reply.body
        assert "data analyst" not in reply.body.split("---")[0].lower()
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "esports analyst"

    def test_it_never_asks_twice(self, conversation):
        orchestrator.answer(FakeLLM(self.VAGUE), conversation,
                            "what about something in esports", [])
        assert planner.session_has_asked(conversation, "what-work")
        for _ in range(3):
            reply = orchestrator.answer(
                FakeLLM([self.ROUTE_ROLE,
                         job("some other job", ["sql", "forecasting",
                                                "dashboards", "statistics"]),
                         "Here is what the catalog offers…"]),
                conversation, "what about something in esports", [])
            assert "what kind of work" not in reply.body

    def test_a_clear_job_title_is_never_questioned(self, conversation):
        """It must not start interrogating people who said what they meant."""
        reply = orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.9, "role": "esports analyst"}',
                     job("esports analyst", ["sql", "dashboards",
                                             "statistical analysis", "python"]),
                     "Here is what the catalog offers…"]),
            conversation, "I want to be an esports analyst", [])
        assert "what kind of work" not in reply.body
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "esports analyst"


class TestItIsARecommendationNotACuratedRuling:
    """It is advice. Calling it "a curated mapping, not a guess" claims more
    standing than it has — a student could reasonably read that as the
    programme's official position on their career."""

    def test_the_role_answer_says_recommend(self):
        body = orchestrator.curated_recommendation("consultant")
        assert "Here's what I'd recommend" in body
        assert "curated" not in body.lower()

    def test_the_plan_line_says_recommend(self):
        plan = planner.build_for(
            {"track": "11 month", "goals": ["consultant"],
             **{f"skill_{a['key']}": 3 for a in planner.SKILL_AREAS}}, frozenset())
        body = planner.render_plan_markdown(plan)
        assert "electives I'd recommend for that career" in body
        assert "a recommendation, not a requirement" in body
        assert "curated" not in body.lower()

    def test_the_uncurated_opening_says_recommendation(self, conversation):
        assert "curated" not in orchestrator.UNCOVERED_ROLE_PREFIX.lower()
        assert "set recommendation ready" in orchestrator.UNCOVERED_ROLE_PREFIX

    def test_no_student_facing_string_says_curated(self):
        """The word is fine in the code's own explanation of where the mapping
        came from; it must not reach the screen."""
        for text in (orchestrator.UNCOVERED_ROLE_PREFIX,
                     orchestrator.NO_INDUSTRY_MATCH, orchestrator.OUT_OF_SCOPE,
                     orchestrator.UNCLEAR, orchestrator.UNCLEAR_OPENING,
                     orchestrator.ASK_FOR_A_LOAD, orchestrator.ASK_FOR_SKILLS,
                     orchestrator.ASK_FOR_A_GOAL, planner.OPENING):
            assert "curated" not in text.lower(), text[:60]
        for role_id in planner.load_careers():
            assert "curated" not in orchestrator.curated_recommendation(
                role_id).lower(), role_id


class TestThePlanOffersOnlyWhatExists:
    ANSWERS = {"track": "11 month", "unmatched_goal": "esports analyst",
               "workload": "moderate",
               **{f"skill_{a['key']}": 3 for a in planner.SKILL_AREAS}}

    def test_no_bundle_means_no_offer_to_switch_to_one(self):
        """It said "say use the recommended bundle" under a plan for a career
        that has no bundle — an instruction that could not work."""
        body = planner.render_plan_markdown(
            planner.build_for(self.ANSWERS, frozenset()))
        assert "use the recommended bundle" not in body
        assert "no ready-made set for that career" in body

    def test_a_curated_career_on_the_scored_route_still_gets_the_offer(self):
        body = planner.render_plan_markdown(planner.build_for(
            {**self.ANSWERS, "unmatched_goal": "", "goals": ["data-scientist"],
             "route": "custom"}, frozenset()))
        assert "use the recommended bundle" in body

    def test_and_the_button_agrees_with_the_line(self):
        """`route_switch_reply` already guarded this; the prose did not."""
        assert planner.route_switch_reply(self.ANSWERS) == []
        assert planner.route_switch_reply(
            {**self.ANSWERS, "goals": ["data-scientist"], "route": "custom"})


class TestAVagueAreaIsPointedAtWhatWeActuallyHave:
    """The model's improvisation is often poor and ours is always relevant:
    "I want to work in healthcare" was met with "I could read that as
    **healthcare worker**" — for a programme with a hand-written Healthcare /
    Life Sciences Analytics set sitting right there."""

    def test_it_finds_the_curated_role_for_an_area(self):
        assert orchestrator.curated_near("healthcare") == \
            ["Healthcare / Life Sciences Analytics"]
        assert orchestrator.curated_near("marketing") == \
            ["Marketing / Growth Analytics"]
        assert orchestrator.curated_near("supply chain") == \
            ["Supply Chain / Operations Analytics"]

    def test_and_returns_nothing_for_an_area_we_do_not_curate(self):
        for area in ("esports", "aerospace", "wildlife", ""):
            assert orchestrator.curated_near(area) == [], area

    def test_the_ask_suggests_ours_rather_than_the_models_guess(self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.8, "role": "healthcare",'
                     ' "industry": "healthcare"}',
                     job("healthcare worker", ["patient care", "sql"])]),
            conversation, "I want to work in healthcare", [])
        assert "Healthcare / Life Sciences Analytics" in reply.body
        assert "healthcare worker" not in reply.body
        assert "ready-made set" in reply.body

    def test_and_accepting_it_lands_on_the_curated_bundle(self, conversation):
        orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.8, "role": "healthcare",'
                     ' "industry": "healthcare"}',
                     job("healthcare worker", ["patient care"])]),
            conversation, "I want to work in healthcare", [])
        assert planner.load_session_intake(conversation)["suggested_goal"] == \
            "Healthcare / Life Sciences Analytics"

        reply = orchestrator.answer(FakeLLM([]), conversation,
                                    "healthcare analyst", [])
        assert planner.load_session_intake(conversation)["goals"] == \
            ["healthcare-analyst"]
        assert "Here's what I'd recommend" in reply.body

    def test_an_area_we_do_not_curate_still_offers_the_models_reading(
            self, conversation):
        reply = orchestrator.answer(
            FakeLLM(['{"route": "role", "confidence": 0.8, "role": "esports",'
                     ' "industry": "esports"}',
                     job("esports event manager", ["event planning", "sql"])]),
            conversation, "what about something in esports", [])
        assert "esports event manager" in reply.body
        assert "my reading rather than something you said" in reply.body


class TestTheQuestionOwnsTheNextTurn:
    """A student answered "what kind of work do you want to do in it?" with
    **yup** and was handed the generic opening as though they had said nothing.

    "yup" was not on the acceptance list — but a longer list is not the fix,
    because the next word off it would have done the same. A question we asked
    one turn ago owns the next turn unless that turn is plainly about something
    else. Same rule the situational route already follows.
    """

    ROUTE_ROLE = ('{"route": "role", "confidence": 0.8, "role": "esports", '
                  '"industry": "esports"}')
    ASKED = [ROUTE_ROLE, job("esports operations manager",
                             ["team logistics", "event planning", "sql"])]

    def _asked(self, conversation):
        reply = orchestrator.answer(FakeLLM(self.ASKED), conversation,
                                    "I want to do somthign in esports", [])
        assert "what kind of work" in reply.body
        return reply

    @pytest.mark.parametrize("said", [
        "yup", "yup!", "yes", "yeah", "yea", "y", "sure", "ok", "go ahead",
        "sounds good", "do it", "that works", "correct", "anything",
        "not sure", "you decide",
    ])
    def test_these_all_accept_the_reading(self, said):
        assert orchestrator._accepts_the_guess(said), said

    @pytest.mark.parametrize("said", ["yup", "sounds good", "go ahead", "y"])
    def test_accepting_it_carries_on_rather_than_starting_over(self, said,
                                                               conversation):
        self._asked(conversation)
        reply = orchestrator.answer(
            FakeLLM([job("esports operations manager",
                         ["team logistics", "sql", "dashboards", "forecasting"]),
                     "Here is what the catalog offers…"]),
            conversation, said, [])
        assert "what you're aiming for after the programme" not in reply.body, \
            f"{said}: fell back to the opening"
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "esports operations manager"

    def test_and_then_asks_for_the_track(self, conversation):
        """One step at a time: role settled, now the track."""
        self._asked(conversation)
        reply = orchestrator.answer(
            FakeLLM([job("esports operations manager",
                         ["team logistics", "sql", "dashboards", "forecasting"]),
                     "Here is what the catalog offers…"]),
            conversation, "yup", [])
        assert "11-month" in reply.body and "17-month" in reply.body

        after = orchestrator.answer(FakeLLM([]), conversation, "11 month", [])
        assert "starting from technically" in after.body

    def test_a_word_nobody_listed_still_returns_to_the_question(self, conversation):
        """The point of the structural fix: an unrecognised reply is treated as
        an answer to what was asked, not as a new topic."""
        self._asked(conversation)
        reply = orchestrator.answer(
            FakeLLM([job("esports data analyst",
                         ["sql", "dashboards", "statistical analysis"]),
                     "Here is what the catalog offers…"]),
            conversation, "the analytics side of it", [])
        assert "what you're aiming for after the programme" not in reply.body
        assert planner.load_session_intake(conversation)["unmatched_goal"] \
            == "analytics", "the sentence around the answer came with it"

    def test_but_a_different_subject_is_still_allowed_through(self, conversation):
        """It must not trap someone who has changed their mind."""
        self._asked(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation,
                                    "actually, I want to be a data scientist", [])
        assert planner.load_session_intake(conversation)["goals"] == ["data-scientist"]

    def test_and_a_course_question_is_still_answered(self, conversation):
        self._asked(conversation)
        reply = orchestrator.answer(FakeLLM(["MGTA 464 is a 2-unit course."]),
                                    conversation, "how many units is MGTA 464", [])
        assert reply.route == router.FACTUAL

    def test_the_suggestion_does_not_capture_later_turns(self, conversation):
        self._asked(conversation)
        orchestrator.answer(
            FakeLLM([job("esports operations manager",
                         ["team logistics", "sql", "dashboards", "forecasting"]),
                     "Here is what the catalog offers…"]),
            conversation, "yup", [])
        assert not planner.load_session_intake(conversation).get("suggested_goal")

    def test_the_offer_describes_what_the_words_actually_do(self, conversation):
        """It used to promise "say **anything** and I'll match what the field
        asks for across the board" — which is not what "anything" did."""
        reply = self._asked(conversation)
        assert "just say **yes**" in reply.body
        assert "across the board" not in reply.body

    def test_a_refusal_does_not_capture_every_later_turn(self, conversation):
        """The worse bug the first fix introduced. Left set, the suggestion
        went on owning every turn: "yup", "11 month", "skip" and "moderate"
        each came back with the same refusal paragraph, because the question
        was still capturing long after it had been answered."""
        self._asked(conversation)
        refused = orchestrator.answer(
            FakeLLM([job("esports operations manager",
                         ["viticulture", "oenology"])]),   # nothing matches
            conversation, "yup", [])
        assert refused.refused is True
        assert not planner.load_session_intake(conversation).get("suggested_goal")

        moved_on = orchestrator.answer(FakeLLM([]), conversation, "11 month", [])
        assert "guessing if I put a plan together" not in moved_on.body
        assert "aiming for" in moved_on.body, "it repeated the refusal"

    def test_the_track_turn_is_never_stolen_by_the_question(self, conversation):
        """"11 month" is the very next thing this route asks for."""
        self._asked(conversation)
        orchestrator.answer(
            FakeLLM([job("esports operations manager",
                         ["sql", "dashboards", "forecasting", "statistics"]),
                     "Here is what the catalog offers…"]),
            conversation, "yup", [])
        reply = orchestrator.answer(FakeLLM([]), conversation, "11 month", [])
        assert planner.load_session_intake(conversation)["track"] == "11 month"
        assert "starting from technically" in reply.body

    def test_the_whole_flow_runs_one_step_at_a_time(self, conversation):
        """The shape reported: vague area -> confirm -> track -> skills ->
        spread -> plan, with every step asking exactly one thing."""
        self._asked(conversation)
        steps = [
            ("yup", "11-month",
             FakeLLM([job("esports operations manager",
                          ["sql", "dashboards", "forecasting", "statistics"]),
                      "Here is what the catalog offers…"])),
            ("11 month", "starting from technically", FakeLLM([])),
            ("skip", "spread across the quarters", FakeLLM([])),
            ("moderate", "plan of study", FakeLLM([])),
        ]
        for said, expected, llm in steps:
            reply = orchestrator.answer(llm, conversation, said, [])
            assert expected in reply.body, f"{said!r} -> {reply.body[:90]!r}"
        assert "esports operations manager" in reply.body
        plan = planner.build_for(planner.load_session_intake(conversation),
                                 frozenset())
        assert plan["totals"]["total"] == planner.TOTAL_UNITS
        assert plan["unfilled"] == []


class TestWhicheverRouteTheClassifierPicks:
    """The same sentence went to `role` one run and `industry` the next.

    "I want to do somthign in esports" is a vague area with a typo, and which
    route the model calls it is not stable between runs. Every test here had
    scripted `role`, so the industry path was never exercised — and on that
    path `unmatched_role` is never set, so `_uncurated_role` was handed the raw
    sentence and asked the model to describe it as a job. It answered
    known=false, correctly, and the whole route collapsed into a refusal that
    had searched for nothing.
    """

    SAID = "I want to do somthign in esports"

    def route(self, name):
        return json.dumps({"route": name, "confidence": 0.8,
                           "role": "" if name == "industry" else "esports",
                           "industry": "esports"})

    @pytest.mark.parametrize("name", ["role", "industry", "combination"])
    def test_the_vague_area_is_asked_about_on_every_route(self, name, conversation):
        reply = orchestrator.answer(
            FakeLLM([self.route(name),
                     job("esports operations manager",
                         ["team logistics", "event planning", "sql"]),
                     "Here is what the catalog offers…"]),
            conversation, self.SAID, [])
        assert "what kind of work" in reply.body.lower(), name
        assert not reply.refused, name

    @pytest.mark.parametrize("name", ["role", "industry", "combination"])
    def test_and_never_claims_a_search_it_did_not_run(self, name, conversation):
        reply = orchestrator.answer(
            FakeLLM([self.route(name), NOT_A_JOB]), conversation, self.SAID, [])
        assert "I searched for what that field currently asks for" not in reply.body
        assert "MGTA" not in reply.body, name

    def test_the_area_is_what_gets_looked_up_not_the_sentence(self, conversation):
        """`ROLE_SYSTEM` asks the model to describe a JOB. Handed a sentence it
        says known=false, which is right and useless."""
        llm = FakeLLM([self.route("industry"),
                       job("esports operations manager", ["sql", "dashboards"]),
                       "…"])
        orchestrator.answer(llm, conversation, self.SAID, [])
        looked_up = llm.calls[1][1][0]["content"]
        assert looked_up == "esports", looked_up

    def test_with_no_industry_named_it_falls_back_to_the_students_words(
            self, conversation):
        llm = FakeLLM([json.dumps({"route": "role", "confidence": 0.8,
                                   "role": "", "industry": ""}),
                       job("something", ["sql"]), "…"])
        orchestrator.answer(llm, conversation, "I want to do somthign in esports", [])
        looked_up = llm.calls[1][1][0]["content"]
        assert looked_up == "somthign esports", looked_up
        assert "I want to" not in looked_up, "the sentence went through raw"
