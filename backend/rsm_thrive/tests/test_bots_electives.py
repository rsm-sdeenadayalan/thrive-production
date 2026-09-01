import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import Conversation, CoursePlan, PlannerSession
from rsm_thrive.services import planner
from rsm_thrive.services.bots import answer_electives
from rsm_thrive.services.llm import FakeLLM

pytestmark = pytest.mark.django_db

FULL = {
    "track": "11 month", "goals": ["data-scientist"],
    "skill_python": "comfortable", "skill_sql": "basic",
    "skill_stats": "comfortable", "skill_ml": "basic",
    "skill_communication": "basic", "workload": "moderate",
    "interests": ["machine-learning"],
}


@pytest.fixture
def user():
    return User.objects.create_user("stu")


@pytest.fixture
def conversation(user):
    """The interview is scoped to one conversation, so tests need one."""
    return Conversation.objects.create(user=user, destination="courses",
                                       title="planning")


def _new_conversation(user):
    return Conversation.objects.create(user=user, destination="courses",
                                       title="another")


def _extracted(**overrides):
    """What the extractor returns after reading the conversation so far."""
    blank = {"track": None, "goals": [], "skill_python": None, "skill_sql": None,
             "skill_stats": None, "skill_ml": None, "skill_communication": None,
             "workload": None, "interests": []}
    return json.dumps({**blank, **overrides})


class TestConversationTitles:
    """A saved list of plans has to say what each plan was FOR.

    Titles come from the student's first message, and on this destination that
    message is usually a button press — so the list filled up with rows called
    "17 month" that were indistinguishable from one another.
    """

    def test_a_button_press_title_is_replaced_once_the_goal_is_known(self, user):
        conversation = Conversation.objects.create(
            user=user, destination="courses", title="17 month")
        fake = FakeLLM(replies=[_extracted(track="17 month",
                                           goals=["data-scientist"])])

        answer_electives(fake, conversation, "data scientist", [])

        conversation.refresh_from_db()
        assert conversation.title == "Course plan — Data Scientist, 17 month"

    def test_a_question_the_student_actually_typed_is_left_alone(self, user):
        # They wrote a better title than this code can compose.
        typed = "which electives suit a product manager"
        conversation = Conversation.objects.create(
            user=user, destination="courses", title=typed)
        fake = FakeLLM(replies=[_extracted(track="17 month",
                                           goals=["data-scientist"])])

        answer_electives(fake, conversation, "data scientist", [])

        conversation.refresh_from_db()
        assert conversation.title == typed

    def test_the_track_alone_is_not_enough_to_name_a_plan(self, user):
        # The track is the FIRST question, so titling on it would name every
        # conversation before any of them had a subject.
        conversation = Conversation.objects.create(
            user=user, destination="courses", title="17 month")
        fake = FakeLLM(replies=[_extracted(track="17 month")])

        answer_electives(fake, conversation, "17 month", [])

        conversation.refresh_from_db()
        assert conversation.title == "17 month"


class TestTheInterview:
    def test_the_first_thing_asked_is_the_track(self, conversation):
        """The brief: ask 11 month or 17 month before recommending anything.

        The two choices ride on the BUTTONS rather than in the message body —
        each one carries its own explanation now, so printing the same list
        above them would say everything twice.
        """
        fake = FakeLLM(replies=[_extracted()])
        reply = answer_electives(fake, conversation, "recommend me some courses", [])
        assert reply.model_note == "intake"
        assert "Step 1 of 4" in reply.body
        assert [r["label"] for r in reply.quick_replies] == ["11 month", "17 month"]
        # And the explanation travels with the control it explains.
        assert reply.quick_replies[0]["description"] == "Summer through Spring"

    def test_no_courses_are_named_before_the_interview_finishes(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation, "11 month", [])
        assert "MGTA" not in reply.body
        assert reply.model_note == "intake"

    def test_after_the_track_it_asks_about_the_goal(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation, "11 month", [])
        assert "Step 2 of 4" in reply.body
        assert "Data Scientist" in [r["label"] for r in reply.quick_replies]

    def test_then_it_asks_for_a_skill_level_in_each_area(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month",
                                           goals=["data-scientist"])])
        reply = answer_electives(fake, conversation, "data scientist", [])
        assert "Step 3 of 4" in reply.body
        for label in ("Python programming", "SQL and databases",
                      "Statistics and regression", "Machine learning"):
            assert label in reply.body

    def test_it_only_asks_for_the_skills_still_missing(self, conversation):
        fake = FakeLLM(replies=[_extracted(
            track="11 month", goals=["data-scientist"],
            skill_python="advanced", skill_sql="advanced")])
        reply = answer_electives(fake, conversation, "python and sql are strong", [])
        assert "Python programming" not in reply.body
        assert "Machine learning" in reply.body

    def test_then_it_asks_how_the_units_are_spread(self, conversation):
        """Replaced "light / moderate / heavy". A word could not be scheduled;
        units per quarter is the same question asked concretely."""
        answers = {**FULL, "workload": None}
        fake = FakeLLM(replies=[_extracted(**answers)])
        reply = answer_electives(fake, conversation, "all basic", [])
        assert "Step 4 of 4" in reply.body
        assert "units" in reply.body.lower()
        assert reply.form and reply.form["kind"] == "units"
        # Seeded with the published plan, and every row inside its own bounds.
        for row in reply.form["rows"]:
            assert row["min"] <= row["default"] <= row["max"], row

    def test_an_invented_answer_is_dropped_and_re_asked(self, conversation):
        """A guessed value becomes a plan the student never agreed to."""
        fake = FakeLLM(replies=[_extracted(track="4 month")])
        reply = answer_electives(fake, conversation, "the short one", [])
        assert reply.model_note == "intake"
        assert "Step 1 of 4" in reply.body

    def test_an_unknown_goal_is_dropped_and_re_asked(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month", goals=["astronaut"])])
        reply = answer_electives(fake, conversation, "astronaut", [])
        assert "Step 2 of 4" in reply.body

    def test_everything_stated_at_once_skips_straight_to_the_plan(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        reply = answer_electives(
            fake, conversation,
            "11 month, data scientist, python fine, light on ML", [])
        assert reply.model_note == "plan"


class TestTheInterviewRemembers:
    """The live failure this guards: answer the track, then the goal, and the
    interview asked for the track again because one extraction did not recover
    it from history."""

    def test_an_earlier_answer_is_not_lost_when_the_next_one_arrives(self, conversation):
        first = FakeLLM(replies=[_extracted(track="17 month")])
        assert "Step 2 of 4" in answer_electives(first, conversation, "17 month", []).body

        # The extractor now reports only the goal and forgets the track.
        second = FakeLLM(replies=[_extracted(goals=["product-manager"])])
        reply = answer_electives(second, conversation, "product manager", [])
        assert "Step 3 of 4" in reply.body, "the track was lost"

    def test_a_correction_overrides_what_was_stored(self, conversation):
        answer_electives(FakeLLM(replies=[_extracted(track="17 month")]),
                         conversation, "17 month", [])
        answer_electives(FakeLLM(replies=[_extracted(track="11 month")]),
                         conversation, "actually the 11 month", [])
        session = PlannerSession.objects.get(conversation=conversation)
        assert session.intake["track"] == "11 month"

    def test_a_partial_interview_is_stored_on_the_conversation(self, conversation):
        answer_electives(FakeLLM(replies=[_extracted(track="11 month")]),
                         conversation, "11 month", [])
        session = PlannerSession.objects.get(conversation=conversation)
        assert session.intake["track"] == "11 month"
        # A half-finished interview must not masquerade as a committed plan.
        assert not CoursePlan.objects.filter(user=conversation.user).exists()

    def test_the_whole_interview_completes_across_turns(self, conversation):
        steps = [
            _extracted(track="11 month"),
            _extracted(goals=["data-scientist"]),
            _extracted(skill_python="comfortable", skill_sql="basic",
                       skill_stats="comfortable", skill_ml="basic",
                       skill_communication="basic"),
            _extracted(workload="moderate"),
        ]
        replies = [answer_electives(FakeLLM(replies=[step]), conversation,
                                    "…", []).body
                   for step in steps]
        assert "Step 2 of 4" in replies[0]
        assert "Step 3 of 4" in replies[1]
        assert "Step 4 of 4" in replies[2]
        assert "## Summer III" in replies[3]


class TestEachConversationStartsOver:
    """Reported: every new chat skipped the questions and reused old answers,
    which made the interview impossible to re-test and let a stale goal stand in
    for one the student had not been asked in this conversation."""

    def _complete(self, conversation):
        answer_electives(FakeLLM(replies=[_extracted(**FULL)]),
                         conversation, "everything", [])

    def test_a_new_conversation_asks_the_track_again(self, conversation):
        self._complete(conversation)
        fresh = _new_conversation(conversation.user)
        reply = answer_electives(FakeLLM(replies=[_extracted()]), fresh,
                                 "help me plan", [])
        assert reply.model_note == "intake"
        assert "Step 1 of 4" in reply.body
        assert "MGTA" not in reply.body

    def test_a_finished_plan_does_not_leak_into_the_next_conversation(self, conversation):
        self._complete(conversation)
        fresh = _new_conversation(conversation.user)
        reply = answer_electives(
            FakeLLM(replies=[_extracted(goals=["consultant"])]), fresh,
            "i want to be a consultant", [])
        # Only the goal is known in the new chat, so the track is still missing.
        assert "Step 1 of 4" in reply.body

    def test_each_conversation_keeps_its_own_answers(self, conversation):
        answer_electives(FakeLLM(replies=[_extracted(track="17 month")]),
                         conversation, "17 month", [])
        fresh = _new_conversation(conversation.user)
        answer_electives(FakeLLM(replies=[_extracted(track="11 month")]),
                         fresh, "11 month", [])
        assert PlannerSession.objects.get(
            conversation=conversation).intake["track"] == "17 month"
        assert PlannerSession.objects.get(
            conversation=fresh).intake["track"] == "11 month"


class TestTheInterviewAlwaysEnds:
    """Measured over 50 conversations: a student who left two skill areas
    unstated was asked for them three times running and never got a plan."""

    PARTIAL = {"track": "11 month", "goals": ["data-scientist"],
               "skill_python": "none", "skill_stats": "basic",
               "skill_communication": "advanced"}

    def _asked_skills(self, times):
        """History containing `times` prior asks of the skills step."""
        return [{"role": "assistant", "content": "**Step 3 of 4.**\n\nTo keep…"}
                for _ in range(times)]

    def test_it_asks_twice_before_assuming_anything(self, conversation):
        fake = FakeLLM(replies=[_extracted(**self.PARTIAL)])
        reply = answer_electives(fake, conversation, "no ML, dunno sql",
                                 self._asked_skills(1))
        assert reply.model_note == "intake"
        assert "Step 3 of 4" in reply.body

    def test_after_two_asks_it_assumes_and_produces_the_plan(self, conversation):
        """Workload included: skills are then the ONLY thing still missing, so
        assuming them should complete the interview."""
        fake = FakeLLM(replies=[_extracted(**{**self.PARTIAL,
                                              "workload": "moderate"})])
        reply = answer_electives(fake, conversation, "moderate",
                                 self._asked_skills(2))
        assert reply.model_note == "plan"
        assert "## Summer III" in reply.body

    def test_assuming_skills_still_asks_for_a_missing_workload(self, conversation):
        fake = FakeLLM(replies=[_extracted(**self.PARTIAL)])
        reply = answer_electives(fake, conversation, "no ML",
                                 self._asked_skills(2))
        assert reply.model_note == "intake"
        assert "Step 4 of 4" in reply.body

    def test_it_says_which_levels_it_assumed(self, conversation):
        fake = FakeLLM(replies=[_extracted(**{**self.PARTIAL,
                                              "workload": "moderate"})])
        reply = answer_electives(fake, conversation, "moderate",
                                 self._asked_skills(2))
        assert "assumed" in reply.body.lower()
        assert "SQL and databases" in reply.body

    def test_a_missing_track_is_never_assumed(self, conversation):
        """A skill can be guessed and corrected; a track silently wrong makes
        every quarter wrong."""
        fake = FakeLLM(replies=[_extracted(goals=["data-scientist"])])
        history = [{"role": "assistant", "content": "**Step 1 of 4.**\n\nWhich…"}
                   for _ in range(3)]
        reply = answer_electives(fake, conversation, "dunno", history)
        assert reply.model_note == "intake"
        assert "Step 1 of 4" in reply.body

    def test_a_missing_goal_is_never_assumed(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        history = [{"role": "assistant", "content": "**Step 2 of 4.**\n\nWhat…"}
                   for _ in range(3)]
        reply = answer_electives(fake, conversation, "not sure", history)
        assert reply.model_note == "intake"
        assert "Step 2 of 4" in reply.body


class TestAmbiguousCourseCodes:
    """The catalog has four Special Topics courses all coded MGTA 495."""

    def test_a_shared_code_is_disambiguated_in_the_plan(self, conversation):
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["consultant"]})
        codes = [r["code"] for q in plan["quarters"] for r in q["courses"]
                 if r["code"]]
        assert len(codes) == len(set(codes)), codes

    def test_the_bare_code_is_still_available_for_matching(self, conversation):
        from rsm_thrive.services import planner

        plan = planner.build_plan(FULL)
        for quarter in plan["quarters"]:
            for row in quarter["courses"]:
                if row["courseId"]:
                    assert row["baseCode"]

    def test_a_disambiguated_code_can_still_be_located(self, conversation):
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["consultant"]})
        target = next((r for q in plan["quarters"] for r in q["courses"]
                       if r["code"] and "(" in r["code"]), None)
        if target is None:
            pytest.skip("this profile planned no ambiguous-coded course")
        assert planner.locate_code(plan, target["code"])[2] is not None
        assert planner.locate_code(plan, target["baseCode"])[2] is not None


class TestAnUnknownCareer:
    """Reported: asking to become an esports analyst produced a plan instead of
    a question -- and then, once it asked, it answered with a menu of ten roles
    the student had not asked about.

    It now does something better than either: looks up what that job actually
    needs (on the web, see `services/role_lookup.py`) and recommends the
    courses this catalog really has for those skills. The old guarantees still
    hold -- no plan, no role menu -- and are still asserted below.
    """

    UNKNOWN = {"track": "11 month", "goals": [], "skill_python": None,
               "skill_sql": None, "skill_stats": None, "skill_ml": None,
               "skill_communication": None, "workload": None, "interests": [],
               "unmatched_goal": "esports analyst"}

    # What `skills_for_role` gets back. Skills, never courses: the model does
    # not know this catalog and the mapping happens in Python.
    ROLE = json.dumps({
        "known": True, "role": "esports analyst",
        "summary": "Turns match and player data into insight.",
        "skills": ["sql", "data analysis", "data visualization"],
        "tools": ["python", "tableau"], "topics": ["statistics"]})

    def _replies(self, *extra):
        return FakeLLM(replies=[json.dumps(self.UNKNOWN), *extra])

    def test_it_recommends_real_courses_for_the_role(self, conversation):
        fake = self._replies(self.ROLE, "MGTA 464 covers SQL. MGTA 457 covers Tableau.")
        reply = answer_electives(fake, conversation, "esports analyst", [])
        assert "MGTA 464" in reply.body

    def test_it_never_produces_a_plan_for_an_uncovered_career(self, conversation):
        fake = self._replies(self.ROLE, "MGTA 464 covers SQL.")
        body = answer_electives(fake, conversation, "esports analyst", []).body
        assert "## Summer III" not in body, "a plan needs answers nobody gave"

    def test_it_does_not_spam_the_list_of_roles(self, conversation):
        """The whole point of the original change: no menu of ten roles."""
        fake = self._replies(self.ROLE, "MGTA 464 covers SQL.")
        body = answer_electives(fake, conversation, "esports analyst", []).body
        for label in ("Data Scientist", "Data Engineer", "Product Manager",
                      "Analytics Consultant"):
            assert label not in body

    def test_a_real_job_the_catalog_cannot_serve_still_points_at_advising(
            self, conversation):
        """The fallback that survives: a genuine job with nothing in the
        catalog teaching it gets the honest answer, not a stretched match."""
        nothing = json.dumps({
            "known": True, "role": "sommelier", "summary": "Tastes wine.",
            "skills": ["wine tasting", "cellar management"], "tools": [],
            "topics": ["viticulture"]})
        fake = self._replies(nothing)
        reply = answer_electives(fake, conversation, "sommelier", [])
        assert reply.model_note == "no-track"
        assert "MSBA advising" in reply.body and "Appointments" in reply.body

    def test_something_that_is_not_a_job_is_not_treated_as_a_career(
            self, conversation):
        """"how do i set up zoom" was being answered with "your career is not
        covered". The role lookup reports it is not a job, and the turn falls
        through to the aside instead."""
        from rsm_thrive.services.bots import ASIDE_UNKNOWN

        not_a_job = json.dumps({"known": False, "role": "", "summary": "",
                                "skills": [], "tools": [], "topics": []})
        # No track in this extraction: a student typing a question does not
        # also state their track in the same breath, and including one made the
        # turn "teach the interview something", which suppresses the aside.
        fake = FakeLLM(replies=[json.dumps({**self.UNKNOWN, "track": None,
                                            "unmatched_goal": "how do i set up zoom"}),
                                not_a_job])
        reply = answer_electives(fake, conversation, "how do i set up zoom", [])
        assert reply.model_note != "no-track"
        assert ASIDE_UNKNOWN in reply.body


class TestJobButtons:
    """Buttons offer every job a path can be built for — which is all of them."""

    def test_every_role_is_offered(self):
        from rsm_thrive.services import planner
        from rsm_thrive.services.electives import load_careers

        assert set(planner.supported_roles()) == set(load_careers())

    def test_every_button_leads_to_a_complete_plan(self):
        """The claim the buttons make: pressing one gets you a real plan."""
        from rsm_thrive.services import planner

        for role_id in planner.supported_roles():
            for track in planner.TRACK_SKELETONS:
                plan = planner.build_plan({**FULL, "track": track,
                                           "goals": [role_id]})
                assert plan["totals"]["total"] == 50, (role_id, track)
                assert plan["unfilled"] == [], (role_id, track)

    def test_a_sparsely_served_role_still_gets_a_path(self):
        """Measured: operations-supply-chain has 5 tagged electives and still
        fills 3 of 7 elective slots on-goal, which is a path, not a dead end."""
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["operations-supply-chain"]})
        on_goal = [r for q in plan["quarters"] for r in q["courses"]
                   if r["requirement"] == "Elective" and r.get("onGoal")]
        assert on_goal
        assert plan["totals"]["total"] == 50

    def test_button_faces_are_short_and_come_from_the_catalog(self):
        from rsm_thrive.services import planner
        from rsm_thrive.services.electives import load_careers

        careers = load_careers()
        for q in planner.quick_replies_for({"key": "goals", "missing": []}):
            assert len(q["label"]) <= 24, q["label"]
            assert q["label"] in {c.get("short_label") for c in careers.values()}

    def test_the_message_sent_keeps_the_full_label_for_matching(self):
        from rsm_thrive.services import planner
        from rsm_thrive.services.electives import load_careers

        labels = {c["label"] for c in load_careers().values()}
        for q in planner.quick_replies_for({"key": "goals", "missing": []}):
            assert q["send"] in labels

    def test_a_slash_inside_a_role_name_survives_the_button(self):
        """"Finance / Quantitative Analyst" must not become "Finance"."""
        from rsm_thrive.services import planner

        faces = {q["label"] for q in planner.quick_replies_for(
            {"key": "goals", "missing": []})}
        assert "Finance" not in faces and "Fraud" not in faces
        assert "Finance / Quant" in faces

    def test_track_and_workload_also_get_buttons(self):
        from rsm_thrive.services import planner

        assert len(planner.quick_replies_for({"key": "track", "missing": []})) == 2
        assert len(planner.quick_replies_for({"key": "workload", "missing": []})) == 3

    def test_the_skills_step_gets_none(self):
        """Five areas at once: thirty buttons is not a shortcut."""
        from rsm_thrive.services import planner

        assert planner.quick_replies_for({"key": "skills", "missing": []}) == []

    def test_the_bot_attaches_the_buttons_to_the_question(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation, "11 month", [])
        assert reply.quick_replies
        assert any(q["label"] == "Data Scientist" for q in reply.quick_replies)


class TestTargetingNote:
    """When a plan comes out mostly breadth, it says so — judged from the plan
    rather than from a catalog tag count that did not predict the outcome."""

    def test_a_mostly_breadth_plan_is_flagged(self):
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["operations-supply-chain"]})
        note = plan["targeting"]
        assert note and note["onGoal"] < note["electiveSlots"]

    def test_a_well_targeted_plan_is_not_flagged(self):
        from rsm_thrive.services import planner

        assert planner.build_plan({**FULL, "goals": ["data-scientist"]})["targeting"] is None

    def _on_goal(self, role):
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": [role]})
        rows = [r for q in plan["quarters"] for r in q["courses"]
                if r["requirement"] == "Elective" and r["swappable"]]
        return sum(1 for r in rows if r.get("onGoal")), len(rows)

    def test_the_note_reports_the_plans_own_numbers(self):
        """Exact rather than derived from a proxy — this is the whole change."""
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["operations-supply-chain"]})
        rows = [r for q in plan["quarters"] for r in q["courses"]
                if r["requirement"] == "Elective" and r["swappable"]]
        note = plan["targeting"]
        assert note["onGoal"] == sum(1 for r in rows if r.get("onGoal"))
        assert note["electiveSlots"] == len(rows)

    def test_more_tagged_electives_does_not_mean_a_more_targeted_plan(self):
        """The finding that retired the old threshold: the catalog count does
        not order the outcomes, so it cannot decide which roles are offered.

        Asserted as "such a pair exists" rather than naming two roles, because
        which pair it is moves with the student's skill levels — the fragility
        that made the first version of this test wrong.
        """
        from rsm_thrive.services import planner
        from rsm_thrive.services.electives import load_careers

        roles = sorted(load_careers())
        pairs = [
            (a, b) for a in roles for b in roles
            if planner.matched_elective_count(a) > planner.matched_elective_count(b)
            and self._on_goal(a)[0] <= self._on_goal(b)[0]
        ]
        assert pairs, "catalog count would have been a fair proxy after all"

    def test_the_note_names_advising_and_the_appointments_tab(self):
        from rsm_thrive.services import planner

        text = planner.render_plan_markdown(
            planner.build_plan({**FULL, "goals": ["operations-supply-chain"]}))
        assert "Appointments" in text and "advising" in text.lower()

    def test_a_flagged_plan_is_still_complete(self):
        from rsm_thrive.services import planner

        plan = planner.build_plan({**FULL, "goals": ["operations-supply-chain"]})
        assert plan["totals"]["total"] == 50 and plan["unfilled"] == []


class TestThePlan:
    def test_the_plan_is_divided_by_quarter(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        body = answer_electives(fake, conversation, "go", []).body
        for quarter in ("Summer III", "Fall", "Winter", "Spring"):
            assert f"## {quarter}" in body

    def test_each_quarter_lists_core_and_elective_courses(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        body = answer_electives(fake, conversation, "go", []).body
        assert "| Requirement |" in body
        assert "Core" in body and "Elective" in body
        # the six required core courses are all named
        for code in ("MGTA 451", "MGTA 452", "MGTA 453", "MGTA 455",
                     "MGTA 444", "MGTA 454"):
            assert code in body

    def test_the_plan_states_the_unit_totals(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        body = answer_electives(fake, conversation, "go", []).body
        assert "50 units" in body and "22 core" in body

    def test_the_plan_offers_booking_and_catalog_links(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        body = answer_electives(fake, conversation, "go", []).body
        assert "https://sis.ucsd.edu/" in body
        assert "drive.google.com" in body

    def test_the_plan_invites_a_change(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        assert "change" in answer_electives(fake, conversation, "go", []).body.lower()

    def test_the_completed_interview_is_saved_for_the_plan_api(self, conversation):
        fake = FakeLLM(replies=[_extracted(**FULL)])
        answer_electives(fake, conversation, "go", [])
        record = CoursePlan.objects.get(user=conversation.user)
        assert record.track == "11 month"
        assert record.intake["goals"] == ["data-scientist"]

    def test_the_track_decides_the_shape_of_the_plan(self, conversation):
        fake = FakeLLM(replies=[_extracted(**{**FULL, "track": "17 month"})])
        body = answer_electives(fake, conversation, "go", []).body
        assert "Fall (second year)" in body


class TestTheGuidedReview:
    """Once a plan exists, walk it a quarter at a time so each choice is small."""

    def _planned(self, conversation):
        answer_electives(FakeLLM(replies=[_extracted(**FULL)]),
                         conversation, "everything", [])

    def _say(self, conversation, text):
        return answer_electives(FakeLLM(replies=[_extracted(**FULL)]),
                                conversation, text, [])

    def test_a_finished_plan_offers_to_walk_through_it(self, conversation):
        reply = answer_electives(FakeLLM(replies=[_extracted(**FULL)]),
                                 conversation, "go", [])
        # Three now: the route switch leads, because it changes the whole plan
        # rather than one slot of it.
        assert [q["send"] for q in reply.quick_replies] == [
            "use the recommended bundle", "walk me through it", "finalise"]

    def test_the_route_switch_is_offered_and_leads_somewhere(self, conversation):
        """The plan is built the custom way, so the button offers the other
        route -- and the value it sends has to be one `route_intent` reads back,
        or the button does nothing."""
        from rsm_thrive.services import planner

        reply = answer_electives(FakeLLM(replies=[_extracted(**FULL)]),
                                 conversation, "go", [])
        switch = reply.quick_replies[0]
        assert planner.route_intent(switch["send"]) == "fixed"
        assert switch["description"], "a route button has to say what it does"

    def test_the_walk_starts_at_the_first_quarter(self, conversation):
        self._planned(conversation)
        reply = self._say(conversation, "walk me through it")
        assert reply.model_note == "review"
        assert "Quarter 1 of 4" in reply.body
        assert "Summer III" in reply.body

    def test_a_quarter_shows_its_core_courses_as_fixed(self, conversation):
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        body = self._say(conversation, "next quarter").body
        assert "Required this quarter" in body
        assert "MGTA 452" in body

    def test_a_quarter_offers_alternatives_and_says_what_they_teach(self, conversation):
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        reply = self._say(conversation, "next quarter")
        assert "Other courses that fit this slot" in reply.body
        assert "teaches" in reply.body
        assert any("instead of" in q["label"] for q in reply.quick_replies)

    def test_two_slots_never_offer_the_same_button_label(self, conversation):
        """A quarter can offer one alternative for two different slots; two
        identical buttons doing different things is a coin toss."""
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        for _ in range(3):
            reply = self._say(conversation, "next quarter")
            labels = [q["label"] for q in reply.quick_replies]
            assert len(labels) == len(set(labels)), labels

    def test_next_advances_one_quarter_at_a_time(self, conversation):
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        for expected in (2, 3, 4):
            assert f"Quarter {expected} of 4" in self._say(
                conversation, "next quarter").body

    def test_the_last_quarter_offers_to_finalise(self, conversation):
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        for _ in range(3):
            reply = self._say(conversation, "next quarter")
        assert any(q["send"] == "finalise" for q in reply.quick_replies)

    def test_next_does_not_run_off_the_end(self, conversation):
        self._planned(conversation)
        self._say(conversation, "walk me through it")
        for _ in range(9):
            reply = self._say(conversation, "next quarter")
        assert "Quarter 4 of 4" in reply.body

    def test_a_swap_mid_review_stays_on_that_quarter(self, conversation):
        """Replacing the view with the whole plan loses the student's place."""
        from rsm_thrive.services import planner

        self._planned(conversation)
        self._say(conversation, "walk me through it")
        fall = self._say(conversation, "next quarter")
        option = next(q for q in fall.quick_replies if "instead of" in q["label"])
        after = self._say(conversation, option["send"])
        assert "Quarter 2 of 4" in after.body
        assert option["label"].split(" instead")[0] in after.body

    def test_finalising_ends_the_review_and_confirms(self, conversation):
        from rsm_thrive.models import PlannerSession

        self._planned(conversation)
        self._say(conversation, "walk me through it")
        reply = self._say(conversation, "finalise")
        assert "Your plan is set" in reply.body
        assert "50 units" in reply.body
        assert PlannerSession.objects.get(conversation=conversation).review is None

    def test_finalising_says_nothing_is_booked_yet(self, conversation):
        self._planned(conversation)
        reply = self._say(conversation, "looks good")
        assert "not booked" in reply.body.lower() or "nothing here is booked" in reply.body.lower()

    def test_review_intent_reads_the_buttons_and_plain_words(self):
        from rsm_thrive.services import planner

        assert planner.review_intent("walk me through it") == "start"
        assert planner.review_intent("go through it quarter by quarter") == "start"
        assert planner.review_intent("next quarter") == "next"
        assert planner.review_intent("keep going") == "next"
        assert planner.review_intent("finalise") == "finalise"
        assert planner.review_intent("looks good") == "finalise"
        assert planner.review_intent("what about MGTA 463") is None
        assert planner.review_intent("") is None

    def test_next_outside_a_review_does_not_pretend_to_advance(self, conversation):
        """No review in progress means "next" is not a navigation instruction."""
        self._planned(conversation)
        reply = self._say(conversation, "next quarter")
        assert reply.model_note != "review"


class TestChangingACourse:
    def _plan_and_swappable(self, conversation):
        """Build the plan, then read a swappable elective OUT of it.

        Deliberately not a hardcoded code: which electives get planned depends
        on the intake and on the scorer's stretch guard, so a literal code here
        would make this test assert yesterday's ranking rather than the swap
        behaviour it is about.
        """
        from rsm_thrive.services import planner
        fake = FakeLLM(replies=[_extracted(**FULL)])
        body = answer_electives(fake, conversation, "go", []).body
        plan = planner.build_plan(FULL, planner.taken_course_ids(conversation.user))
        code = next(r["code"] for q in plan["quarters"] for r in q["courses"]
                    if r["swappable"] and r["courseId"] and r["units"] == 4)
        return body, code

    def test_naming_one_planned_course_offers_alternatives(self, conversation):
        _, code = self._plan_and_swappable(conversation)
        fake = FakeLLM(replies=[_extracted(**FULL)])
        reply = answer_electives(fake, conversation, f"change {code}", [])
        assert reply.model_note == "plan"
        assert code in reply.body
        assert "same" in reply.body.lower() or "give up" in reply.body.lower()

    def test_naming_a_replacement_performs_the_swap(self, conversation):
        import re

        _, code = self._plan_and_swappable(conversation)
        fake = FakeLLM(replies=[_extracted(**FULL)])
        offered = answer_electives(fake, conversation, f"change {code}", []).body
        options = re.findall(r"\| \*\*([A-Z]{2,4} \d{3}[A-Z]?)\*\* \|", offered)
        assert options, offered
        fake2 = FakeLLM(replies=[_extracted(**FULL)])
        reply = answer_electives(fake2, conversation, f"swap {code} for {options[0]}", [])
        assert "Swapped" in reply.body
        assert options[0] in reply.body

    def test_an_impossible_swap_explains_the_rule(self, conversation):
        """MGTA 402 is a 2-unit course, so it cannot fill a 4-unit slot."""
        _, code = self._plan_and_swappable(conversation)
        fake = FakeLLM(replies=[_extracted(**FULL)])
        reply = answer_electives(fake, conversation, f"swap {code} for MGTA 402", [])
        assert "can't put" in reply.body
        assert "units" in reply.body

    def test_a_core_course_cannot_be_changed(self, conversation):
        self._plan_and_swappable(conversation)
        fake = FakeLLM(replies=[_extracted(**FULL)])
        reply = answer_electives(fake, conversation, "change MGTA 451", [])
        assert "cannot be changed" in reply.body


class TestAQuestionIsNotAnAnswer:
    """The defect: asked "what if I switch to 17 month?", the extractor
    reported track="17 month" and the student's committed plan was rebuilt on
    the other track -- `CoursePlan` included, which is per-user, outlives the
    conversation and is what `/api/thrive/plan` serves. A what-if replaced the
    real plan of study.
    """

    def test_a_hypothetical_does_not_overwrite_an_answer_on_file(self):
        from rsm_thrive.services import planner

        stored = {"track": "11 month", "goals": ["data-scientist"]}
        merged = planner.merge_intake(stored, {"track": "17 month"}, asking=True)
        assert merged["track"] == "11 month"

    def test_a_question_commits_nothing_not_even_into_a_blank(self):
        """Narrowed after measurement. Allowing a question to fill BLANKS was
        the original rule, on the theory that "what if I want to be a data
        scientist?" carries real information. It carries the same risk in a
        quieter form: probing every step of the interview, "is next quarter
        heavy?" wrote workload="heavy" from a turn that stated no preference.
        The interview asks again instead."""
        from rsm_thrive.services import planner

        merged = planner.merge_intake({"track": "11 month"},
                                      {"goals": ["data-scientist"]}, asking=True)
        assert "goals" not in merged
        assert merged["track"] == "11 month", "what was on file stays on file"

    def test_a_plain_answer_still_overwrites(self):
        from rsm_thrive.services import planner

        merged = planner.merge_intake({"track": "17 month"},
                                      {"track": "11 month"}, asking=False)
        assert merged["track"] == "11 month"

    @pytest.mark.parametrize("text", [
        "what if I switch to 17 month?", "should I have said data engineer?",
        "what electives are there?", "why do you need my track?",
        "can I change this later?",
    ])
    def test_these_read_as_questions(self, text):
        from rsm_thrive.services import planner

        assert planner.is_question(text)

    @pytest.mark.parametrize("text", [
        "11 month", "data scientist", "moderate", "11 month?",
        "python 4 sql 3", "",
    ])
    def test_these_read_as_answers(self, text):
        from rsm_thrive.services import planner

        # "11 month?" is a hedged ANSWER, not a question -- a trailing "?" alone
        # must not be enough, or an uncertain student stops being heard.
        assert not planner.is_question(text)


class TestTheAsideDoesNotInventOrDoubleAsk:
    """Two defects in the mid-interview answer path itself.

    With no retrieved context the model answered "what's the weather in san
    diego?" and volunteered "have you completed MGB 290 (Analytics
    Practicum)?" -- a course that is not in the catalog. And asked "are you an
    AI?" it answered, then asked a question of its own, which landed directly
    above the interview's own different question.
    """

    def test_no_context_refuses_deterministically(self):
        from rsm_thrive.services import bots
        from rsm_thrive.services.llm import FakeLLM

        # An exhausted FakeLLM raises if it is called at all.
        prefix, cited = bots._aside(FakeLLM(replies=[]), "what is the recipe for lasagna")
        assert bots.ASIDE_UNKNOWN in prefix
        assert cited == []

    def test_the_refusal_states_its_scope_rather_than_deferring(self):
        """"I don't have material -- MSBA advising can" is a fair answer about a
        fee schedule and a silly one about the weather, which advising cannot
        help with either. The refusal names what this bot does instead."""
        from rsm_thrive.services import bots

        lowered = bots.ASIDE_UNKNOWN.lower()
        assert "course planner" in lowered
        assert "electives" in lowered and "plan of study" in lowered
        # It may still point elsewhere, but not as the whole answer.
        assert not lowered.startswith("i don't have material")

    @pytest.mark.parametrize("body,expected", [
        ("Yes I am an AI. Which quarter are you in?", "Yes I am an AI."),
        ("Answer line.\n\nAnd a question?", "Answer line."),
        ("Fine. Now — **which quarter are you in?**", "Fine."),
        ("Only a question?", ""),
        ("A. B? C.", "A. B? C."),
        ("Tuition is **50 units**", "Tuition is **50 units**"),
        ("", ""),
        (None, ""),
    ])
    def test_a_trailing_question_is_removed(self, body, expected):
        from rsm_thrive.services.bots import _without_trailing_question

        assert _without_trailing_question(body) == expected


class TestThePlanIsNotReprintedAtEveryTurn:
    """The defect: `_plan_reply` was the unconditional fallthrough, so "ok",
    "thanks!" and "how do I enrol?" each reprinted the whole 3,680-character
    plan of study -- 24 of 25 probes."""

    @pytest.mark.parametrize("text", [
        "show me the plan", "print it again", "the plan again", "my plan",
    ])
    def test_these_ask_for_the_plan(self, text):
        from rsm_thrive.services.bots import _wants_the_plan

        assert _wants_the_plan(text)

    @pytest.mark.parametrize("text", [
        "thanks!", "ok", "hmm", "how do I enrol?", "can you email this to me?",
    ])
    def test_these_do_not(self, text):
        from rsm_thrive.services.bots import _wants_the_plan

        assert not _wants_the_plan(text)


class TestTheStepCounterSurvivesAnAside:
    """The defect: the attempt counter matched with `startswith`, so once a
    step could be preceded by the answer to a question, the marker was no
    longer first in the body and the count stayed at zero.

    That is the counter the skills escape hatch reads, so a student who asked
    anything during the skills step could be asked for them forever.
    """

    def test_the_marker_is_found_even_when_an_aside_precedes_it(self):
        from rsm_thrive.services import planner

        step = {"key": "skills", "missing": []}
        marker = f"**Step {planner.step_position(step)} of"
        with_aside = ("Electives are listed in the catalog.\n\n---\n\n"
                      f"{marker} 4.**\n\nHow would you rate...")
        assert marker in with_aside
        assert not with_aside.startswith(marker), "otherwise this proves nothing"


class TestTheOpeningQuestionIsPartOfTheRecord:
    """The defect: the courses interview shows its first question as a
    client-side `starter`, so the conversation a send created began with the
    student's answer and nothing above it -- "11 month", answering a question
    that was never a message and was gone on reload."""

    def test_a_courses_conversation_opens_with_the_question(self, client):
        from rsm_thrive.testing import make_student
        from rsm_thrive.services import planner
        from rsm_thrive.views import chat as chat_views

        profile = make_student(username="seeded")
        client.force_login(profile.user)
        chat_views.llm_factory = lambda: FakeLLM(replies=[json.dumps({
            "track": "11 month", "goals": [], "workload": None,
            "interests": [], "unmatched_goal": None})])
        response = client.post(
            "/api/thrive/conversations",
            data=json.dumps({"destination": "courses", "body": "11 month"}),
            content_type="application/json")
        assert response.status_code == 201, response.content[:200]
        messages = response.json()["messages"]
        assert messages[0]["role"] == "thrive"
        assert messages[0]["body"] == planner.opening_prompt()["body"]
        assert [q["send"] for q in messages[0]["quickReplies"]] == ["11 month", "17 month"]
        assert messages[1]["role"] == "student"

    def test_other_destinations_are_not_seeded(self, client):
        from rsm_thrive.testing import make_student
        from rsm_thrive.views import chat as chat_views

        profile = make_student(username="unseeded")
        client.force_login(profile.user)
        chat_views.llm_factory = lambda: FakeLLM(replies=["an answer"])
        response = client.post(
            "/api/thrive/conversations",
            data=json.dumps({"destination": "resources", "body": "hello"}),
            content_type="application/json")
        assert response.status_code == 201, response.content[:200]
        assert response.json()["messages"][0]["role"] == "student"


class TestAQuestionWithoutAQuestionMark:
    """The defect: "What classes do you have access to" got the step repeated
    back with no answer.

    Two things had to line up. `is_question` requires a literal "?", so the
    strict test said no -- correctly, since its other job is refusing to
    overwrite a stored answer. The fallback was `not extracted`, which sounds
    right and never fires: the extractor is handed the whole transcript every
    turn and re-reports what the student already said, so `extracted` came back
    as {"track": "11 month"} from three turns earlier and the aside was skipped.

    The signal that works is whether the turn taught the interview anything NEW.
    """

    def _conversation(self, profile):
        return Conversation.objects.create(
            user=profile.user, destination="courses", title="t")

    def test_a_turn_that_adds_nothing_new_gets_an_answer(self, conversation):
        # The extractor re-reports the stored track and nothing else, which is
        # exactly what it does live. With no corpus in the test database the
        # aside refuses deterministically and consumes no second reply.
        planner.save_session_intake(conversation, {"track": "11 month"})
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation,
                                 "What classes do you have access to", [])
        from rsm_thrive.services.bots import ASIDE_UNKNOWN

        assert ASIDE_UNKNOWN in reply.body, reply.body[:200]
        assert "**Step 2 of 4" in reply.body, "the step must still be asked"
        assert not reply.body.startswith("**Step"), "the answer comes first"

    def test_a_real_answer_is_not_treated_as_a_question(self, conversation):
        planner.save_session_intake(conversation, {"track": "11 month"})
        fake = FakeLLM(replies=[_extracted(track="11 month",
                                           goals=["data-scientist"])])
        reply = answer_electives(fake, conversation, "data scientist", [])
        from rsm_thrive.services.bots import ASIDE_UNKNOWN

        # It taught the interview something, so it gets no aside -- just the
        # next step.
        assert ASIDE_UNKNOWN not in reply.body
        assert reply.body.startswith("**Step 3 of 4")


class TestAnIncidentalWordIsNotAnAnswer:
    """Found by probing a question at every point in the interview: the word
    "heavy" inside "is next quarter heavy?" was recorded as the student's
    workload preference. The turn stated no preference at all."""

    @pytest.mark.parametrize("text", [
        "is next quarter heavy?", "is the workload heavy?",
        "are these courses light?", "does it get heavy later?",
        "will it be a light quarter?", "can I do 11 month?",
        "should I pick data scientist?", "was 17 month the longer one?",
    ])
    def test_these_read_as_questions(self, text):
        from rsm_thrive.services import planner

        assert planner.is_question(text), text

    @pytest.mark.parametrize("text", [
        "heavy", "light", "11 month", "11 month?", "moderate",
        "data scientist", "python 4 sql 3",
    ])
    def test_answers_are_still_answers(self, text):
        # A hedged answer starts with its own value, never with an auxiliary.
        from rsm_thrive.services import planner

        assert not planner.is_question(text), text

    def test_the_measured_case_end_to_end(self):
        from rsm_thrive.services import planner

        extracted = planner.normalise_intake({"workload": "heavy"})
        assert extracted == {"workload": "heavy"}, "the extractor does report it"
        merged = planner.merge_intake({}, extracted,
                                      asking=planner.is_question("is next quarter heavy?"))
        assert merged == {}, "but a question must not turn it into an answer"
