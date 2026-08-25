import pytest

from rsm_thrive.services import planner
from rsm_thrive.services.electives import load_catalog

ANSWERS = {
    "track": "11 month",
    "goals": ["data-scientist"],
    "skill_python": "comfortable",
    "skill_sql": "basic",
    "skill_stats": "comfortable",
    "skill_ml": "basic",
    "skill_communication": "basic",
    "workload": "moderate",
    "interests": ["machine-learning"],
}

BEGINNER = {**ANSWERS, "skill_python": "none", "skill_sql": "none",
            "skill_stats": "none", "skill_ml": "none",
            "goals": ["product-manager"], "workload": "light", "interests": []}


class TestIntake:
    def test_every_question_maps_to_a_scoring_input(self):
        keys = {q["key"] for q in planner.intake_questions()}
        assert "track" in keys and "goals" in keys and "workload" in keys
        # The brief requires the track and a per-area skill level be asked.
        for area in planner.SKILL_AREAS:
            assert f"skill_{area['key']}" in keys

    def test_track_options_are_the_two_real_tracks(self):
        track = next(q for q in planner.intake_questions() if q["key"] == "track")
        assert {o["value"] for o in track["options"]} == set(planner.TRACK_SKELETONS)

    def test_validate_rejects_a_missing_track(self):
        answers = {**ANSWERS}
        del answers["track"]
        assert any("track" in p for p in planner.validate_intake(answers))

    def test_validate_rejects_an_unknown_goal(self):
        problems = planner.validate_intake({**ANSWERS, "goals": ["astronaut"]})
        assert any("goals" in p for p in problems)

    def test_validate_caps_the_number_of_goals(self):
        problems = planner.validate_intake(
            {**ANSWERS, "goals": ["data-scientist", "consultant",
                                  "marketing-analyst", "data-engineer"]})
        assert any("at most 3" in p for p in problems)

    def test_a_complete_intake_validates(self):
        assert planner.validate_intake(ANSWERS) == []

    def test_communication_does_not_inflate_technical_comfort(self):
        """A strong presenter is not therefore ready for PySpark."""
        quiet = planner.profile_from_intake(
            {**BEGINNER, "skill_communication": "advanced"})
        assert quiet["technical_comfort"] == planner.profile_from_intake(
            {**BEGINNER, "skill_communication": "none"})["technical_comfort"]

    def test_skill_answers_reach_the_scorer(self):
        low = planner.profile_from_intake(BEGINNER)["technical_comfort"]
        high = planner.profile_from_intake(
            {**ANSWERS, "skill_python": "advanced", "skill_sql": "advanced",
             "skill_stats": "advanced", "skill_ml": "advanced"})["technical_comfort"]
        assert low < high


class TestSkillRatings:
    """The skills step is answered by clicking a 1-5 rating per area."""

    def test_the_form_offers_a_row_per_area_pre_set_to_the_middle(self):
        step = planner.next_intake_step({"track": "11 month",
                                         "goals": ["data-scientist"]})
        form = planner.rating_form_for(step)
        assert form["kind"] == "rating"
        assert [r["key"] for r in form["rows"]] == [
            f"skill_{a['key']}" for a in planner.SKILL_AREAS]
        assert [p["value"] for p in form["scale"]] == [1, 2, 3, 4, 5]
        assert form["default"] == planner.DEFAULT_SKILL_RATING == 3

    def test_only_the_areas_still_missing_are_asked(self):
        step = {"key": "skills", "missing": ["skill_ml"]}
        form = planner.rating_form_for(step)
        assert [r["key"] for r in form["rows"]] == ["skill_ml"]

    def test_no_other_step_gets_a_form(self):
        for key in ("track", "goals", "workload"):
            assert planner.rating_form_for({"key": key, "missing": []}) is None

    def test_a_submitted_form_reads_like_a_person_wrote_it(self):
        said = planner.compose_rating_message(
            {"skill_python": 4, "skill_sql": 2})
        assert said == "Python programming 4, SQL and databases 2"

    @pytest.mark.parametrize("given,expected", [
        (4, 4), ("4", 4), ("comfortable", 4), ("none", 1), ("advanced", 5),
        ("expert", 5), ("beginner", 1), ("  Basic  ", 2),
    ])
    def test_a_rating_is_read_from_a_number_or_a_word(self, given, expected):
        """The buttons send numbers; people type words. Both are answers."""
        assert planner.skill_score(given) == expected

    @pytest.mark.parametrize("given", [0, 6, 9, -1, "", "banana", None, True])
    def test_an_unreadable_rating_is_rejected_not_guessed(self, given):
        assert planner.skill_score(given) is None

    def test_ratings_are_stored_as_numbers_whatever_arrived(self):
        answers = planner.normalise_intake(
            {"skill_python": "comfortable", "skill_sql": "2", "skill_ml": 5})
        assert answers == {"skill_python": 4, "skill_sql": 2, "skill_ml": 5}

    def test_an_out_of_range_rating_is_dropped(self):
        assert "skill_stats" not in planner.normalise_intake({"skill_stats": 9})

    def test_the_ratings_drive_technical_comfort_directly(self):
        low = planner.profile_from_intake(
            {**ANSWERS, "skill_python": 1, "skill_sql": 1,
             "skill_stats": 1, "skill_ml": 1})
        high = planner.profile_from_intake(
            {**ANSWERS, "skill_python": 5, "skill_sql": 5,
             "skill_stats": 5, "skill_ml": 5})
        assert low["technical_comfort"] == 1
        assert high["technical_comfort"] == 5

    def test_words_and_numbers_reach_the_same_comfort(self):
        by_word = planner.profile_from_intake(
            {**ANSWERS, "skill_python": "comfortable", "skill_sql": "comfortable",
             "skill_stats": "comfortable", "skill_ml": "comfortable"})
        by_number = planner.profile_from_intake(
            {**ANSWERS, "skill_python": 4, "skill_sql": 4,
             "skill_stats": 4, "skill_ml": 4})
        assert by_word["technical_comfort"] == by_number["technical_comfort"]

    def test_a_low_rating_still_raises_the_prerequisite_caution(self):
        from rsm_thrive.services.electives import load_catalog

        course = next(c for c in load_catalog()
                      if "python" in (c.get("prerequisites") or "").lower())
        cautions = planner.prerequisite_cautions(
            course, {**ANSWERS, "skill_python": 1})
        assert cautions and "out of 5" in cautions[0]

    def test_a_high_rating_raises_no_caution(self):
        from rsm_thrive.services.electives import load_catalog

        course = next(c for c in load_catalog()
                      if "python" in (c.get("prerequisites") or "").lower())
        assert planner.prerequisite_cautions(
            course, {**ANSWERS, "skill_python": 5, "skill_stats": 5,
                     "skill_ml": 5, "skill_sql": 5}) == []


class TestSkeletons:
    @pytest.mark.parametrize("track", sorted(planner.TRACK_SKELETONS))
    def test_every_track_totals_fifty_units(self, track):
        by_id = {c["id"]: c for c in load_catalog()}
        quarters = planner.TRACK_SKELETONS[track]
        core = sum(by_id[s["course_id"]]["units"] for q in quarters
                   for s in q["slots"] if s["kind"] == "core")
        fixed = sum(by_id[s["course_id"]]["units"] for q in quarters
                    for s in q["slots"] if s["kind"] == "fixed")
        open_slots = sum(s["units"] for q in quarters
                         for s in q["slots"] if s["kind"] == "elective")
        assert core == planner.CORE_UNITS
        assert fixed + open_slots == planner.ELECTIVE_UNITS
        assert core + fixed + open_slots == planner.TOTAL_UNITS

    @pytest.mark.parametrize("track", sorted(planner.TRACK_SKELETONS))
    def test_declared_quarter_units_match_their_slots(self, track):
        by_id = {c["id"]: c for c in load_catalog()}
        for quarter in planner.TRACK_SKELETONS[track]:
            total = sum(by_id[s["course_id"]]["units"] if s.get("course_id")
                        else s["units"] for s in quarter["slots"])
            assert total == quarter["units"], quarter["key"]


@pytest.mark.django_db
class TestBuildPlan:
    @pytest.mark.parametrize("track", sorted(planner.TRACK_SKELETONS))
    def test_plan_is_complete_and_adds_up(self, track):
        plan = planner.build_plan({**ANSWERS, "track": track})
        assert plan["unfilled"] == []
        assert plan["totals"]["total"] == planner.TOTAL_UNITS
        assert plan["totals"]["core"] == planner.CORE_UNITS
        assert plan["totals"]["elective"] == planner.ELECTIVE_UNITS
        for quarter in plan["quarters"]:
            assert quarter["unitsPlanned"] == quarter["unitsExpected"]

    def test_every_quarter_lists_core_and_elective_labelled(self):
        """The brief: show the core classes too, marked core vs elective."""
        plan = planner.build_plan(ANSWERS)
        for quarter in plan["quarters"]:
            assert quarter["courses"]
            for row in quarter["courses"]:
                assert row["requirement"] in ("Core", "Elective")
        cores = [r for q in plan["quarters"] for r in q["courses"]
                 if r["requirement"] == "Core"]
        assert {r["code"] for r in cores} == {
            "MGTA 451", "MGTA 452", "MGTA 453", "MGTA 455", "MGTA 444", "MGTA 454"}

    def test_no_course_appears_twice(self):
        for track in planner.TRACK_SKELETONS:
            plan = planner.build_plan({**ANSWERS, "track": track})
            ids = [r["courseId"] for q in plan["quarters"] for r in q["courses"]
                   if r["courseId"]]
            assert len(ids) == len(set(ids)), track

    def test_electives_are_offered_in_the_quarter_they_are_placed_in(self):
        by_id = {c["id"]: c for c in load_catalog()}
        for track in planner.TRACK_SKELETONS:
            plan = planner.build_plan({**ANSWERS, "track": track})
            for quarter in plan["quarters"]:
                for row in quarter["courses"]:
                    if not row["courseId"]:
                        continue
                    seasons = {(o.get("season") or "").upper() for o
                               in by_id[row["courseId"]].get("offerings") or []}
                    assert quarter["season"] in seasons, (row["code"], quarter["key"])

    def test_core_slots_are_never_swappable(self):
        plan = planner.build_plan(ANSWERS)
        for quarter in plan["quarters"]:
            for row in quarter["courses"]:
                if row["requirement"] == "Core":
                    assert row["swappable"] is False

    def test_the_plan_changes_with_the_goal(self):
        """If two different students get the same electives, the intake is decoration."""
        ds = planner.build_plan(ANSWERS)
        pm = planner.build_plan(BEGINNER)
        def electives(plan):
            return {r["code"] for q in plan["quarters"] for r in q["courses"]
                    if r["requirement"] == "Elective" and r["swappable"]}
        assert electives(ds) != electives(pm)

    def test_a_beginner_is_warned_about_prerequisites(self):
        plan = planner.build_plan(BEGINNER)
        assert any(r["cautions"] for q in plan["quarters"] for r in q["courses"])

    def test_cautions_never_remove_a_course(self):
        """Advisory, not a filter — the student and their advisor decide."""
        plan = planner.build_plan(BEGINNER)
        assert plan["unfilled"] == []
        assert plan["totals"]["total"] == planner.TOTAL_UNITS

    def test_already_taken_courses_are_not_planned_again(self):
        plan = planner.build_plan(ANSWERS)
        first = next(r["courseId"] for q in plan["quarters"] for r in q["courses"]
                     if r["swappable"])
        again = planner.build_plan(ANSWERS, taken_ids={first})
        assert first not in {r["courseId"] for q in again["quarters"]
                             for r in q["courses"]}

    def test_the_plan_is_deterministic(self):
        assert planner.build_plan(ANSWERS) == planner.build_plan(ANSWERS)

    def test_unknown_track_is_an_error_not_a_silent_default(self):
        with pytest.raises(ValueError):
            planner.build_plan({**ANSWERS, "track": "4 month"})

    def test_plan_carries_booking_and_catalog_links(self):
        plan = planner.build_plan(ANSWERS)
        keys = {link["key"] for link in plan["links"]}
        assert {"tss", "schedule", "plans-drive"} <= keys
        for link in plan["links"]:
            assert link["url"].startswith("https://")


@pytest.mark.django_db
class TestAlternatives:
    def test_options_fill_the_same_hole(self):
        plan = planner.build_plan(ANSWERS)
        result = planner.alternatives_for(plan, ANSWERS, "fall", 2)
        assert result["options"]
        current = result["current"]
        for option in result["options"]:
            assert option["units"] == current["units"]

    def test_options_are_not_already_in_the_plan(self):
        plan = planner.build_plan(ANSWERS)
        in_plan = {r["courseId"] for q in plan["quarters"] for r in q["courses"]}
        for option in planner.alternatives_for(plan, ANSWERS, "fall", 2)["options"]:
            assert option["courseId"] not in in_plan

    def test_each_option_says_why_it_is_an_alternative(self):
        plan = planner.build_plan(ANSWERS)
        for option in planner.alternatives_for(plan, ANSWERS, "fall", 2)["options"]:
            assert option["sharedSkills"] or option["sharedFocus"] or option["reasons"]

    def test_options_are_ordered_by_similarity_to_the_current_course(self):
        plan = planner.build_plan(ANSWERS)
        sims = [o["similarity"] for o in
                planner.alternatives_for(plan, ANSWERS, "fall", 2)["options"]]
        assert sims == sorted(sims, reverse=True)

    def test_a_fixed_slot_offers_nothing_and_says_so(self):
        plan = planner.build_plan(ANSWERS)
        result = planner.alternatives_for(plan, ANSWERS, "summer", 0)
        assert result["swappable"] is False and result["options"] == []
        assert result["why"]

    def test_an_unknown_slot_is_an_error(self):
        plan = planner.build_plan(ANSWERS)
        with pytest.raises(ValueError):
            planner.alternatives_for(plan, ANSWERS, "nope", 0)


@pytest.mark.django_db
class TestSwap:
    def _first_option(self):
        plan = planner.build_plan(ANSWERS)
        return planner.alternatives_for(plan, ANSWERS, "fall", 2)["options"][0]

    def test_a_swap_sticks_and_keeps_the_plan_valid(self):
        option = self._first_option()
        selections = planner.apply_swap(ANSWERS, {}, "fall", 2, option["courseId"])
        plan = planner.build_plan(ANSWERS, selections=selections)
        assert plan["quarters"][1]["courses"][2]["courseId"] == option["courseId"]
        assert plan["totals"]["total"] == planner.TOTAL_UNITS
        assert plan["unfilled"] == []

    def test_a_swap_only_moves_the_slot_it_targets(self):
        option = self._first_option()
        before = planner.build_plan(ANSWERS)
        after = planner.build_plan(
            ANSWERS, selections=planner.apply_swap(ANSWERS, {}, "fall", 2,
                                                   option["courseId"]))
        changed = [(q["key"], i) for q, qa in zip(before["quarters"], after["quarters"])
                   for i, (a, b) in enumerate(zip(q["courses"], qa["courses"]))
                   if a["courseId"] != b["courseId"]]
        assert changed == [("fall", 2)]

    def test_a_swapped_course_is_marked_as_the_students_choice(self):
        option = self._first_option()
        plan = planner.build_plan(
            ANSWERS, selections=planner.apply_swap(ANSWERS, {}, "fall", 2,
                                                   option["courseId"]))
        assert plan["quarters"][1]["courses"][2]["note"] == "your choice"

    def test_wrong_unit_size_is_refused(self):
        with pytest.raises(ValueError, match="units"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, "MGTA 402")

    def test_a_course_not_offered_that_quarter_is_refused(self):
        with pytest.raises(ValueError, match="not offered"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, "MGTA 456")

    def test_a_core_course_cannot_fill_an_elective_slot(self):
        with pytest.raises(ValueError, match="core"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, "MGTA 452")

    def test_a_fixed_slot_cannot_be_swapped(self):
        with pytest.raises(ValueError, match="fixed"):
            planner.apply_swap(ANSWERS, {}, "summer", 1, "MGTA 457")

    def test_an_unknown_course_is_refused(self):
        with pytest.raises(ValueError, match="unknown course"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, "MGTA 999")

    def test_a_course_already_taken_is_refused(self):
        option = self._first_option()
        with pytest.raises(ValueError, match="already taken"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, option["courseId"],
                               taken_ids={option["courseId"]})

    def test_the_same_course_cannot_be_planned_twice(self):
        """Needs a course that is BOTH already in the plan elsewhere and legal
        for the target slot — otherwise an earlier rule refuses it first and the
        duplicate guard is never reached."""
        by_id = {c["id"]: c for c in load_catalog()}
        plan = planner.build_plan(ANSWERS)
        elsewhere = next(
            (r["courseId"] for q in plan["quarters"] if q["key"] != "fall"
             for r in q["courses"]
             if r["swappable"] and r["courseId"]
             and by_id[r["courseId"]]["units"] == 4
             and any((o.get("season") or "").upper() == "FA"
                     for o in by_id[r["courseId"]].get("offerings") or [])),
            None)
        assert elsewhere, "no in-plan elective is also legal for the Fall slot"
        with pytest.raises(ValueError, match="already in your"):
            planner.apply_swap(ANSWERS, {}, "fall", 2, elsewhere)


@pytest.mark.django_db
class TestRendering:
    def test_markdown_lists_every_quarter_and_marks_core_vs_elective(self):
        plan = planner.build_plan(ANSWERS)
        text = planner.render_plan_markdown(plan)
        for quarter in plan["quarters"]:
            assert f"## {quarter['label']}" in text
        assert "| Requirement |" in text
        assert "Core" in text and "Elective" in text

    def test_markdown_uses_tables_the_frontend_can_render(self):
        text = planner.render_plan_markdown(planner.build_plan(ANSWERS))
        assert "|---|---|---|---|" in text

    def test_markdown_carries_the_booking_links(self):
        text = planner.render_plan_markdown(planner.build_plan(ANSWERS))
        assert "https://sis.ucsd.edu/" in text
        assert "drive.google.com" in text

    def test_markdown_names_every_planned_course(self):
        plan = planner.build_plan(ANSWERS)
        text = planner.render_plan_markdown(plan)
        for quarter in plan["quarters"]:
            for row in quarter["courses"]:
                if row["code"]:
                    assert row["code"] in text

    def test_markdown_separates_goal_courses_from_breadth(self):
        text = planner.render_plan_markdown(planner.build_plan(ANSWERS))
        assert "Why these electives" in text

    def test_markdown_surfaces_a_beginners_warnings(self):
        text = planner.render_plan_markdown(planner.build_plan(BEGINNER))
        assert "Worth knowing before you book" in text

    def test_markdown_ends_with_the_advising_disclaimer(self):
        text = planner.render_plan_markdown(planner.build_plan(ANSWERS))
        assert "MSBA advising" in text


class TestSimilarity:
    def test_a_course_is_most_similar_to_itself(self):
        catalog = {c["id"]: c for c in load_catalog()}
        a = catalog["CSE 251A"]
        assert planner.similarity(a, a) == 1.0

    def test_unrelated_courses_score_lower_than_related_ones(self):
        catalog = {c["id"]: c for c in load_catalog()}
        ml = catalog["CSE 251A"]
        near = planner.similarity(ml, catalog["CSE 251B"])   # both ML
        far = planner.similarity(ml, catalog["MGTA 402"])    # presentation skills
        assert near > far

    def test_shared_skills_come_from_the_alternative(self):
        catalog = {c["id"]: c for c in load_catalog()}
        shared = planner.shared_skills(catalog["CSE 251A"], catalog["CSE 251B"])
        assert all(s in catalog["CSE 251B"]["skills"] for s in shared)
