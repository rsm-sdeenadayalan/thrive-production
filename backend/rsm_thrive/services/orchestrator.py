"""The course surface's one dispatcher.

`router.classify` decides WHAT kind of question this is; this decides what to
do about it and produces the reply. Nothing else routes: the regex that used to
live in `grounded_course_advisor`, the interview state machine in
`planner.next_intake_step`, and the chain of `if` branches in
`bots.answer_electives` are all replaced by the table in `answer` below.

## Free text first

There is no interview. A student who types a real sentence gets an answer to
that sentence, not step 1 of 4 — and the one place a question comes back is the
`unclear` route, plus the single question the situational route asks when it
genuinely does not know which quarter someone is standing in. A form that opens
by asking four questions makes a student answer three they did not need to.

The plan-of-study machinery survives untouched. Swapping a course, walking the
plan a quarter at a time and finalising it are all still here — they were never
the interview, they are what a student does with a plan once one exists, and
they are checked BEFORE the router runs so that "next quarter" and "swap 461
for 463" are not classified as though they were fresh questions.

## The rule this module enforces

**No fact about a course, a unit count, a prerequisite or a deadline is ever
stated unless it came from the catalog, the published skeletons or the
retrieved corpus.**

The model interprets and explains; it never asserts a number. Every handler
below holds that line in the same way: the deterministic layer produces the
facts, the prompt is given those facts and told they are the whole of what it
may say, and where a handler has no grounding it REFUSES rather than answering
from the model's own memory. `grounded_course_advisor` already worked this way;
this makes it the property of the whole surface.
"""

import re

from rsm_thrive.services import (bundles, electives, planner, router,
                                 situation, skill_match)
from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.bots import (BotReply, _catalog_context,
                                      _explain_course, _finalise_reply,
                                      _handle_change_request, _plan_reply,
                                      _review_reply, _small_talk_reply,
                                      _wants_the_plan, append_sources,
                                      build_context)
from rsm_thrive.services.electives import (NON_MSBA_UNIT_CAP,
                                            load_careers, load_catalog)
from rsm_thrive.services.grounded_course_advisor import recommend_for_question
from rsm_thrive.services.retrieval import retrieve


# ---------------------------------------------------------------------------
# What a turn states outright
# ---------------------------------------------------------------------------

# "11 month" / "17-month" / "the eleven month one". A closed set of two, so a
# pattern is the whole implementation and no model call is needed to read it.
_TRACK_WORDS = {
    "11 month": re.compile(r"\b(?:11|eleven)[\s-]?month\b", re.IGNORECASE),
    "17 month": re.compile(r"\b(?:17|seventeen)[\s-]?month\b", re.IGNORECASE),
}


def stated_track(question):
    """The track this turn names, or "". Deterministic."""
    for track, pattern in _TRACK_WORDS.items():
        if pattern.search(question or ""):
            return track
    return ""


def learned_from(question):
    """Intake values this turn states outright, read without a model call.

    The whole of what the four-step interview used to extract, for the two
    fields a plan cannot be built without -- and both come from closed sets, so
    both are deterministic. The track is one of two strings; the goal is
    matched against `careers.json`'s own curated job titles by
    `router.matched_role`, which is the same lookup that makes the role route
    authoritative.

    Skills and per-quarter load are NOT read here and are never asked for. They
    refine a plan and are not required to build one, so under free-text-first
    they are assumed, stated as assumed, and correctable in a sentence. An
    interview that gates a plan behind five sliders is the thing being removed.
    """
    learned = {}
    track = stated_track(question)
    if track:
        learned["track"] = track
    role_id, _exact = router.role_match(question)
    if role_id:
        learned["goals"] = [role_id]
    learned.update(planner.read_skills(question))
    # Only outside the walk-through. During it, "light" is about the quarter on
    # screen rather than about the courses in general -- see
    # `_apply_quarter_load` -- and `_maintenance` runs first, so a review turn
    # never reaches here.
    #
    # The looser `load_mentioned` is used ONLY when this turn already stated a
    # track or a goal, because then it is plainly an intake turn: "11 month,
    # data scientist, heavy" names all three and the strict whole-message test
    # finds none of them. On any other turn the strict test governs, so a
    # passing remark that a course is heavy states no preference.
    load = (planner.load_mentioned(question) if learned
            else planner.load_intent(question))
    if load:
        learned["workload"] = load
    return learned


# Asked once, before the plan exists, and it is the ONE preference question
# that survived the interview's removal.
#
# It is not the old per-quarter unit form. That asked a student to distribute
# fifty units across four quarters before they had seen a single course, which
# is a spreadsheet question dressed as a conversation. This asks for one word
# and turns it into a starting distribution (`planner.seeded_units`), which the
# walk-through then refines one quarter at a time -- with the student looking
# at the courses each answer changes.
#
# The wording is about WHERE THE WEIGHT SITS rather than about how hard the
# courses are, and that is deliberate. The degree is fixed at 50 units, so
# "light" cannot mean fewer; and on this catalog it cannot mean easier either,
# because the elective list holds 14 moderate courses, 9 heavy and exactly one
# light, so a light preference has nothing lighter to pick. Promising an easier
# plan and then delivering the same twelve courses would be worse than not
# asking.
ASK_FOR_A_LOAD = (
    "Before I lay it out — how do you want the load spread across the "
    "quarters?\n\n"
    "- **light** — start easy; the later quarters carry more\n"
    "- **moderate** — the published plan, evenly spread\n"
    "- **heavy** — front-load it; get the weight done early\n\n"
    "The degree is 50 units either way, so this is about where they sit rather "
    "than how many there are. Say one of those — and I'll ask about each "
    "quarter individually when we walk through the plan, so nothing here is "
    "final.")

ASSUMED_LOAD_NOTE = (
    "I've spread the units the way the published plan does, since you haven't "
    "said — say _light_ or _heavy_ any time and I'll redo it.\n\n")

LOAD_APPLIED_NOTE = (
    "Spread **{load}**: {spread}. The degree is still {total} units — a "
    "lighter quarter is a heavier one somewhere else.\n\n")

LOAD_UNAVAILABLE_NOTE = (
    "You asked for a **{load}** spread, and on the {track} track the quarters "
    "are already close enough to their limits that there is nothing to move — "
    "so this is the published spread. You can still change any single quarter "
    "when we walk through it.\n\n")

# Asked before the load spread, because it changes WHICH courses are picked
# rather than where they sit -- `profile_from_intake` averages the technical
# areas into the comfort level `_pick` and `rank_electives` both read.
#
# It used to be five sliders on a form. Asked in prose it is one line back, and
# partial answers are fine: rating two areas and ignoring three is a real
# answer, and the rest are assumed and said to be assumed.
ASK_FOR_SKILLS = (
    "Two quick things and I'll build it.\n\n"
    "**First — where are you starting from technically?** Rate yourself 1–5 on "
    "any of these that you have a view on:\n\n"
    "- **Python**\n- **SQL and databases**\n- **Statistics and regression**\n"
    "- **Machine learning**\n- **Presenting and storytelling**\n\n"
    "However you'd say it: _\"python 4, sql 2\"_, _\"strong in python, never "
    "done ML\"_, or just _\"skip\"_ and I'll assume the middle of the scale. "
    "This decides how far I stretch you, not whether you get the courses you "
    "need.")

# Said when a title was matched with a character of slop. Confirmed rather
# than assumed: guessing which of fourteen careers someone meant is not a
# guess to make quietly.
FUZZY_ROLE_NOTE = (
    "Reading **{said}** as **{label}** — say the word if you meant something "
    "else.\n\n")

ASK_FOR_A_GOAL = (
    "Good \u2014 **{track}** it is. What are you aiming for after the "
    "programme?\n\nAny job title works \u2014 \"data scientist\", "
    "\"pricing analyst\", \"product manager\" \u2014 or name an industry "
    "and I'll work from what that field is currently asking for.")


GOAL_SWITCHED = "Switched to **{label}**.\n\n"

ELECTIVES_CHANGED = (
    "That changes the electives: **{gained}** in, **{lost}** out.\n\n")

ELECTIVES_UNCHANGED = (
    "The recommended electives come out the **same** for both — in this "
    "catalog, {before} and {after} draw on the same set. What moves is the "
    "emphasis and the order, not the courses. Here it is again under the new "
    "heading so the plan says what it is for.\n\n")


def _goal_change_note(previous, answers, user):
    """What changed, when the goal did. "" when it did not.

    THE fix for a plan that looked like a repeat. A student who switched from
    data analyst to consultant got a plan with an identical header, an
    identical Summer (it is entirely required) and no mention anywhere of
    which career it was for -- so a rebuild that really had happened read as
    the bot saying the same thing twice.

    Saying the electives are unchanged, where they are, is the honest half of
    this. Two career profiles in a 24-elective catalog can genuinely resolve
    to the same six courses, and pretending otherwise -- or silently
    reprinting -- is worse than naming it.
    """
    before = list((previous or {}).get("goals") or [])
    after = list((answers or {}).get("goals") or [])
    if not after or before == after:
        return ""
    careers = load_careers()
    label = careers.get(after[0], {}).get("label", after[0])
    note = GOAL_SWITCHED.format(label=label)
    if not before:
        return note
    # The student's own enrolments, so the verdict below is about the plan
    # they would actually be shown rather than about a hypothetical one.
    taken = planner.taken_course_ids(user)
    old_plan = planner.build_for({**answers, "goals": before}, taken)
    new_plan = planner.build_for(answers, taken)
    was, now = planner.elective_codes(old_plan), planner.elective_codes(new_plan)
    if was == now:
        return note + ELECTIVES_UNCHANGED.format(
            before=careers.get(before[0], {}).get("label", before[0]),
            after=label)
    gained, lost = sorted(now - was), sorted(was - now)
    if gained or lost:
        return note + ELECTIVES_CHANGED.format(
            gained=", ".join(gained) or "nothing new",
            lost=", ".join(lost) or "nothing")
    return note


UNCURATED_COVERAGE = (
    "\n\n_On **{goal}**: this plan covers about **{share:.0%}** of what that "
    "career asks for. {gap}_")
UNCURATED_GAP = "It has nothing here for {unmet}."
UNCURATED_NO_GAP = "Everything I found it asking for is covered somewhere in it."
UNCURATED_DROPPED = (
    "\n\n_{dropped} matched your career but didn't fit the unit limits — ask "
    "me to swap {one} in and I'll show you what it would displace._")


def _uncurated_coverage_note(answers, plan):
    """How much of an uncurated career the FINISHED plan covers, or "".

    The recommendation already quotes a coverage figure, and that figure is
    about the six courses it recommended. The plan is not those six courses:
    quarters have unit floors and ceilings, and a course that does not fit is
    dropped. So the number a student was given could describe a set they were
    never actually shown -- stated to the digit, and quietly wrong.

    Recomputed here against the courses that survived scheduling. The
    discrimination weights still come from the WHOLE catalog, so the share
    stays comparable with the one quoted earlier; only the pool being measured
    narrows.

    Curated careers are not measured. Their bundle IS the answer to what the
    career needs -- a hand-authored mapping, not a match -- so scoring it
    against scraped requirements would be marking our own advising against a
    web page.
    """
    goal = answers.get("unmatched_goal")
    wanted = answers.get("goal_skills") or []
    if not goal or not wanted or not plan:
        return ""
    placed = {course["courseId"]: course
              for quarter in plan.get("quarters") or []
              for course in quarter.get("courses") or []}
    if not placed:
        return ""
    rows = [course for course in electives.load_catalog()
            if course["id"] in placed]
    if not rows:
        return ""
    fits = skill_match.rank(wanted, catalog=rows, limit=len(rows))
    cover = skill_match.coverage(wanted, fits)
    unmet = cover["unmet"][:4]
    note = UNCURATED_COVERAGE.format(
        goal=goal, share=cover["metShare"],
        gap=(UNCURATED_GAP.format(unmet=", ".join(unmet)) if unmet
             else UNCURATED_NO_GAP))
    # Naming what fell out matters more than the percentage: the student was
    # shown these courses by name one turn ago, and silently dropping one reads
    # as the plan disagreeing with the recommendation for no stated reason.
    dropped = [code for code in (answers.get("goal_courses") or [])
               if code not in placed]
    if dropped:
        shown = [planner.display_code({"code": code}) for code in dropped[:3]]
        note += UNCURATED_DROPPED.format(
            dropped=", ".join(f"**{code}**" for code in shown),
            one=f"**{shown[0]}**")
    return note


def _plan_now(conversation, answers, previous=None):
    """Build and show the plan, saying what was assumed rather than asking.

    `fill_assumed_skills` supplies a low-middle level for every skill area the
    student has not mentioned. Deliberately low: under-claiming keeps courses
    in reach and the plan says what it assumed, where over-claiming puts
    someone in a course they cannot pass.
    """
    filled, assumed = planner.fill_assumed_skills(
        answers, [f"skill_{area['key']}" for area in planner.SKILL_AREAS])
    track = filled.get("track") or "11 month"
    load = filled.get("workload")
    lead = ""
    if not load:
        lead += ASSUMED_LOAD_NOTE
    elif not filled.get("quarter_units"):
        # Turn the one-word answer into a real distribution, once. A later
        # per-quarter answer wins, so this never overwrites a decision.
        seeded = planner.seeded_units(track, load)
        if seeded:
            filled = {**filled, "quarter_units": seeded}
            lead += LOAD_APPLIED_NOTE.format(
                load=load, total=planner.TOTAL_UNITS,
                spread=", ".join(
                    f"{planner.quarter_label(track, key)} {units} units"
                    for key, units in seeded.items()))
        elif load != "moderate":
            lead += LOAD_UNAVAILABLE_NOTE.format(load=load, track=track)
    planner.save_session_intake(conversation, filled)
    # For an uncurated career there is no bundle, so what was matched from the
    # web IS the recommendation: pin it where it fits and let the scorer fill
    # the rest. See `planner.selections_for_courses`.
    pinned = planner.selections_for_courses(
        filled, filled.get("goal_courses") or [],
        planner.taken_course_ids(conversation.user))
    reply = _plan_reply(conversation.user, filled, pinned)
    tail = _uncurated_coverage_note(filled, reply.plan)
    lead = _goal_change_note(previous, filled, conversation.user) + lead
    if assumed:
        # The level is read off `ASSUMED_SKILL` rather than written out here.
        # It used to say "some exposure" as a literal, and when the assumed
        # level moved off "basic" the sentence would have been describing a
        # value the plan was no longer built on.
        level = planner.skill_label(planner.ASSUMED_SKILL)
        lead += (f"I've assumed **{level}** for " + ", ".join(assumed)
                 + " since you haven't said \u2014 tell me where that's wrong "
                   "and I'll redo it.\n\n")
    return spoken(BotReply(lead + reply.body + tail, [], "plan",
                           reply.quick_replies, route="plan"))


def _confirmation(question):
    """A line confirming a role read with a character of slop, or "".

    Prefixed onto whatever question comes next, so the confirmation and the
    next step are one turn rather than two.
    """
    role_id, exact = router.role_match(question)
    if not role_id:
        return ""
    # Confirmed for two different readings, both of which put a career in front
    # of a student who did not quite name it: a MISSPELLED title, and an AREA
    # that matched a career off its short label. "Something in supply chain"
    # came back as the full Supply Chain / Operations Analytics set with
    # nothing saying that was a reading.
    if exact and router.names_a_job_function(question):
        return ""
    label = (load_careers().get(role_id) or {}).get("label", role_id)
    said = " ".join((question or "").split())[:40]
    return FUZZY_ROLE_NOTE.format(said=said, label=label)


def named_only_a_track(question):
    """True when the track is the ONLY thing this turn says.

    The goal question is worth asking for "11 month" and insulting for "11
    month fintech". The test is what survives removing the track phrase and the
    words that wrap any answer -- `_ROLE_FILLER` already holds those, down to
    "industry" and "something", because it was written for exactly this job on
    the role path.

    Deliberately blind to WHAT is left over. Judging that is the router's work
    and it has a model to do it with; all this decides is whether there is
    anything there to judge.
    """
    remainder = question or ""
    for pattern in _TRACK_WORDS.values():
        remainder = pattern.sub(" ", remainder)
    return not [word for word in re.findall(r"[a-z0-9+#/-]+", remainder.lower())
                if word not in _ROLE_FILLER]


def _intake_progress(conversation, question, answers):
    """A turn that moved the plan forward, or None.

    Runs before the router and produces no question of its own except one: a
    student who has named a track and nothing else has not said what the plan
    is FOR, and a plan of study built around no goal is just the published
    skeleton. That is the only genuinely blocking gap on this route, so it is
    the only thing asked.
    """
    learned = learned_from(question)
    merged = {**answers, **learned}
    changed = any(merged.get(key) != answers.get(key) for key in learned)
    if learned.get("track") and answers.get("track") \
            and learned["track"] != answers["track"]:
        # The spread belongs to the OLD track's shape. Quarter keys differ
        # between the two -- only the 17-month track has a second Fall -- so
        # carrying it across loses a quarter's worth of units and the loads the
        # student chose no longer describe the quarters they now have.
        # Re-seeded below from the overall preference, which does still apply.
        merged.pop("quarter_units", None)
        merged.pop("quarter_loads", None)
        # And where the walk-through had got to: that index counts quarters in
        # the OLD track's sequence, and the two tracks have different numbers
        # of them.
        planner.clear_session_review(conversation)
        if merged.get("workload"):
            seeded = planner.seeded_units(learned["track"], merged["workload"])
            if seeded:
                merged["quarter_units"] = seeded
    if learned and changed:
        planner.save_session_intake(conversation, merged)

    if planner.declines_skills(question):
        # Declining IS an answer, and it must be recorded or the question comes
        # back on the next turn.
        planner.note_session_asked(conversation, "skills")
    # `unmatched_goal` counts. A career the catalog curates no id for is still
    # a career the student named -- see `planner.next_intake_step`.
    plannable = bool(merged.get("track")
                     and (merged.get("goals") or merged.get("unmatched_goal")))
    if plannable:
        # Both questions are asked once, and only once. A student who answers
        # with something else gets their plan on the NEXT turn with what was
        # assumed said out loud: an interview with no exit is the thing being
        # removed, so the exit is recorded rather than rediscovered.
        if (not any(key.startswith("skill_") for key in merged)
                and not planner.session_has_asked(conversation, "skills")):
            planner.note_session_asked(conversation, "skills")
            return BotReply(_confirmation(question) + ASK_FOR_SKILLS, [],
                            "intake", route="plan")
        if (not merged.get("workload")
                and not planner.session_has_asked(conversation, "workload")):
            planner.note_session_asked(conversation, "workload")
            return BotReply(_confirmation(question) + ASK_FOR_A_LOAD, [],
                            "intake", route="plan")
        # Delivered automatically exactly once -- that is the answer to what
        # they asked for. After that it is reprinted only when this turn
        # changed something the plan is built from, so "thanks" and "how do I
        # enrol?" do not each reprint 3,700 characters.
        if not planner.session_has_asked(conversation, "plan"):
            planner.note_session_asked(conversation, "plan")
            return _plan_now(conversation, merged, answers)
        if changed:
            return _plan_now(conversation, merged, answers)
        return None
    if not learned or not changed:
        return None
    if merged.get("track") and "goals" not in learned:
        if named_only_a_track(question):
            return BotReply(ASK_FOR_A_GOAL.format(track=merged["track"]), [],
                            "intake", route="plan")
        # The turn named a track AND something else. Asking here would throw
        # the something else away and put back the question it answers: "11
        # month fintech" was met with "what are you aiming for? ... or name an
        # industry", which the student had just done. Falling through hands the
        # turn to the router, which can place "fintech" -- and the track is
        # already saved above, so nothing is lost either way.
        return None
    # A goal with no track yet: the role route answers it properly, with the
    # curated bundle, and asks for the track at the end of that.
    return None


# ---------------------------------------------------------------------------
# Route: a role the catalog curates
# ---------------------------------------------------------------------------

FIT_LINE = {
    "anchor": "the spine of this path — take these",
    "differentiator": "what separates a strong candidate from a competent one",
    "universal": "everyone takes these, whatever the path",
}


def curated_recommendation(role_id):
    """The curated bundle for a role, as Markdown. No model involved at all.

    THE quality floor. Fourteen roles have a hand-authored mapping in
    `bundles.json` and those stay authoritative — "I want to be a data
    scientist" gets our recommendation, not a model's guess at one. Every
    course named here is looked up in the catalog, so a code that does not
    exist cannot be printed.
    """
    bundle = bundles.bundle_for(role_id)
    if not bundle:
        return None
    role = load_careers().get(role_id) or {}
    catalog = {course["id"]: course for course in load_catalog()}
    lines = [f"**{role.get('label', role_id)}** — {role.get('work', '')}".rstrip(" —"),
             ""]
    if role.get("gate"):
        lines += [f"_{role['gate']}_", ""]
    # A RECOMMENDATION, said as one. It used to read "the elective set the
    # programme recommends for that path -- a curated mapping, not a guess",
    # which claims more standing than this has: the mapping is ours, it is
    # advice, and a student reading it as the programme's official position
    # would be reading it wrongly. What it IS -- deterministic, the same for
    # everyone with this goal, not a model's improvisation -- is a property
    # worth having and not a reason to sound authoritative about it.
    lines.append("Here's what I'd recommend for that path:")
    for layer in ("anchor", "differentiator", "universal"):
        codes = [code for code in (bundle.get(layer) or []) if code in catalog]
        if not codes:
            continue
        lines += ["", f"**{layer.title()}** — {FIT_LINE[layer]}"]
        for code in codes:
            course = catalog[code]
            seasons = sorted({o["season"] for o in course.get("offerings") or []})
            lines.append(
                f"- **{course['code']} — {course['title']}** "
                f"({course['units']} units"
                + (f", offered {', '.join(seasons)}" if seasons else "")
                + ")")
    lines += _enrolment_caveats(
        [code for layer in ("anchor", "differentiator", "universal")
         for code in (bundle.get(layer) or []) if code in catalog])
    lines += ["", planner.RECOMMENDATION_ONLY,
              "", "Tell me which track you're on — **11-month** or **17-month** "
                  "— and I'll lay this out quarter by quarter as a full plan of "
                  "study."]
    return "\n".join(lines)


def _enrolment_caveats(codes):
    """Say, per programme, on what terms a non-MSBA course can be taken.

    Recommending a course a student cannot actually enrol in is a bad failure,
    and it is a silent one: the recommendation looks identical to a good one
    right up until enrolment is refused. The catalog carries CSE, MBA (MGT) and
    MFin (MGTF) entries under `DEPARTMENT_LABELS`, which states the terms —
    consent for MGT/MGTF, and CSE majors having priority so CSE seats go as
    space permits — and that belongs beside the recommendation rather than in a
    data file nobody reads.

    Note that this states the CATALOG'S OWN terms, not a claim that the list is
    authoritative. Whether the CSE entries are the courses MSBA students may
    actually take is an open question with the programme office; until it is
    answered, saying "confirm before you plan around it" is the honest form of
    a recommendation we are not certain we can stand behind.
    """
    from rsm_thrive.services.electives import DEPARTMENT_LABELS

    seen = []
    for code in codes:
        prefix = code.split()[0]
        if prefix != "MGTA" and prefix not in seen:
            seen.append(prefix)
    if not seen:
        return []
    lines = ["", "**Before you plan around these:**"]
    for prefix in seen:
        name, terms = DEPARTMENT_LABELS.get(prefix, (prefix, ""))
        lines.append(f"- {prefix} courses are {name} — {terms}."
                     if terms else f"- {prefix} courses are {name}.")
    lines.append(f"- Up to {NON_MSBA_UNIT_CAP} of the 28 elective units may "
                 f"come from outside the MSBA's own courses. Confirm any "
                 f"non-MGTA course with MSBA advising before you count on it.")
    return lines


UNCOVERED_ROLE_PREFIX = (
    "I don't have a set recommendation ready for **{role}**, so rather than "
    "guess I looked up what that job actually asks for and matched it against "
    "this catalog.\n\n")


def _answer_role(llm, route, conversation, question, history):
    body = curated_recommendation(route.role_id) if route.role_id else None
    if body:
        body = _confirmation(question) + body
        # Remember the goal, so a follow-up naming a track builds the right
        # plan without asking the student to say the role again.
        stored = planner.load_session_intake(conversation)
        planner.save_session_intake(conversation, {**stored, "goals": [route.role_id]})
        return BotReply(body, [], "curated", route=router.ROLE,
                        route_confidence=route.confidence)
    return _uncurated_role(llm, route, conversation, question)


# Words that are ALWAYS in a question and never distinguish one job from
# another. What is left after these is what the student actually named.
_ROLE_FILLER = frozenset("""
a an the i im i'm want wants wanted like would love to be become work working
in into on at for with about something anything some kind sort area field
industry sector space world side of my me you what how do does can could
job role career position work maybe perhaps think thinking interested
it its them they there here part bit stuff thing things doing get getting
that this those these actually just really please yeah yes ok
""".split())


def invented_job_function(said, role):
    """The job the model named that the student did not, or "".

    The guard against answering a question nobody asked. "What about something
    in esports" came back as a full recommendation for **esports operations
    coordinator** -- a job title the student had not said, followed by a list
    of "your target requirements" they had never given. The recommendation was
    perfectly good and it was for somebody else's career.

    It is the HEAD NOUN that decides, the last word of the title, because that
    is the job FUNCTION -- analyst, engineer, coordinator, biologist -- and
    inventing one is the whole failure. The modifiers are not the same thing: a
    student who typed "airscpae engineer" said "engineer" and merely misspelled
    the domain, and one who said "climate risk modeller" is not asking to be
    quizzed on whether they meant "modeler".

    Detecting invention rather than listing job nouns is deliberate. A list
    would have to know "biologist", "actuary", "modeller" and whatever comes
    next, and would be wrong about the one after that. "Did we make this up, or
    did they say it?" is exact, and it is the actual question.
    """
    import re as _re

    spoken = {word for word in _re.findall(r"[a-z]+", (said or "").lower())
              if word not in _ROLE_FILLER}
    proposed = [word for word in _re.findall(r"[a-z]+", (role or "").lower())
                if word not in _ROLE_FILLER]
    if not proposed:
        return ""
    head = proposed[-1]
    if any(router._within_one_edit(head, word) for word in spoken):
        return ""
    return head


def _student_words(question):
    """What the student actually named, with the sentence around it removed.

    Taken from the QUESTION rather than from `route.unmatched_role`, which is
    the model's extraction and can be thinner than what was said: scripted with
    a classifier that reported "esports" for a turn that read "esports
    analyst", the reply came back about **esports** -- dropping the very word
    the student had added to answer the question we had just asked them.
    """
    import re as _re

    words = [word for word in _re.findall(r"[a-z0-9+#/-]+", (question or "").lower())
             if word not in _ROLE_FILLER]
    return " ".join(words)[:60]


def curated_near(area):
    """Careers we DO have a ready-made set for that mention this area.

    Asked before falling back on the model's guess, because the model's guess
    is often poor and ours is always relevant: "I want to work in healthcare"
    was met with "I could read that as **healthcare worker**" -- an improvised
    title, for a programme that has a hand-written Healthcare / Life Sciences
    Analytics set sitting right there. Suggesting the curated one both answers
    better and lands the student on the stronger plan.
    """
    word = " ".join((area or "").lower().split())
    if not word:
        return []
    out = []
    for role in load_careers().values():
        haystack = " ".join(
            [role.get("label", ""), role.get("short_label", "")]
            + list(role.get("titles") or [])).lower()
        if word in haystack:
            out.append(role["label"])
    return out


ASK_WHAT_KIND_OF_WORK_CURATED = (
    "**{area}** — what kind of work do you want to do in it?\n\n"
    "The courses differ a lot between, say, analytics, operations and "
    "marketing, so a job title is enough. {closest} is the closest thing I "
    "have a ready-made set for — say that, or name a different job title.")

ASK_WHAT_KIND_OF_WORK = (
    "**{area}** — what kind of work do you want to do in it?\n\n"
    "I could read that as **{guess}**, but that is my reading rather than "
    "something you said, and the courses differ a lot between, say, analytics, "
    "operations and marketing. A job title is enough.\n\n"
    "Or just say **yes** and I'll go with that reading.")

_ACCEPTANCES = frozenset({
    # Yes, in the ways people type it. "yup" was missing and that alone broke
    # the flow: the student answered the question, was not understood, and got
    # the generic opening back as if they had said nothing.
    "yes", "yep", "yup", "yeah", "yea", "ya", "y", "aye", "yes please",
    "correct", "that's right", "thats right", "right", "exactly", "spot on",
    "that works", "that one", "go with that", "go with it", "use that",
    "sounds good", "sounds right", "perfect", "great", "fine", "ok", "okay",
    "sure", "please", "go ahead", "go on", "do it", "lets do that",
    "let's do that", "that's the one", "thats the one",
    # And "I don't mind", which is an acceptance of whatever we suggested.
    "anything", "any", "anything works", "whatever", "not sure", "no idea",
    "dunno", "don't mind", "dont mind", "no preference", "you choose",
    "you decide", "either", "up to you",
})


def _accepts_the_guess(question):
    """Is this whole message a "yes" to the reading we offered?

    Whole-message and punctuation-insensitive, so "yup!" and "Yes." count. A
    closed list is fragile here in exactly the way it is everywhere else -- the
    guard against that is not a longer list but `answer`, which sends anything
    unrecognised BACK to the question it was answering rather than treating it
    as a fresh topic.
    """
    import re as _re

    lowered = " ".join(_re.sub(r"[^a-z' ]+", " ", (question or "").lower()).split())
    return lowered in _ACCEPTANCES


UNCURATED_NEXT = (
    "\n\n" + planner.RECOMMENDATION_ONLY
    + "\n\n---\n\nTell me which track you're on — **11-month** or "
      "**17-month** — and I'll build the whole plan of study around these.")


def _uncurated_role(llm, route, conversation, question):
    """A real job with no bundle: look up what it needs, match our catalog.

    Same two-stage shape the rest of this module uses. The model says what the
    JOB requires; `role_lookup.courses_for_role` decides which of OUR courses
    teach that. The model never picks a course, so it can never name one that
    does not exist.

    The GOAL and the matched courses are then remembered, and that is the part
    that was missing. A student who said "esports analyst" got a good grounded
    list and then, on their very next turn, was asked what they were aiming for
    -- the career they had just named -- and never reached a plan at all. An
    uncurated career is still a career: `selections_for_courses` pins what was
    matched into the slots it fits and the scorer fills the rest, so the answer
    ends in a plan of study like every other route.
    """
    from rsm_thrive.services import role_lookup

    stored = planner.load_session_intake(conversation)
    # A guess the student was offered last turn and has just accepted. Their
    # "yes" is not a job title, so the suggestion becomes the name.
    accepted = bool(stored.get("suggested_goal")) and _accepts_the_guess(question)
    # What to look up, best source first. `ROLE_SYSTEM` asks the model to
    # describe a JOB, so it has to be handed something job-shaped: given the
    # raw sentence "I want to do somthign in esports" it answered known=false
    # -- correctly, that is not a job -- and the whole route collapsed into a
    # refusal that had searched for nothing.
    #
    # `route.industry` matters most here. `unmatched_role` is only ever set on
    # a ROLE or COMBINATION route, so an INDUSTRY route arrived with nothing
    # but the sentence -- and which of the two the classifier picks for "I want
    # to do something in esports" is not stable between runs.
    named = stored["suggested_goal"] if accepted else (
        route.unmatched_role or route.industry
        or _student_words(question) or question)
    profile = role_lookup.skills_for_role(llm, named)
    if profile and accepted:
        profile = {**profile, "role": stored["suggested_goal"]}

    # Did the model name a job the student did not?
    # Ask whenever the student named no JOB at all, whatever the model came
    # back with. The invention check alone was not enough: on one run the model
    # echoed the student's own words closely enough to pass it, and the plan
    # came out headed "somthign esports" -- a typo promoted to a career.
    if (profile and not accepted
            and not router.names_a_job_function(_student_words(question))
            and not planner.session_has_asked(conversation, "what-work")):
        planner.note_session_asked(conversation, "what-work")
        planner.save_session_intake(
            conversation, {**stored, "suggested_goal": profile["role"][:60]})
        area = " ".join(word for word in (route.industry or named).split()
                        if word.lower() not in _ROLE_FILLER) or named
        close = curated_near(area)
        if close:
            planner.save_session_intake(
                conversation, {**stored, "suggested_goal": close[0]})
            return BotReply(ASK_WHAT_KIND_OF_WORK_CURATED.format(
                area=area,
                closest=", ".join(f"**{label}**" for label in close[:2])),
                [], "intake", route=router.ROLE,
                route_confidence=route.confidence)
        return BotReply(
            ASK_WHAT_KIND_OF_WORK.format(area=area, guess=profile["role"]),
            [], "intake", route=router.ROLE, route_confidence=route.confidence)

    if profile and not accepted:
        # Compared against what the STUDENT wrote, not against
        # `route.unmatched_role` -- that is the model's own extraction, so
        # comparing the two asks whether the model agrees with itself. Measured:
        # a classifier that read "I want to work in esports" as the role
        # "esports analyst" made "analyst" look spoken, and the check passed on
        # a word the student had never typed.
        invented = invented_job_function(_student_words(question), profile["role"])
        if invented and not planner.session_has_asked(conversation, "what-work"):
            # Offer it, do not assert it.
            planner.note_session_asked(conversation, "what-work")
            planner.save_session_intake(
                conversation, {**stored, "suggested_goal": profile["role"][:60]})
            area = " ".join(
                word for word in (route.industry or named).split()
                if word.lower() not in _ROLE_FILLER) or named
            close = curated_near(area)
            if close:
                # Suggest OUR set rather than the model's improvisation, and
                # remember it as the guess so "yes" accepts something real.
                planner.save_session_intake(
                    conversation, {**stored, "suggested_goal": close[0]})
                named_close = (f"**{close[0]}**" if len(close) == 1 else
                               ", ".join(f"**{label}**" for label in close[:2]))
                body = ASK_WHAT_KIND_OF_WORK_CURATED.format(
                    area=area, closest=named_close)
            else:
                body = ASK_WHAT_KIND_OF_WORK.format(
                    area=area, guess=profile["role"])
            return BotReply(body, [], "intake", route=router.ROLE,
                            route_confidence=route.confidence)
        # The NAME is the student's, always. The lookup is worth having --
        # what the model knows about the WORK is why we asked it -- but it
        # gets the job title wrong in both directions: it RENAMED "esports
        # analyst" to "data analyst", and it THINNED it to plain "analyst",
        # losing the very word the student had added. Either way the heading
        # ends up describing somebody else's career.
        profile = {**profile, "role": _student_words(question) or profile["role"]}

    matches = role_lookup.courses_for_role(profile) if profile else []
    found = role_lookup.explain_fit(
        llm, profile, matches, role_lookup.coverage_for_role(profile)) \
        if matches else ""
    if found:
        stored = planner.load_session_intake(conversation)
        settled = {**stored,
                   "unmatched_goal": profile["role"][:60],
                   "goal_courses": [row["course"]["id"] for row in matches],
                   # The requirements themselves, not just what matched them.
                   # Without these the plan cannot check its OWN coverage: the
                   # figure quoted with the recommendation is about the six
                   # courses that were recommended, and scheduling does not
                   # promise to keep all six.
                   "goal_skills": ((profile.get("skills") or [])
                                   + (profile.get("tools") or [])
                                   + (profile.get("topics") or []))[:40]}
        # The question has been answered; the suggestion must not go on
        # capturing later turns.
        settled.pop("suggested_goal", None)
        planner.save_session_intake(conversation, settled)
        return BotReply(
            UNCOVERED_ROLE_PREFIX.format(role=profile["role"]) + found
            # Before the what-next prompt, so the sources sit against the
            # claims they support rather than after a change of subject.
            + role_lookup.cite(profile)
            + UNCURATED_NEXT, [], "role-web", route=router.ROLE,
            route_confidence=route.confidence)
    # Cleared here too. Left set, a lookup that came back empty repeated its
    # refusal for ever: "yup", "11 month", "skip" and "moderate" each came back
    # with the same paragraph, because the question was still capturing turns
    # long after it had been answered.
    if stored.get("suggested_goal"):
        planner.save_session_intake(
            conversation, {key: value for key, value in stored.items()
                           if key != "suggested_goal"})
    return BotReply(planner.uncovered_career_reply(named), [],
                    "no-track", route=router.ROLE,
                    route_confidence=route.confidence, refused=True)


# ---------------------------------------------------------------------------
# Route: an industry we have no bundle for
# ---------------------------------------------------------------------------

NO_INDUSTRY_MATCH = (
    # No claim about what was searched. This is reached from two paths -- a
    # lookup that ran and found nothing, and one that could not run at all --
    # and the old wording asserted a search either way.
    "I couldn't find enough of what that field asks for in the MSBA elective "
    "catalog to recommend anything honestly.\n\n"
    "I won't name a course without a catalog match — a plausible-sounding "
    "recommendation is worse than none. **MSBA advising** can tell you whether "
    "the programme supports that direction; you can book time from the "
    "**Appointments** tab.")


def _answer_industry(llm, route, conversation, question):
    """Web for the field's requirements, catalog for the courses. Never both.

    This is `grounded_course_advisor` unchanged, and it is where the aerospace
    case stops being plausible-and-unhelpful: when nothing in the catalog
    matches, the reply says so and names no course, rather than returning six
    courses that share the word "analytics" with the question.

    `recommend_for_question` returns None for TWO different reasons and they
    need different answers. Either the lookup ran and found nothing usable, or
    it never ran at all because the question is not shaped like an industry
    question. "Aerospace engineer" is the second: it names a JOB, the classifier
    called it an industry because "aerospace" is a field word, and the reply
    came back in 1.8 seconds saying "I searched for what that field currently
    asks for" -- a claim about a search that had not happened. Falling through
    to the role path both tells the truth and answers the question that was
    actually asked.
    """
    body, codes = recommend_for_question(llm, question)
    if body:
        return BotReply(body, [], "industry-catalog", route=router.INDUSTRY,
                        route_confidence=route.confidence, refused=not codes)
    reply = _uncurated_role(llm, route, conversation, question)
    if not reply.refused:
        return reply
    return BotReply(NO_INDUSTRY_MATCH, [], "industry-none",
                    route=router.INDUSTRY, route_confidence=route.confidence,
                    refused=True)


# ---------------------------------------------------------------------------
# Route: a role AND an industry
# ---------------------------------------------------------------------------

COMBINATION_JOIN = (
    "\n\n---\n\n**Now the {industry} part.** The spine above is fixed by the "
    "role; where the field changes things is which electives you pick around "
    "it. Here is what that field currently asks for, matched only against this "
    "catalog:\n\n")

COMBINATION_NO_FIELD = (
    "\n\n---\n\n_On the {industry} side: I searched for what that field asks "
    "for and couldn't match enough of it to this catalog to add anything "
    "beyond the set above. That set is still the right spine for the role._")


def _answer_combination(llm, route, conversation, question, history):
    """Role determinism for the spine, industry context on the electives.

    The order is the point. A role we curate has an authoritative answer and it
    goes first, in full; the industry lookup can only ever ADD colour to the
    elective choices around it. Letting the web half lead would put a
    probabilistic answer in front of a deterministic one for a question whose
    deterministic half we are sure about.
    """
    spine = _answer_role(llm, route, conversation, question, history)
    if spine.refused:
        # No curated spine to protect, so this is an industry question that
        # happened to mention a job title.
        return _answer_industry(llm, route, conversation, question)
    if not route.role_id:
        # The role path answered without a curated bundle -- a web-matched set,
        # or the question about which job they mean. Either way it is the
        # answer, and there is no spine to decorate.
        #
        # `spine.refused or not route.role_id` sent BOTH of those to the
        # industry path, which discarded a perfectly good clarifying question
        # and then re-ran the same lookup -- by which time `what-work` was
        # already marked as asked, so the second pass could only refuse.
        return spine
    industry_body, codes = recommend_for_question(llm, question)
    label = route.industry or "industry"
    if industry_body and codes:
        spine.body += COMBINATION_JOIN.format(industry=label) + industry_body
    else:
        spine.body += COMBINATION_NO_FIELD.format(industry=label)
    spine.route = router.COMBINATION
    spine.model_note = "curated+industry"
    return spine


# ---------------------------------------------------------------------------
# Route: a factual question about a course
# ---------------------------------------------------------------------------

FACTUAL_SYSTEM = (
    "You are THRIVE, answering a Rady MSBA student's factual question about "
    "courses.\n\n"
    "ABSOLUTE RULE: answer ONLY from the catalog entries and numbered passages "
    "below. Never state a unit count, a prerequisite, a quarter, a deadline or "
    "a policy that is not written there. Where the material does not say, say "
    "that it does not say — and for prerequisites, enrolment consent or "
    "approvals, send them to MSBA advising (bookable from the Appointments "
    "tab) rather than inferring.\n\n"
    "Name courses by code. Cite numbered passages like [1] where you used one. "
    "Be concise — at most four sentences or a short list. Do not recommend "
    "courses and do not ask a question back.")

FACTUAL_REFUSAL = (
    "I don't have catalog or syllabus material that answers that, and I'd "
    "rather not guess — a wrong prerequisite or unit count is the kind of "
    "mistake you'd only find out about at enrolment.\n\n"
    "**MSBA advising** can confirm it; you can book time from the "
    "**Appointments** tab.")


def _answer_factual(llm, route, question, history):
    """Structured catalog first, syllabus corpus second, both or nothing.

    `courses.json` is the source of truth for units, seasons, prerequisites and
    workload because it carries them as FIELDS; a retrieved prose chunk carries
    whatever a page happened to say. The corpus is still retrieved alongside,
    because a syllabus answers "what does this course actually cover" in a way
    a catalog row does not.
    """
    config = bot_config("electives")
    catalog = _catalog_context(question)
    hits = retrieve(question, "courses", config["top_k"],
                    config["min_similarity"], config.get("lexical_min"),
                    config.get("lexical_floor", 0.0))
    if not catalog and not hits:
        return BotReply(FACTUAL_REFUSAL, [], "refusal", route=router.FACTUAL,
                        route_confidence=route.confidence, refused=True)
    system = FACTUAL_SYSTEM
    if catalog:
        system += f"\n\nCatalog entries:\n\n{catalog}"
    if hits:
        system += f"\n\nContext passages:\n\n{build_context(hits)}"
    messages = (history[-config["max_history_turns"]:]
                + [{"role": "user", "content": question}])
    try:
        body = (llm.chat(system, messages) or "").strip()
    except Exception:
        body = ""
    if not body:
        return BotReply(FACTUAL_REFUSAL, [], "refusal", route=router.FACTUAL,
                        route_confidence=route.confidence, refused=True)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "catalog-rag",
                    route=router.FACTUAL, route_confidence=route.confidence)


# ---------------------------------------------------------------------------
# Route: where this student actually is
# ---------------------------------------------------------------------------

def _answer_situational(llm, route, conversation, question):
    """Deterministic arithmetic, model-written interpretation. See `situation`."""
    stored = planner.load_session_situation(conversation)
    body, asked, resolved = situation.answer(llm, conversation.user, question,
                                             stored)
    # Written whether or not anything was asked: a partial position is exactly
    # what the next turn needs, and a resolved one lets a follow-up ("what if I
    # take 16 units in Spring?") skip the extraction entirely. `awaiting` is
    # what brings a bare "winter" back here rather than to the classifier,
    # which has no way to know that one word is the answer to a question this
    # route asked one turn ago.
    planner.save_session_situation(conversation,
                                   {**stored, **resolved, "awaiting": asked})
    return BotReply(body, [], "situation", route=router.SITUATIONAL,
                    route_confidence=route.confidence)


# ---------------------------------------------------------------------------
# Route: one quarter, on its own
# ---------------------------------------------------------------------------

QUARTER_NEEDS_A_GOAL = (
    "I can plan **{label}** on its own — I just need to know what the plan is "
    "FOR. What are you aiming for after the programme? A job title is enough, "
    "or an industry.")

QUARTER_UNKNOWN = (
    "I couldn't tell which quarter you meant. On the {track} track they are: "
    "{quarters}. Say one of those and I'll plan just that one.")

QUARTER_LEAD = (
    "Here's **{label}** on its own. Say **next quarter** to carry on through "
    "the rest, or **show me the plan** for all {count} at once.")


def _answer_quarter(llm, route, conversation, question, answers):
    """One quarter, planned and shown by itself.

    A student asking "what should I take in Winter?" is asking a narrower
    question than "build my plan", and answering it with twelve courses across
    four quarters is answering a question they did not ask. The whole plan is
    still built underneath -- a quarter cannot be planned in isolation, because
    which electives are still available in Winter depends on what Spring and
    Fall took -- and only the quarter they asked about is shown.

    Deliberately NOT gated behind the load-spread question. That question earns
    its place before a whole plan of study; in front of one quarter it is an
    interruption, and the per-quarter load question is already in the output.
    """
    track = (answers.get("track") or stated_track(question)
             or _profile_track(conversation.user) or "11 month")
    key = planner.resolve_quarter(track, route.quarter or question)
    if key is None:
        return BotReply(
            QUARTER_UNKNOWN.format(
                track=track,
                quarters=", ".join(f"**{planner.quarter_label(track, k)}**"
                                   for k in planner.quarter_keys(track))),
            [], "quarter", route=router.QUARTER,
            route_confidence=route.confidence)

    label = planner.quarter_label(track, key)
    merged = {**answers, "track": track}
    if not merged.get("goals"):
        planner.save_session_intake(conversation, merged)
        return BotReply(QUARTER_NEEDS_A_GOAL.format(label=label), [], "intake",
                        route=router.QUARTER, route_confidence=route.confidence)

    filled, _assumed = planner.fill_assumed_skills(
        merged, [f"skill_{area['key']}" for area in planner.SKILL_AREAS])
    planner.save_session_intake(conversation, filled)
    plan = planner.build_for(filled, planner.taken_course_ids(conversation.user))
    index = next((position for position, quarter in enumerate(plan["quarters"])
                  if quarter["key"] == key), 0)
    reply = _review_reply(conversation, conversation.user, filled, index)
    lead = QUARTER_LEAD.format(label=label, count=len(plan["quarters"]))
    return spoken(BotReply(f"{lead}\n\n---\n\n{reply.body}", [], "quarter",
                           reply.quick_replies, route=router.QUARTER,
                           route_confidence=route.confidence))


def _profile_track(user):
    from rsm_thrive.models import StudentProfile

    profile = StudentProfile.objects.filter(user=user).first()
    return profile.track if profile else ""


# ---------------------------------------------------------------------------
# Routes that decline
# ---------------------------------------------------------------------------

OUT_OF_SCOPE = (
    "That's outside what I do — I'm the course planner, so I can answer "
    "questions about MSBA courses and electives, recommend courses for a "
    "career or an industry, and work out what's left in your plan of study.\n\n"
    "For anything else about the programme, **Ask THRIVE's Resources tab** "
    "answers from Rady's own material, and **MSBA advising** is bookable from "
    "the **Appointments** tab.")

DEGRADED = (
    "I can't reach my language model at the moment, so I can't work out what "
    "you're asking — that's a problem at my end, not with your question or "
    "with the course material.\n\n"
    "**What still works right now:** name a career and a track and I'll build "
    "the whole plan of study — _\"11 month, data scientist\"_ — then walk it "
    "quarter by quarter, change the load, or swap a course. None of that needs "
    "the model.\n\n"
    "What needs it back: questions about a specific course, industries and "
    "careers I have no ready-made set for, and working out where you are in "
    "the programme.")

UNCLEAR = (
    "I want to make sure I answer the right question. Are you asking about:\n\n"
    "- **a course** — what it covers, its units, when it runs;\n"
    "- **what to take** for a particular job or industry; or\n"
    "- **your own plan** — what's left, or how to finish on time?\n\n"
    "Tell me which and I'll go straight to it.")

# Said instead of the menu above when the conversation has established nothing
# yet -- a greeting, or a first message nobody could route. The three-shapes
# menu is the right answer to a question that was unclear; it is a cold answer
# to "hi", and it made the reply carry the menu AND the offer to plan
# underneath it, which is two invitations for one word.
UNCLEAR_OPENING = (
    "Happy to help — tell me **what you're aiming for after the programme** "
    "(a job title like \"data scientist\", or an industry) and **which track** "
    "you're on, the 11-month or the 17-month, and I'll lay out your whole plan "
    "of study.\n\n"
    "Or ask me something narrower — whether a course has prerequisites, what "
    "to take in one particular quarter — and I'll start there instead.")


def _decline(route, llm, conversation, question, answers):
    if route.name == router.DEGRADED:
        # Never `refused`: the corpus is fine, we could not reach the model.
        # Counting an outage as a content gap would put it straight into the
        # refusal report, which is meant to be the list of material to write.
        return BotReply(DEGRADED, [], "degraded", route=router.DEGRADED,
                        route_confidence=route.confidence)

    """Say plainly that this is not something we do, or ask which of three.

    With a plan already on screen there is a third case and it is the common
    one: "thanks", "ok", "that's helpful". Those are not out of scope and they
    are not unclear -- they are small talk, and answering them with a scope
    refusal or a menu of three question types reads as a bot that has stopped
    listening. `_small_talk_reply` answers in two sentences and never reprints
    the plan.
    """
    if planner.next_intake_step(answers) is None:
        reply = _small_talk_reply(llm, conversation.user, answers, question,
                                  planner.is_question(question))
        reply.route = route.name
        reply.route_confidence = route.confidence
        return reply
    if route.name == router.OUT_OF_SCOPE:
        return BotReply(OUT_OF_SCOPE, [], "out-of-scope",
                        route=router.OUT_OF_SCOPE,
                        route_confidence=route.confidence, refused=True)
    if not answers.get("track") and not answers.get("goals"):
        # `model_note` is what stops `_with_a_way_back` adding the offer to
        # plan underneath: this reply already IS that offer.
        return BotReply(UNCLEAR_OPENING, [], "unclear-opening",
                        route=router.UNCLEAR, route_confidence=route.confidence)
    return BotReply(UNCLEAR, [], "unclear", route=router.UNCLEAR,
                    route_confidence=route.confidence)


# ---------------------------------------------------------------------------
# No buttons anywhere on this surface
# ---------------------------------------------------------------------------

def spoken(reply):
    """Turn a reply's buttons into a line of things the student can SAY.

    The click flow is gone, and that includes the shortcuts under a finished
    plan. They were never the interview, but they were still buttons, and a
    surface that answers free text and then hands back a row of chips is two
    interaction models in one conversation.

    The affordance is not dropped, only respoken. Every `send` string was
    already an ordinary sentence -- that was the point of them, so the
    transcript read as though the student had typed it -- and `route_intent`,
    `review_intent` and `mentioned_codes` all parse the same words whether
    they arrive from a button or a keyboard. Derived from the buttons
    themselves rather than written out again, so the two cannot drift.
    """
    if not reply.quick_replies:
        return reply
    sends = [choice["send"] for choice in reply.quick_replies if choice.get("send")]
    reply.quick_replies = []
    reply.form = None
    if not sends:
        return reply
    # Navigation and the load answers first, swaps after, and only the swaps
    # are capped. A quarter with two elective slots offers six swaps, and a
    # flat cap put all six in the line and dropped "next quarter" and the
    # light/moderate/heavy answers off the end -- the two things a student is
    # most likely to want next, crowded out by the ones they are least likely
    # to type verbatim.
    swaps = [send for send in sends if send.lower().startswith("swap ")]
    listed = [send for send in sends if send not in swaps] + swaps[:3]
    spoken_line = " · ".join(f"**{send}**" for send in listed)
    reply.body = f"{reply.body}\n\n_You can say:_ {spoken_line}"
    return reply


# ---------------------------------------------------------------------------
# Maintaining a plan that already exists
# ---------------------------------------------------------------------------

NOT_ADJUSTABLE = (
    "**{label}** isn't adjustable — the published plan fills it entirely with "
    "required courses, so there is no elective room to move. Say **next "
    "quarter** and I'll show you one you can change.")

BLOCKED_BY_A_CHOICE = (
    "I can't make **{label}** {load} without moving {blockers} off the load "
    "you already chose for {them}. The degree is {total} units, so the ones "
    "you have decided about are the only place these could come from.\n\n"
    "Tell me to make {blockers} moderate again and I'll do both.{available}")

CANNOT_REBALANCE = (
    "I can't make **{label}** {load} at all. The programme is {total} units "
    "and Summer is fixed, so units taken out of one quarter have to land in "
    "another — and the others are already at their limits.{available}")


def _available_note(options, load):
    rest = [option for option in options if option["value"] != load]
    if not rest:
        return ""
    return (" What I can do here: "
            + ", ".join(f"**{o['value']}** ({o['units']} units)" for o in rest)
            + ".")


def _apply_quarter_load(conversation, answers, index, load):
    """Move one quarter to a light / moderate / heavy load, and rebuild.

    The units change and so does the recommendation: `_resized` re-cuts the
    quarter's elective slots to the new budget, so a quarter asked to carry 18
    units instead of 14 gets another elective slot and the scorer fills it.
    That is the whole point of asking here rather than on a form -- the student
    is looking at the courses the answer changes.

    What is OFFERED and what is applied come from the same call, so the
    walk-through can never propose a load this refuses.
    """
    user = conversation.user
    plan = planner.build_for(answers, planner.taken_course_ids(user))
    quarters = plan["quarters"]
    index = max(0, min(index, len(quarters) - 1))
    quarter = quarters[index]
    track = answers.get("track") or "11 month"
    chosen = answers.get("quarter_units") or {}
    decided = dict(answers.get("quarter_loads") or {})
    options = planner.load_options_for(track, quarter["key"], chosen,
                                       set(decided))

    if not planner.units_for_load(track, quarter["key"], "moderate"):
        return BotReply(NOT_ADJUSTABLE.format(label=quarter["label"]), [],
                        "review", route="plan")

    if decided.get(quarter["key"]) == load:
        # Said twice. Re-running the rebalance would produce the same numbers
        # and a reply claiming a change that did not happen.
        reply = _review_reply(conversation, user, answers, index)
        return spoken(BotReply(
            f"**{quarter['label']}** is already {load} — "
            f"{quarter['unitsPlanned']} units.\n\n---\n\n" + reply.body,
            [], "review", reply.quick_replies, route="plan"))

    offered = next((o for o in options if o["value"] == load), None)
    if offered is None:
        target = planner.LOAD_BOUNDS.get(load)
        bound = next((q for q in planner.adjustable_quarters(track)
                      if q["key"] == quarter["key"]), {})
        _wanted, blockers = planner.rebalanced_units(
            track, chosen, quarter["key"], bound.get(target, 0), set(decided))
        note = _available_note(options, load)
        if blockers:
            names = ", ".join(f"**{planner.quarter_label(track, key)}**"
                              for key in blockers)
            return BotReply(BLOCKED_BY_A_CHOICE.format(
                label=quarter["label"], load=load, blockers=names,
                them="it" if len(blockers) == 1 else "them",
                total=planner.TOTAL_UNITS, available=note),
                [], "review", route="plan")
        return BotReply(CANNOT_REBALANCE.format(
            label=quarter["label"], load=load, total=planner.TOTAL_UNITS,
            available=note), [], "review", route="plan")

    wanted, _blockers = planner.rebalanced_units(
        track, chosen, quarter["key"], offered["units"], set(decided))
    answers = {**answers, "quarter_units": wanted,
               "quarter_loads": {**decided, quarter["key"]: load}}
    planner.save_session_intake(conversation, answers)
    planner.save_intake(user, answers)

    others = [key for key in wanted if key != quarter["key"]]
    lead = [f"**{quarter['label']}** is now {load} — "
            f"{wanted[quarter['key']]} units.",
            "The other quarters absorbed it: "
            + ", ".join(f"{planner.quarter_label(track, key)} {wanted[key]} units"
                        for key in others)
            + f". The degree is still {planner.TOTAL_UNITS} units."]
    reply = _review_reply(conversation, user, answers, index)
    return spoken(BotReply("\n\n".join(lead) + "\n\n---\n\n" + reply.body,
                           [], "review", reply.quick_replies, route="plan"))


def _maintenance(llm, conversation, question, answers):
    """Acting on a plan already on screen, or None to route the question.

    Checked before the router because these are not questions about courses —
    they are operations on a plan. "next quarter" names nothing the classifier
    could recognise, and "swap 461 for 463" names two course codes and would be
    routed as a factual question about them.
    """
    user = conversation.user
    if planner.next_intake_step(answers) is not None:
        return None

    wanted_route = planner.route_intent(question)
    if wanted_route:
        answers = {**answers, "route": wanted_route}
        planner.save_session_intake(conversation, answers)
        reply = _plan_reply(user, answers)
        lead = ("Here it is built from the recommended bundle for that path."
                if wanted_route == "fixed"
                else "Here it is filled against your own skills and workload "
                     "instead.")
        return spoken(BotReply(f"{lead}\n\n{reply.body}", [], "plan",
                               reply.quick_replies, route="plan"))

    session = planner.load_session_review(conversation)

    # A load word, mid-walk-through, is about the quarter on screen. Checked
    # before `review_intent` because the two vocabularies do not overlap but
    # the ORDER states which reading wins, and before the change handler
    # because "light" names no course and would fall through to small talk.
    load = planner.load_intent(question)
    if session is not None and load:
        return _apply_quarter_load(conversation, answers, session["index"], load)

    intent = planner.review_intent(question)
    if intent == "finalise":
        return spoken(_finalise_reply(conversation, user, answers))
    if intent == "start":
        return spoken(_review_reply(conversation, user, answers, 0))
    if intent == "next" and session is not None:
        return spoken(_review_reply(conversation, user, answers, session["index"] + 1))

    if planner.is_question(question):
        explained = _explain_course(user, answers, question)
        if explained is not None:
            return explained

    change = _handle_change_request(user, answers, question)
    if change is not None:
        if session is not None:
            return spoken(_review_reply(conversation, user, answers, session["index"]))
        return change

    if _wants_the_plan(question):
        return spoken(_plan_reply(user, answers))
    return None


# ---------------------------------------------------------------------------
# Coming back to the plan
# ---------------------------------------------------------------------------

# The routes that answer something OTHER than "build my plan". After one of
# these, and while no plan exists yet, the reply offers to get back to it --
# the surface opened by asking two questions, and a student who answered
# neither should not have to remember that it was waiting.
#
# `role` and `combination` are absent because they already end by asking for
# the track, and `quarter` because it produces a plan. Adding them would put
# two invitations in one reply.
_DETOURS = frozenset({router.FACTUAL, router.INDUSTRY, router.OUT_OF_SCOPE,
                      router.UNCLEAR})

# Capped at two. Once is a helpful offer; on every turn it is a leaflet, and a
# student asking a run of catalog questions is doing something legitimate that
# does not need interrupting.
NUDGES = (
    "\n\n---\n\nWhenever you're ready: tell me **what you're aiming for** "
    "and **which track** you're on, and I'll lay out your whole plan of "
    "study — or name one quarter and I'll do just that one.",
    "\n\n_Still happy to build that plan — one line like _\"11 month, data "
    "scientist\"_ is enough._",
)


def _with_a_way_back(conversation, answers, reply):
    """Append the offer to plan, at most twice per conversation."""
    if reply.route not in _DETOURS or reply.model_note == "unclear-opening":
        return reply
    if answers.get("track") and answers.get("goals"):
        return reply            # the plan exists; nothing to come back to
    for position, nudge in enumerate(NUDGES):
        key = f"nudge-{position}"
        if planner.session_has_asked(conversation, key):
            continue
        planner.note_session_asked(conversation, key)
        reply.body += nudge
        return reply
    return reply


# ---------------------------------------------------------------------------
# The dispatcher
# ---------------------------------------------------------------------------

CAREERS_INTRO = (
    "I have ready-made pathways for **{count}** careers. Each one is a "
    "hand-built set of electives rather than something assembled on the "
    "spot:\n\n")
CAREERS_OUTRO = (
    "\n\nName any of them and I'll build the whole plan of study — say the "
    "track in the same breath (*\"11 month, data scientist\"*) and I'll go "
    "straight to it.\n\n**Not on the list?** Say what you're aiming for "
    "anyway. I'll look up what that job asks for, match it against this "
    "catalog, and tell you how much of it we actually cover — including the "
    "parts we don't.")


def _answer_careers(route):
    """The curated careers, listed. No model, no retrieval, no web.

    "What jobs do you have" is a closed question about our own data and it was
    getting a clarifying question back, which is the worst answer available: it
    asks the student to work out how to phrase something we could simply have
    told them.

    Read from `careers.json` rather than written out, so the list cannot drift
    from the bundles it promises. The last paragraph advertises the uncurated
    path on purpose -- a list of fourteen reads as a menu, and a student whose
    goal is not on it needs to know it is still a question worth asking.
    """
    careers = electives.load_careers()
    labels = sorted(
        (career.get("short_label") or career.get("label") or key)
        for key, career in careers.items())
    body = (CAREERS_INTRO.format(count=len(labels))
            + "\n".join(f"- **{label}**" for label in labels)
            + CAREERS_OUTRO)
    return BotReply(body, [], "careers", route=router.CAREERS,
                    route_confidence=route.confidence)


CATALOG_INTRO = (
    "I can plan across **{total} courses** — **{core} core** and "
    "**{electives} electives** — drawn from {programmes} programmes:\n\n")
CATALOG_CAP = (
    "\n**Up to {cap} of your 28 elective units** may come from outside the "
    "MSBA's own courses. The rest have to be MGTA.\n\n")
CATALOG_NEXT = (
    "Ask about any code and I'll tell you what it covers, what it needs first "
    "and when it runs — or name a career and a track (*\"11 month, data "
    "scientist\"*) and I'll build the whole plan around them.")


def _sentence(text):
    """First letter up, the rest untouched. `str.capitalize` lowercases the
    tail, which turns "pre-approved MSBA electives" into "msba"."""
    return text[:1].upper() + text[1:] if text else text


def _answer_catalog(route):
    """The catalog, broken down by programme. No model, no retrieval.

    A model handed 86 rows summarises them away: it answered "86 courses, 6
    core and 80 electives, all others are electives", which is arithmetic the
    student could already see and none of the context they asked for. The
    breakdown is the answer, and it comes from the catalog itself so it cannot
    drift from what the planner can actually schedule.

    Codes rather than titles for the other programmes. Eighty-six titles is a
    wall; the codes are scannable, grouped by what each programme IS, and any
    one of them can be asked about by name in the next turn -- which the
    closing line says.
    """
    overview = electives.catalog_overview()
    catalog = electives.load_catalog()
    body = CATALOG_INTRO.format(
        total=overview["total"], core=overview["core"],
        electives=overview["electives"], programmes=len(overview["programmes"]))

    for programme in sorted(overview["programmes"],
                            key=lambda p: (p["prefix"] != "MGTA", -p["total"])):
        rows = [c for c in catalog if c.get("department") == programme["prefix"]]
        body += (f"### {programme['name']} — {programme['total']} "
                 f"{'course' if programme['total'] == 1 else 'courses'}\n"
                 f"_{_sentence(programme['terms'])}._\n\n")
        core = [c for c in rows if c["is_core"]]
        if core:
            body += ("**Core** — everyone takes these, "
                     f"{sum(c['units'] for c in core)} units:\n\n")
            body += "".join(
                f"- **{planner.display_code(c)}** — {c['title']} ({c['units']}u)\n"
                for c in sorted(core, key=lambda c: c["code"]))
            body += "\n**Electives:**\n\n"
        electives_here = sorted((c for c in rows if not c["is_core"]),
                                key=lambda c: c["code"])
        if programme["prefix"] == "MGTA":
            # The home programme, listed in full: these are the courses a
            # student is choosing between most of the time.
            body += "".join(
                f"- **{planner.display_code(c)}** — {c['title']} ({c['units']}u)\n"
                for c in electives_here)
        else:
            body += ", ".join(f"**{planner.display_code(c)}** {c['title']}"
                              for c in electives_here) + "\n"
        body += "\n"

    body += CATALOG_CAP.format(cap=overview["nonMsbaCap"])
    body += CATALOG_NEXT
    return BotReply(body, [], "catalog-overview", route=router.CATALOG,
                    route_confidence=route.confidence)


HANDLERS = {
    router.CAREERS: lambda llm, route, conv, q, h: _answer_careers(route),
    router.CATALOG: lambda llm, route, conv, q, h: _answer_catalog(route),
    router.ROLE: lambda llm, route, conv, q, h: _answer_role(llm, route, conv, q, h),
    router.COMBINATION: lambda llm, route, conv, q, h: _answer_combination(llm, route, conv, q, h),
    router.INDUSTRY: lambda llm, route, conv, q, h: _answer_industry(
        llm, route, conv, q),
    router.FACTUAL: lambda llm, route, conv, q, h: _answer_factual(llm, route, q, h),
    router.SITUATIONAL: lambda llm, route, conv, q, h: _answer_situational(llm, route, conv, q),
    router.QUARTER: lambda llm, route, conv, q, h: _answer_quarter(
        llm, route, conv, q, planner.load_session_intake(conv)),
}


def answer(llm, conversation, question, history):
    """One turn on the courses surface.

    Order: plan maintenance, then a route, then the route's handler. The route
    and its confidence travel out on the `BotReply` so `ChatTurnLog` records
    which path an answer came down — without that, "the aerospace answer was
    bad" is a complaint about a black box rather than a finding about a route.
    """
    answers = planner.load_session_intake(conversation)
    maintained = _maintenance(llm, conversation, question, answers)
    if maintained is not None:
        if not maintained.route:
            maintained.route = "plan"
        return maintained

    # Reading a track or a goal off the turn happens only where it could not
    # displace a better answer. A rule route already decided is a stronger
    # signal than the two words it happened to contain: "I've switched from
    # 17-month to 11-month and I'm already in Winter" names a track, and
    # letting that reach `_intake_progress` answered a question about finishing
    # on time by asking what job they wanted. So the enrichment runs only when
    # nothing was ruled, or when the rule was ROLE -- which is the one route
    # `_intake_progress` can legitimately complete, because a role plus a track
    # IS the plan.
    ruled = router.rule_route(question)

    # A turn answering "what kind of work do you want to do in it?".
    #
    # THE fix, rather than the longer acceptance list above. "yup" was not on
    # that list, so a student who had answered the question was handed the
    # generic opening as though they had said nothing -- and any word not on
    # the list would have done the same. A question we asked one turn ago owns
    # the next turn unless that turn is plainly about something else, which is
    # the same rule the situational route already follows.
    # Never for a turn that teaches the intake something: without this it
    # stole "11 month", which is the very next thing this route asks for.
    if (answers.get("suggested_goal")
            and planner.session_has_asked(conversation, "what-work")
            and not learned_from(question)
            and (ruled is None or ruled.name == router.UNCLEAR)):
        return _with_a_way_back(conversation, answers, _uncurated_role(
            llm, router.Route(router.ROLE,
                              why="answering the question this route asked"),
            conversation, question))

    # A turn that answers a question this surface asked one turn ago. Only the
    # situational route asks anything, and what comes back is usually a single
    # word -- "winter" -- which no classifier can place. A rule route that says
    # otherwise still wins: a student who answers a question with a different
    # question has changed the subject, and holding them to the old one is the
    # interview behaviour being removed.
    if (planner.load_session_situation(conversation).get("awaiting")
            and (ruled is None or ruled.name == router.SITUATIONAL)):
        return _answer_situational(
            llm, router.Route(router.SITUATIONAL,
                              why="answering a question this route asked"),
            conversation, question)

    if ruled is None or ruled.name == router.ROLE:
        progressed = _intake_progress(conversation, question, answers)
        if progressed is not None:
            return progressed

    route = ruled or router.classify(llm, question)
    handler = HANDLERS.get(route.name)
    if handler is None:
        return _with_a_way_back(
            conversation, answers,
            _decline(route, llm, conversation, question, answers))
    reply = handler(llm, route, conversation, question, history)
    if not reply.route:
        reply.route = route.name
    return _with_a_way_back(conversation, answers, reply)
