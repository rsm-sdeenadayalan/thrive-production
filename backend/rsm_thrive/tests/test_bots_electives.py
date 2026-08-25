import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import Conversation, CoursePlan, PlannerSession
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


class TestTheInterview:
    def test_the_first_thing_asked_is_the_track(self, conversation):
        """The brief: ask 11 month or 17 month before recommending anything."""
        fake = FakeLLM(replies=[_extracted()])
        reply = answer_electives(fake, conversation, "recommend me some courses", [])
        assert reply.model_note == "intake"
        assert "11 month" in reply.body and "17 month" in reply.body
        assert "Step 1 of 4" in reply.body

    def test_no_courses_are_named_before_the_interview_finishes(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation, "11 month", [])
        assert "MGTA" not in reply.body
        assert reply.model_note == "intake"

    def test_after_the_track_it_asks_about_the_goal(self, conversation):
        fake = FakeLLM(replies=[_extracted(track="11 month")])
        reply = answer_electives(fake, conversation, "11 month", [])
        assert "Step 2 of 4" in reply.body
        assert "Data Scientist" in reply.body

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

    def test_then_it_asks_about_workload(self, conversation):
        answers = {**FULL, "workload": None}
        fake = FakeLLM(replies=[_extracted(**answers)])
        reply = answer_electives(fake, conversation, "all basic", [])
        assert "Step 4 of 4" in reply.body
        assert "course load" in reply.body

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
    a question — and then, once it asked, it answered with a menu of ten roles
    the student had not asked about."""

    UNKNOWN = {"track": "11 month", "goals": [], "skill_python": None,
               "skill_sql": None, "skill_stats": None, "skill_ml": None,
               "skill_communication": None, "workload": None, "interests": [],
               "unmatched_goal": "esports analyst"}

    def test_it_says_it_has_no_material_for_that_career(self, conversation):
        fake = FakeLLM(replies=[json.dumps(self.UNKNOWN)])
        reply = answer_electives(fake, conversation,
                                 "i want to be an esports analyst", [])
        assert reply.model_note == "no-track"
        assert "esports analyst" in reply.body

    def test_it_points_at_advising_and_the_appointments_tab(self, conversation):
        fake = FakeLLM(replies=[json.dumps(self.UNKNOWN)])
        body = answer_electives(fake, conversation, "esports analyst", []).body
        assert "MSBA advising" in body
        assert "Appointments" in body

    def test_it_does_not_spam_the_list_of_roles(self, conversation):
        """The whole point of the change: no menu of ten roles."""
        fake = FakeLLM(replies=[json.dumps(self.UNKNOWN)])
        body = answer_electives(fake, conversation, "esports analyst", []).body
        for label in ("Data Scientist", "Data Engineer", "Product Manager",
                      "Analytics Consultant"):
            assert label not in body
        assert "Step 2 of 4" not in body

    def test_no_plan_is_produced_for_an_uncovered_career(self, conversation):
        fake = FakeLLM(replies=[json.dumps({
            **self.UNKNOWN, "skill_python": "basic", "skill_sql": "basic",
            "skill_stats": "basic", "skill_ml": "basic",
            "skill_communication": "basic", "workload": "moderate"})])
        body = answer_electives(fake, conversation, "esports analyst", []).body
        assert "## Summer III" not in body
        assert "MGTA" not in body

    def test_it_still_leaves_a_way_forward(self, conversation):
        fake = FakeLLM(replies=[json.dumps(self.UNKNOWN)])
        body = answer_electives(fake, conversation, "esports analyst", []).body
        assert "tell me which one" in body.lower()

    def test_naming_a_covered_role_afterwards_resumes_the_interview(self, conversation):
        answer_electives(FakeLLM(replies=[json.dumps(self.UNKNOWN)]),
                         conversation, "esports analyst", [])
        resumed = FakeLLM(replies=[_extracted(track="11 month",
                                              goals=["data-scientist"])])
        reply = answer_electives(resumed, conversation, "data scientist ok", [])
        assert reply.model_note == "intake"
        assert "Step 3 of 4" in reply.body

    def test_a_recognised_goal_is_never_diverted_to_advising(self, conversation):
        """An unmatched mention alongside a real choice must not block the plan."""
        fake = FakeLLM(replies=[json.dumps({
            **self.UNKNOWN, "goals": ["data-scientist"],
            "skill_python": "basic", "skill_sql": "basic", "skill_stats": "basic",
            "skill_ml": "basic", "skill_communication": "basic",
            "workload": "moderate"})])
        reply = answer_electives(fake, conversation,
                                 "esports, but data scientist works", [])
        assert reply.model_note == "plan"


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
        assert [q["send"] for q in reply.quick_replies] == [
            "walk me through it", "finalise"]

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
