"""Light / moderate / heavy, asked twice and meaning two different things.

The original asked both at once, on a form, before the student had seen a
single course: five sliders distributing fifty units across four quarters. What
replaced it splits the question in two, because it always was two questions:

* **How demanding should the courses be?** Asked once, before the plan. It
  changes which electives get picked (`rank_electives` penalises a course whose
  own workload exceeds the preference) and changes no unit counts at all.
* **How many units should THIS quarter carry?** Asked during the walk-through,
  quarter by quarter, while the student is looking at the four courses the
  answer changes.

The constraint that shapes all of it: the degree is 50 units and Summer is
fixed, so a lighter quarter is a heavier one somewhere else. There is no such
thing as a globally light plan, and the tests below pin that down rather than
letting a 46-unit plan out of the door.
"""

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import Conversation, PlannerSession
from rsm_thrive.services import orchestrator, planner
from rsm_thrive.services.llm import FakeLLM

pytestmark = pytest.mark.django_db

FULL = {"track": "11 month", "goals": ["data-scientist"],
        "skill_python": "comfortable", "skill_sql": "basic",
        "skill_stats": "comfortable", "skill_ml": "basic",
        "skill_communication": "basic", "workload": "moderate"}


@pytest.fixture
def user():
    return User.objects.create_user("stu")


@pytest.fixture
def conversation(user):
    return Conversation.objects.create(user=user, destination="courses",
                                        title="planning")


def mid_walk(conversation, index=1, **overrides):
    """A conversation part-way through the walk-through."""
    PlannerSession.objects.update_or_create(
        conversation=conversation,
        defaults={"intake": {**FULL, **overrides},
                  "asked": ["workload", "plan"],
                  "review": {"index": index}})
    return conversation


# ---------------------------------------------------------------------------
# Reading the word
# ---------------------------------------------------------------------------

class TestReadingTheWord:
    @pytest.mark.parametrize("text,expected", [
        ("light", "light"), ("Heavy", "heavy"), ("medium", "moderate"),
        ("moderate", "moderate"), ("make it light", "light"),
        ("push me", "heavy"), ("normal", "moderate"),
    ])
    def test_these_are_answers(self, text, expected):
        assert planner.load_intent(text) == expected

    @pytest.mark.parametrize("text", [
        "is next quarter heavy?", "are these courses light?",
        "which one is the heavy option?", "swap MGTA 461 for MGTA 463",
        "next quarter", "finalise", "",
    ])
    def test_these_are_not(self, text):
        assert planner.load_intent(text) is None

    def test_a_bare_hedge_still_answers(self):
        """`is_question` treats "heavy?" as a hedged answer rather than a
        question, on the argued grounds that an answer starts with its own
        value where a question starts with an auxiliary. A student replying
        "heavy?" to "how heavy do you want Fall?" is answering it."""
        assert planner.load_intent("heavy?") == "heavy"

    def test_a_load_inside_an_intake_sentence_is_found(self):
        """"11 month, data scientist, heavy" names all three, and strict
        whole-message matching finds none of them."""
        assert planner.load_mentioned("11 month, data scientist, heavy") == "heavy"

    def test_but_only_where_the_turn_is_stating_intake_facts(self):
        """`load_mentioned` applied to any message would read "MGTA 456 is
        heavy" as a preference. `learned_from` only reaches for it on a turn
        that already stated a track or a goal."""
        assert orchestrator.learned_from("MGTA 456 is heavy") == {}
        assert orchestrator.learned_from("11 month and heavy") == {
            "track": "11 month", "workload": "heavy"}


# ---------------------------------------------------------------------------
# The arithmetic: 50 units, always
# ---------------------------------------------------------------------------

class TestTheDegreeTotalNeverMoves:
    def test_a_lighter_quarter_is_a_heavier_one_elsewhere(self):
        wanted, disturbed = planner.rebalanced_units("11 month", {}, "fall", 12)
        assert wanted == {"fall": 12, "winter": 16, "spring": 14}
        assert disturbed == []
        assert sum(wanted.values()) == planner.TOTAL_UNITS \
            - planner.fixed_quarter_units("11 month")

    def test_every_distribution_it_produces_is_schedulable(self):
        for track in ("11 month", "17 month"):
            for quarter in planner.adjustable_quarters(track):
                for load in ("light", "moderate", "heavy"):
                    units = planner.units_for_load(track, quarter["key"], load)
                    wanted, _ = planner.rebalanced_units(
                        track, {}, quarter["key"], units)
                    if wanted is None:
                        continue
                    assert not planner.quarter_units_problems(track, wanted), \
                        (track, quarter["key"], load, wanted)

    def test_units_move_two_at_a_time(self):
        """`_resized` cuts a budget into 4-unit slots plus a 2-unit remainder,
        so an odd budget leaves a hole no course in the catalog can fill."""
        for track in ("11 month", "17 month"):
            for quarter in planner.adjustable_quarters(track):
                wanted, _ = planner.rebalanced_units(
                    track, {}, quarter["key"],
                    planner.units_for_load(track, quarter["key"], "heavy"))
                if wanted is None:
                    continue
                assert all(value % 2 == 0 for value in wanted.values()), wanted

    def test_an_impossible_load_is_refused_rather_than_approximated(self):
        """The 17-month second Fall cannot take 8 units: the three quarters
        before it are already at their 12-unit floors."""
        wanted, _ = planner.rebalanced_units("17 month", {}, "fall-two", 8)
        assert wanted is None

    def test_a_load_is_offered_at_the_heaviest_value_it_can_reach(self):
        """A quarter's own enrolment cap is not the real cap. On the 17-month
        track every quarter caps at 18 units and none can reach it: 18 in Fall
        leaves 24 for the other three, whose floors add up to 26. Reading the
        cap literally offered that Fall only "light", so the heaviest thing the
        student could have was the one option they were not shown."""
        assert planner.units_for_load("17 month", "fall", "heavy") == 16
        assert planner.units_for_load("11 month", "fall", "heavy") == 18
        offered = {option["value"]: option["units"]
                   for option in planner.load_options_for("17 month", "fall-two")}
        assert offered == {"light": 2, "moderate": 4, "heavy": 6}

    def test_a_quarter_with_no_lighter_version_offers_no_duplicate(self):
        """The 17-month Fall's published load IS its floor, so "light" and
        "moderate" are the same number and offering both is not a choice."""
        options = planner.load_options_for("17 month", "fall")
        assert len({option["units"] for option in options}) == len(options)

    def test_an_earlier_choice_is_not_silently_undone(self):
        """Answering "light" for Winter used to push Fall back off the "light"
        the student had picked one quarter earlier, with nothing saying so."""
        after_fall, _ = planner.rebalanced_units("11 month", {}, "fall", 12)
        after_winter, disturbed = planner.rebalanced_units(
            "11 month", after_fall, "winter", 12, pinned={"fall"})
        assert after_winter["fall"] == 12, "their Fall choice survived"
        assert disturbed == []

    def test_and_when_it_would_have_to_be_undone_it_is_refused(self):
        """All three light is 36 units against 42 required, so the third
        request cannot be honoured without moving the first two. Refused and
        named, rather than done silently."""
        chosen = {"fall": 12, "winter": 12, "spring": 18}
        wanted, blockers = planner.rebalanced_units(
            "11 month", chosen, "spring", 12, pinned={"fall", "winter"})
        assert wanted is None
        assert blockers == ["fall", "winter"], "and it names them"

    def test_a_quarter_fixed_by_earlier_choices_offers_nothing(self):
        chosen = {"fall": 12, "winter": 12, "spring": 18}
        assert planner.load_options_for("11 month", "spring", chosen,
                                        {"fall", "winter"}) == []


# ---------------------------------------------------------------------------
# Asked once, before the plan
# ---------------------------------------------------------------------------

class TestThePreferenceIsAskedFirst:
    def _to_the_spread(self, conversation, opener="11 month, data scientist"):
        """Answer the skills question so the spread question is what's next."""
        orchestrator.answer(FakeLLM([]), conversation, opener, [])
        return orchestrator.answer(FakeLLM([]), conversation, "skip", [])

    def test_it_is_asked_before_any_course_is_named(self, conversation):
        reply = self._to_the_spread(conversation)
        assert "spread across the quarters" in reply.body.lower()
        assert "MGTA" not in reply.body

    def test_it_is_honest_that_the_total_does_not_move(self, conversation):
        """The degree is 50 units. A question that implied "light" meant less
        work would be promising something the plan cannot deliver."""
        reply = self._to_the_spread(conversation)
        assert "50 units either way" in reply.body
        assert "nothing here is final" in reply.body, "the walk-through refines it"

    def test_answering_it_builds_the_plan(self, conversation):
        orchestrator.answer(FakeLLM([]), conversation, "11 month, data scientist", [])
        reply = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "MGTA" in reply.body
        assert planner.load_session_intake(conversation)["workload"] == "light"

    def test_the_answer_becomes_a_real_distribution(self, conversation):
        self._to_the_spread(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert planner.load_session_intake(conversation)["quarter_units"] == {
            "fall": 12, "winter": 12, "spring": 18}
        assert "Spring 18 units" in reply.body, "and says where the weight went"

    def test_heavy_front_loads_it_instead(self):
        assert planner.seeded_units("11 month", "heavy") == {
            "fall": 18, "winter": 12, "spring": 12}

    def test_moderate_is_the_published_plan(self):
        assert planner.seeded_units("11 month", "moderate") == {}

    def test_it_acts_on_units_because_it_cannot_act_on_difficulty(self):
        """Documented rather than fixed. `rank_electives` does penalise a
        course heavier than the student asked for, but almost nothing in the
        catalog is graded light -- so a light preference has nothing lighter to
        pick and the picks come out identical. Asking about course difficulty
        and then delivering the same twelve courses would be worse than not
        asking.

        The bound was ONE light elective when the catalog held 31 courses. It
        is now two out of eighty, which is the same situation and not a
        different one; if it ever reaches a real share of the catalog, the
        question becomes worth asking and this test should fail so somebody
        revisits it.
        """
        from rsm_thrive.services.electives import load_catalog

        electives = [c for c in load_catalog() if not c["is_core"]]
        light_courses = [c for c in electives if c.get("workload") == "light"]
        assert len(light_courses) / len(electives) < 0.1, (
            "light electives are no longer negligible -- a light preference "
            "may now be actionable, so revisit the question")

        picked = lambda plan: [row["code"] for quarter in plan["quarters"]
                               for row in quarter["courses"] if row["swappable"]]
        light = planner.build_for({**FULL, "workload": "light"}, frozenset())
        heavy = planner.build_for({**FULL, "workload": "heavy"}, frozenset())
        assert picked(light) == picked(heavy)

    def test_a_track_that_cannot_honour_it_says_so(self, conversation):
        """No quarter on the 17-month track can reach its 18-unit cap, so
        "heavy" there is a much smaller change than on the 11-month track."""
        seeded = planner.seeded_units("17 month", "heavy")
        assert seeded == {"fall": 16, "winter": 12, "spring": 12, "fall-two": 2}

    def test_a_light_preference_flags_what_it_could_not_honour(self):
        plan = planner.build_for({**FULL, "workload": "light"}, frozenset())
        stretches = [note for quarter in plan["quarters"]
                     for row in quarter["courses"]
                     for note in (row.get("stretch") or [])]
        assert any("light load you asked for" in note for note in stretches)

    def test_it_is_never_asked_twice(self, conversation):
        self._to_the_spread(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation,
                                    "actually just show me the plan", [])
        assert "spread across the quarters" not in reply.body.lower()
        assert "MGTA" in reply.body, "the plan arrives anyway"
        assert "published plan does" in reply.body, "and says what it assumed"


# ---------------------------------------------------------------------------
# Asked again, per quarter, during the walk-through
# ---------------------------------------------------------------------------

class TestEachQuarterIsAskedDuringTheWalkThrough:
    def test_the_quarter_carries_the_question_with_real_numbers(self, conversation):
        mid_walk(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation, "next quarter", [])
        assert "How heavy should" in reply.body
        assert "12 units" in reply.body and "18 units" in reply.body

    def test_answering_moves_the_units_and_says_where_they_went(self, conversation):
        mid_walk(conversation)
        reply = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "is now light — 12 units" in reply.body
        assert "absorbed it" in reply.body
        answers = planner.load_session_intake(conversation)
        assert answers["quarter_units"] == {"fall": 12, "winter": 16, "spring": 14}
        assert answers["quarter_loads"] == {"fall": "light"}

    def test_the_recommendation_moves_with_the_units(self, conversation):
        """A quarter asked to carry 18 units instead of 14 gets another
        elective slot, and the scorer fills it. That is the whole reason for
        asking here rather than on a form."""
        mid_walk(conversation)
        before = planner.build_for(FULL, frozenset())
        orchestrator.answer(FakeLLM([]), conversation, "heavy", [])
        after = planner.build_for(planner.load_session_intake(conversation),
                                  frozenset())
        fall = lambda plan: next(q for q in plan["quarters"] if q["key"] == "fall")
        # The direction, not exact numbers: a curated bundle may sit up to
        # `bundles.QUARTER_FLEX` off its target to be schedulable at all, and
        # the plan says so where it does. See `planner.route_line`.
        assert fall(after)["unitsPlanned"] > fall(before)["unitsPlanned"]
        # Units, not row count. On a curated bundle the number of slots comes
        # from the sizes of the bundle's own courses, so 18 units can be four
        # rows or five; what must move is the load.
        elective_units = lambda plan: sum(
            row["units"] for row in fall(plan)["courses"]
            if row["requirement"] == "Elective")
        assert elective_units(after) > elective_units(before)
        assert after["totals"]["total"] == planner.TOTAL_UNITS

    def test_the_plan_still_totals_fifty_units(self, conversation):
        mid_walk(conversation)
        orchestrator.answer(FakeLLM([]), conversation, "heavy", [])
        plan = planner.build_for(planner.load_session_intake(conversation),
                                 frozenset())
        assert plan["totals"]["total"] == planner.TOTAL_UNITS

    def test_summer_says_plainly_that_it_cannot_change(self, conversation):
        mid_walk(conversation, index=0)
        reply = orchestrator.answer(FakeLLM([]), conversation, "heavy", [])
        assert "isn't adjustable" in reply.body
        assert "required courses" in reply.body
        assert planner.load_session_intake(conversation).get("quarter_units") is None

    def test_a_load_outside_the_walk_through_is_the_overall_preference(
            self, conversation):
        """Same word, two meanings, disambiguated by whether a walk-through is
        running rather than by asking which they meant."""
        PlannerSession.objects.update_or_create(
            conversation=conversation,
            defaults={"intake": FULL, "asked": ["workload", "plan"],
                      "review": None})
        orchestrator.answer(FakeLLM(["fine"]), conversation, "heavy", [])
        answers = planner.load_session_intake(conversation)
        assert answers["workload"] == "heavy"
        # It seeds the WHOLE spread, not one quarter -- which is exactly the
        # difference from the same word said mid-walk-through.
        assert answers["quarter_units"] == {"fall": 18, "winter": 12,
                                            "spring": 12}
        assert "quarter_loads" not in answers

    def test_a_second_visit_states_the_answer_rather_than_re_asking(
            self, conversation):
        mid_walk(conversation)
        first = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "is now light" in first.body

        again = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "is already light — 12 units" in again.body
        assert "absorbed it" not in again.body, "nothing moved the second time"
        assert "Fall is light — 12 units**, as you asked" in again.body
        assert "How heavy should Fall be?" not in again.body

    def test_a_choice_already_made_is_never_moved_to_satisfy_a_later_one(
            self, conversation):
        """Refused and explained, rather than done silently. All three
        quarters light is 36 units against the 42 the degree needs."""
        mid_walk(conversation, index=3,
                 quarter_units={"fall": 12, "winter": 12, "spring": 18},
                 quarter_loads={"fall": "light", "winter": "light"})
        reply = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "without moving" in reply.body
        assert "**Fall**" in reply.body and "**Winter**" in reply.body
        answers = planner.load_session_intake(conversation)
        assert answers["quarter_units"]["fall"] == 12, "their choice survived"

    def test_an_impossible_request_says_so_and_names_the_total(
            self, conversation):
        mid_walk(conversation, index=4, track="17 month",
                 quarter_units={"fall": 12, "winter": 12, "spring": 12,
                                "fall-two": 6},
                 quarter_loads={"fall": "light", "winter": "light",
                                "spring": "light"})
        reply = orchestrator.answer(FakeLLM([]), conversation, "light", [])
        assert "can't make" in reply.body.lower()
        assert "50 units" in reply.body

    def test_the_walk_through_still_carries_no_buttons(self, conversation):
        mid_walk(conversation)
        for turn in ("next quarter", "light", "heavy"):
            reply = orchestrator.answer(FakeLLM([]), conversation, turn, [])
            assert reply.quick_replies == [], turn
            assert reply.form is None, turn
            assert "_You can say:_" in reply.body, turn

    def test_the_spoken_line_keeps_navigation_ahead_of_swaps(self, conversation):
        """A quarter with two elective slots offers six swaps. A flat cap put
        all six in the line and dropped "next quarter" and the load answers off
        the end — the two things a student is most likely to want next."""
        mid_walk(conversation, index=2)
        reply = orchestrator.answer(FakeLLM([]), conversation, "next quarter", [])
        line = reply.body.split("_You can say:_")[1]
        assert "**light**" in line and "**heavy**" in line
        assert "**finalise**" in line or "**next quarter**" in line
        assert line.index("**light**") < line.index("swap"), "navigation first"
        assert line.count("swap ") <= 3, "and the swaps are the capped half"
