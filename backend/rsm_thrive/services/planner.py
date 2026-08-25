"""Intake-driven course planner: interview the student, then build a full plan.

## Why this is not the electives bot

`services/electives.py` answers "which electives suit my career goal" in one
turn. It already accepts a rich profile — technical comfort, workload
tolerance, weighted career tags — but `recommend_for` hardcodes comfort 3 and
"moderate" workload, because a single chat turn has nowhere to ask. So the
engine was always able to personalise and never had the data.

This module supplies that data. It asks first (`intake_questions`), maps the
answers onto the profile the scorer already understands (`profile_from_intake`),
and then fills a real plan of study quarter by quarter rather than returning a
flat top-five.

## The plan is a skeleton with holes, not a free-for-all

The quarter structure, the core courses and the unit size of every elective
slot come from Rady's published plans of study (data/corpus/program/). A
student does not get to choose whether MGTA 451 is in their first summer, and
a 2-unit hole cannot be filled with a 4-unit course. Encoding the skeleton
means the planner cannot produce a schedule that would not be approved: the
core sequence is fixed, and each generated plan totals exactly 50 units —
22 core and 28 elective — which `tests/test_planner.py` asserts rather than
trusts.

## Deterministic, like the scorer it sits on

No LLM decides what goes in a slot. Same answers in, same plan out, which is
what makes a swap explainable ("these two courses teach these same skills")
and the whole thing testable. The LLM's job, if it is used at all, is to talk
about a plan this module produced.
"""
import json
import re
from functools import lru_cache

from rsm_thrive.models import Enrollment
from rsm_thrive.services.electives import (WORKLOAD_LEVEL, load_careers,
                                            load_catalog, rank_electives)

# ---------------------------------------------------------------------------
# The published skeletons
# ---------------------------------------------------------------------------

# `core` slots are the 22 required units and are never swappable. `fixed` slots
# are elective-labelled in the published plan but effectively determined:
# Summer is the only quarter with almost no elective offerings, so there is
# nothing to swap them for, and saying so is more honest than offering a choice
# that does not exist.
TRACK_SKELETONS = {
    "11 month": [
        {"key": "summer", "label": "Summer III", "season": "SU", "units": 8, "slots": [
            {"kind": "core", "course_id": "MGTA 451"},
            {"kind": "fixed", "course_id": "MGTA 403"},
            {"kind": "fixed", "course_id": "MGTA 464"},
        ]},
        {"key": "fall", "label": "Fall", "season": "FA", "units": 14, "slots": [
            {"kind": "core", "course_id": "MGTA 452"},
            {"kind": "core", "course_id": "MGTA 453"},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 2},
        ]},
        {"key": "winter", "label": "Winter", "season": "WI", "units": 14, "slots": [
            {"kind": "core", "course_id": "MGTA 455"},
            {"kind": "core", "course_id": "MGTA 444"},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 4},
        ]},
        {"key": "spring", "label": "Spring", "season": "SP", "units": 14, "slots": [
            {"kind": "core", "course_id": "MGTA 454"},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 2},
        ]},
    ],
    "17 month": [
        {"key": "summer", "label": "Summer III", "season": "SU", "units": 8, "slots": [
            {"kind": "core", "course_id": "MGTA 451"},
            {"kind": "fixed", "course_id": "MGTA 403"},
            {"kind": "fixed", "course_id": "MGTA 464"},
        ]},
        {"key": "fall", "label": "Fall", "season": "FA", "units": 12, "slots": [
            {"kind": "core", "course_id": "MGTA 452"},
            {"kind": "core", "course_id": "MGTA 453"},
            {"kind": "elective", "units": 4},
        ]},
        {"key": "winter", "label": "Winter", "season": "WI", "units": 14, "slots": [
            {"kind": "core", "course_id": "MGTA 455"},
            {"kind": "core", "course_id": "MGTA 444"},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 4},
        ]},
        {"key": "spring", "label": "Spring", "season": "SP", "units": 12, "slots": [
            {"kind": "core", "course_id": "MGTA 454"},
            {"kind": "elective", "units": 4},
            {"kind": "elective", "units": 4},
        ]},
        {"key": "fall-two", "label": "Fall (second year)", "season": "FA", "units": 4, "slots": [
            {"kind": "elective", "units": 4},
        ]},
    ],
}

CORE_UNITS = 22
ELECTIVE_UNITS = 28
TOTAL_UNITS = 50

# Where a student goes to ACT on a plan. Every URL here is one the corpus
# already carries (crawled/Graduate Enrollment, crawled/Booking Your Classes,
# corpus/program) rather than one guessed from memory: a plan that sends a
# student to a wrong booking page is worse than one that sends them nowhere.
ACTION_LINKS = [
    {"key": "tss", "label": "Book these courses in TSS",
     "url": "https://sis.ucsd.edu/",
     "note": "Triton Student System — where graduate students book classes."},
    {"key": "webreg", "label": "WebReg (Summer)",
     "url": "https://act.ucsd.edu/webreg2",
     "note": "Summer sessions are booked in WebReg rather than TSS."},
    {"key": "schedule", "label": "Schedule of Classes",
     "url": "https://act.ucsd.edu/cgi-bin/tritonlink.pl/2/students/academic/classes/schedule_of_classes.pl",
     "note": "Confirm the day, time and seat count before you book."},
    {"key": "booking-help", "label": "How booking works in TSS",
     "url": "https://students.ucsd.edu/my-tritonlink/tools/tool-help/booking.html",
     "note": "Step-by-step help if a booking is refused."},
    {"key": "grad-enrollment", "label": "Graduate enrollment rules",
     "url": "https://students.ucsd.edu/academics/enroll/graduate-enrollment/index.html",
     "note": "Unit minimums, deadlines and holds."},
    {"key": "plans-drive", "label": "Official plans of study (Rady Drive)",
     "url": "https://drive.google.com/drive/folders/1NkOVx60spVY31IHWZ7KWlGXBiXLL6Xk6",
     "note": "The published plan this schedule follows. Sign in with your UCSD "
             "account — see THRIVE's syllabus guidance if you hit a permission wall."},
]

# ---------------------------------------------------------------------------
# The intake
# ---------------------------------------------------------------------------

# Declared skill, per area, on a scale the prerequisite text can be checked
# against. "comfortable" is 4 rather than 3 deliberately: a student who says
# they are comfortable with Python should not be steered away from the courses
# that use it, and the scorer penalises any course above the stated comfort.
# A 1-5 self-rating per area. Five points rather than the four named levels this
# started with, because `rank_electives` already scores `technical_comfort` on
# 1-5: a rating maps straight through instead of being translated by a table,
# and a student who wants the middle of the range now has one.
SKILL_SCALE = [
    {"value": 1, "label": "1", "help": "New to it"},
    {"value": 2, "label": "2", "help": "Some exposure"},
    {"value": 3, "label": "3", "help": "Working knowledge"},
    {"value": 4, "label": "4", "help": "Comfortable"},
    {"value": 5, "label": "5", "help": "Advanced"},
]

# Where the rating form starts before a student touches it. The middle, so
# adjusting means moving in whichever direction is true rather than starting
# from a claim the student has not made.
DEFAULT_SKILL_RATING = 3

# The words students actually type, kept as accepted input alongside the
# numbers. Dropping them would mean "python is comfortable" — which is how
# people answer this question in prose — stopped being understood the moment
# the buttons arrived.
SKILL_WORDS = {
    "none": 1, "beginner": 1, "new": 1,
    "basic": 2, "some": 2,
    "working": 3, "moderate": 3, "okay": 3, "ok": 3,
    "comfortable": 4, "good": 4, "strong": 4,
    "advanced": 5, "expert": 5,
}


def skill_score(value):
    """A rating as 1-5, from either a number or a word. None when unreadable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 1 <= value <= 5:
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text.isdigit() and 1 <= int(text) <= 5:
            return int(text)
        return SKILL_WORDS.get(text)
    return None


def skill_label(value):
    """How a rating reads back to the student."""
    score = skill_score(value)
    if score is None:
        return str(value)
    entry = next(s for s in SKILL_SCALE if s["value"] == score)
    return f"{score} ({entry['help'].lower()})"

# The areas the catalog's prerequisites actually talk about. Each carries the
# words used to spot that demand in a course's free-text prerequisite line.
SKILL_AREAS = [
    {"key": "python", "label": "Python programming",
     "prereq_words": ["python", "programming", "pyspark", "coding"]},
    {"key": "sql", "label": "SQL and databases",
     "prereq_words": ["sql", "database", "etl"]},
    {"key": "stats", "label": "Statistics and regression",
     "prereq_words": ["statistics", "statistical", "regression", "probability"]},
    {"key": "ml", "label": "Machine learning",
     "prereq_words": ["machine learning", "supervised", "deep learning"]},
    {"key": "communication", "label": "Presenting and storytelling",
     "prereq_words": []},
]

# Communication is a real skill and not a proxy for technical comfort, so it is
# excluded from the comfort average — otherwise a strong presenter reads as
# ready for PySpark.
TECHNICAL_AREAS = [area["key"] for area in SKILL_AREAS if area["prereq_words"]]

WORKLOAD_CHOICES = [
    {"value": "light", "label": "Lighter — I have commitments outside class"},
    {"value": "moderate", "label": "Moderate — a normal full load"},
    {"value": "heavy", "label": "Heavy — I want to be pushed"},
]

TRACK_CHOICES = [
    {"value": "11 month", "label": "11 month — Summer through Spring"},
    {"value": "17 month", "label": "17 month — finishes the following Fall"},
]


@lru_cache(maxsize=1)
def _catalog_by_id():
    return {course["id"]: course for course in load_catalog()}


@lru_cache(maxsize=1)
def _ambiguous_codes():
    """Codes shared by more than one distinct course.

    The catalog carries four Special Topics courses all coded MGTA 495, with
    different ids, titles, seasons and topics. Their ids keep the plan correct —
    measured over 80 generated plans, zero contained a duplicated course ID —
    but 25 of those plans PRINTED "MGTA 495" on two rows, which reads as the
    same course listed twice and makes "change MGTA 495" ambiguous.
    """
    counts = {}
    for course in load_catalog():
        counts[course["code"]] = counts.get(course["code"], 0) + 1
    return frozenset(code for code, n in counts.items() if n > 1)


def display_code(course):
    """The code as a student should see it, disambiguated when it has to be."""
    code = course["code"]
    if code not in _ambiguous_codes():
        return code
    suffix = course["id"][len(code):].lstrip("- ").strip()
    return f"{code} ({suffix})" if suffix else code


def intake_questions():
    """The interview, as data the UI renders and the tests assert against.

    A fixed script rather than an LLM conversation: every answer feeds a
    specific scoring input, so a question with nowhere to land is a question
    not worth asking a student.
    """
    careers = load_careers()
    tags = sorted({tag for course in load_catalog()
                   for tag in (course.get("career_tags") or [])})
    return [
        {"key": "track", "kind": "single", "required": True,
         "prompt": "Which track are you on?",
         "help": "It decides how many quarters the plan has and which quarter each course lands in.",
         "options": TRACK_CHOICES},
        {"key": "goals", "kind": "multi", "required": True, "max": 3,
         "prompt": "What role are you aiming for after the program?",
         "help": "Pick up to three. The first one counts most.",
         "options": [{"value": role_id, "label": role["label"],
                      "description": role.get("description", "")}
                     for role_id, role in sorted(careers.items(),
                                                 key=lambda kv: kv[1]["label"])]},
        *[{"key": f"skill_{area['key']}", "kind": "single", "required": True,
           "prompt": f"How would you rate your {area['label']} right now?",
           "help": "Honest answers give a better plan — this is used to keep "
                   "courses in reach and to warn about prerequisites.",
           "options": [{"value": lvl["value"], "label": lvl["label"],
                        "description": lvl["help"]}
                       for lvl in SKILL_SCALE]}
          for area in SKILL_AREAS],
        {"key": "workload", "kind": "single", "required": True,
         "prompt": "How heavy a course load do you want?",
         "options": WORKLOAD_CHOICES},
        {"key": "interests", "kind": "multi", "required": False,
         "prompt": "Anything you particularly want to work on?",
         "help": "Optional. These are matched against course topics and tools.",
         "options": [{"value": tag, "label": tag.replace("-", " ")} for tag in tags]},
    ]


def validate_intake(answers):
    """Return a list of human-readable problems with a submitted intake."""
    problems = []
    for question in intake_questions():
        value = answers.get(question["key"])
        if question["key"].startswith("skill_"):
            # Accepts whatever `normalise_intake` accepts — a 1-5 number from
            # the rating form, or the words people type. Validating against the
            # option list alone would reject "comfortable", which is still a
            # perfectly good answer to a question asked in prose.
            if question["required"] and skill_score(value) is None:
                problems.append(f"{question['key']}: rate 1-5")
        elif question["kind"] == "single":
            allowed = {opt["value"] for opt in question["options"]}
            if question["required"] and value not in allowed:
                problems.append(f"{question['key']}: pick one of {sorted(allowed)}")
        else:
            allowed = {opt["value"] for opt in question["options"]}
            chosen = value or []
            if not isinstance(chosen, list):
                problems.append(f"{question['key']}: expected a list")
                continue
            if question["required"] and not chosen:
                problems.append(f"{question['key']}: choose at least one")
            unknown = [c for c in chosen if c not in allowed]
            if unknown:
                problems.append(f"{question['key']}: unknown {unknown}")
            if question.get("max") and len(chosen) > question["max"]:
                problems.append(f"{question['key']}: at most {question['max']}")
    return problems


def profile_from_intake(answers):
    """Map interview answers onto the profile `rank_electives` already reads."""
    technical = [skill_score(answers.get(f"skill_{key}")) or DEFAULT_SKILL_RATING
                 for key in TECHNICAL_AREAS]
    comfort = round(sum(technical) / len(technical)) if technical else 3
    return {
        "career_roles": list(answers.get("goals") or []),
        "career_tags": list(answers.get("interests") or []),
        "technical_comfort": comfort,
        "workload_preference": answers.get("workload") or "moderate",
        "interests": [tag.replace("-", " ") for tag in (answers.get("interests") or [])],
    }


# ---------------------------------------------------------------------------
# Prerequisite cautions
# ---------------------------------------------------------------------------

def prerequisite_cautions(course, answers):
    """Areas a course's prerequisites demand that the student rated low.

    Advisory, never a filter. The prerequisite text is prose written for humans
    ("Solid Python programming experience required"), so matching words in it is
    a hint and not an entitlement to remove a course from a student's plan —
    that call belongs to the student and their advisor, and the wording is
    surfaced next to the warning so they can make it.
    """
    text = " ".join(filter(None, [course.get("prerequisites") or ""])).lower()
    if not text:
        return []
    cautions = []
    for area in SKILL_AREAS:
        if not area["prereq_words"]:
            continue
        if not any(word in text for word in area["prereq_words"]):
            continue
        level = answers.get(f"skill_{area['key']}")
        score = skill_score(level)
        if score is not None and score <= 2:
            cautions.append(
                f"expects {area['label'].lower()} and you rated yourself "
                f"{skill_label(level)} out of 5")
    return cautions


# ---------------------------------------------------------------------------
# Similarity, for "give me something else that teaches the same thing"
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9]+")
# Words that appear in nearly every skill phrase and so carry no signal about
# whether two courses teach the same thing.
_SKILL_STOPWORDS = frozenset("""
a an the and or of to in on for with from as is are be using use used data
your you basic advanced introduction intro topics business analytics course
""".split())


def _phrase_words(phrases):
    words = set()
    for phrase in phrases or []:
        words |= {w for w in _WORD.findall(phrase.lower())
                  if len(w) > 2 and w not in _SKILL_STOPWORDS}
    return words


def _learning_words(course):
    """The vocabulary of what a course teaches: skills first, then topics/tools."""
    return (_phrase_words(course.get("skills"))
            | _phrase_words(course.get("topics"))
            | _phrase_words(course.get("tools")))


def similarity(left, right):
    """How much of the same learning two courses deliver, 0..1.

    Jaccard over the words of skills, topics and tools, plus a bump for shared
    career tags. Tags alone are too coarse — every marketing course shares the
    "marketing" tag while teaching completely different things — and words
    alone miss that two differently-worded courses serve the same career, so
    the two signals are combined rather than chosen between.
    """
    lw, rw = _learning_words(left), _learning_words(right)
    overlap = len(lw & rw) / len(lw | rw) if (lw | rw) else 0.0
    lt, rt = set(left.get("career_tags") or []), set(right.get("career_tags") or [])
    tag_overlap = len(lt & rt) / len(lt | rt) if (lt | rt) else 0.0
    return round(0.7 * overlap + 0.3 * tag_overlap, 4)


def shared_skills(left, right, limit=4):
    """Skill phrases from `right` that overlap what `left` teaches."""
    lw = _learning_words(left)
    scored = []
    for phrase in right.get("skills") or []:
        words = _phrase_words([phrase])
        if words & lw:
            scored.append((len(words & lw), phrase))
    scored.sort(key=lambda pair: -pair[0])
    return [phrase for _, phrase in scored[:limit]]


def distinct_skills(left, right, limit=3):
    """Skill phrases `left` teaches that `right` does not — what a swap loses."""
    rw = _learning_words(right)
    return [phrase for phrase in (left.get("skills") or [])
            if not (_phrase_words([phrase]) & rw)][:limit]


# ---------------------------------------------------------------------------
# Building the plan
# ---------------------------------------------------------------------------

def _offered_in(course, season):
    return any((offering.get("season") or "").upper() == season
               for offering in course.get("offerings") or [])


def _within_workload(course, preference):
    return WORKLOAD_LEVEL.get(course.get("workload", "moderate"), 2) <= preference


def _within_comfort(course, comfort):
    return (course.get("technical_level") or 3) <= comfort


# A course this far above the student's stated comfort is a different kind of
# problem from one a single level above it. One level is a stretch; two is
# putting someone who reported no programming into PySpark.
SEVERE_STRETCH = 2


def _pick(candidates, profile):
    """Choose an elective: the ranked best, minus the severe mismatches.

    `rank_electives` already penalises a course that is heavier or more
    technical than the student asked for, and those penalties are calibrated.
    Measured across 100 synthetic students, overriding them with hard
    preference tiers cut electives-above-comfort from 214 to 102 but dropped
    goal alignment from 72% to 56% — it started filling career-critical slots
    with comfortable but irrelevant courses, which is a worse plan, not a
    safer one.

    So only a SEVERE technical mismatch (two levels or more above the declared
    comfort) is skipped while a ranked alternative exists. Workload is left
    entirely to the scorer: the catalog contains exactly one "light" elective,
    so a light-workload preference is not satisfiable and pretending otherwise
    would just push off-goal courses into the plan. Where a preference cannot
    be met, `_stretch_notes` says so on the row.
    """
    comfort = profile["technical_comfort"]
    gentle = [r for r in candidates
              if (r["course"].get("technical_level") or 3) - comfort < SEVERE_STRETCH]
    for tier in (gentle, candidates):
        if tier:
            return tier[0]["course"]
    return None


def _stretch_notes(course, profile):
    """Where this course exceeds what the student asked for."""
    notes = []
    preference = WORKLOAD_LEVEL.get(profile.get("workload_preference"), 2)
    if not _within_workload(course, preference):
        notes.append(
            f"{course.get('workload')} workload, above the "
            f"{profile.get('workload_preference')} load you asked for — nothing "
            f"lighter is offered for this slot")
    if not _within_comfort(course, profile["technical_comfort"]):
        notes.append(
            f"more technical (level {course.get('technical_level')}) than the "
            f"level {profile['technical_comfort']} you reported")
    return notes


def _entry(course, kind, *, swappable, reasons=None, cautions=None, note="",
           stretch=None, on_goal=None):
    """One row of a quarter, labelled core or elective as the student sees it."""
    return {
        "courseId": course["id"],
        "code": display_code(course),
        # The bare catalog code, for anything matching on identity rather than
        # display — `code` may carry a disambiguating suffix.
        "baseCode": course["code"],
        "title": course["title"],
        "units": course["units"],
        "kind": kind,                       # "core" | "elective"
        "requirement": "Core" if kind == "core" else "Elective",
        "swappable": swappable,
        "technicalLevel": course.get("technical_level"),
        "workload": course.get("workload"),
        "skills": (course.get("skills") or [])[:4],
        "reasons": reasons or [],
        "cautions": cautions or [],
        "note": note,
        # Where the course exceeds a limit the student stated. Separate from
        # `cautions`, which is about prerequisites: one is "this is harder than
        # you wanted", the other is "you may not be ready for this".
        "stretch": stretch or [],
        # 28 elective units have to be filled and few goals have 28 units of
        # on-target courses, so some electives are breadth by necessity. Saying
        # which is which stops the plan implying every choice serves the goal.
        "onGoal": on_goal,
    }


def build_plan(answers, taken_ids=frozenset(), selections=None):
    """Build the whole plan of study for one student.

    `selections` is {quarter_key: {slot_index: course_id}} and wins over the
    automatic pick, which is what makes a swap a persisted edit rather than a
    re-roll: the plan is rebuilt from the intake every time and the student's
    overrides are re-applied on top, so nothing else in the plan shifts
    underneath a single change.

    Every quarter lists its CORE courses as well as its electives, each row
    labelled, because a plan that shows only the electives does not tell a
    student what their quarter looks like.
    """
    catalog = _catalog_by_id()
    profile = profile_from_intake(answers)
    track = answers.get("track") or "11 month"
    skeleton = TRACK_SKELETONS.get(track)
    if skeleton is None:
        raise ValueError(f"unknown track {track!r}")

    ranked = rank_electives(load_catalog(), profile, load_careers())
    fit = {row["course"]["id"]: row for row in ranked}
    selections = selections or {}
    careers = load_careers()
    goal_tags = {tag for role in profile["career_roles"]
                 for tag in (careers.get(role, {}).get("career_tags") or [])}

    used, quarters, unfilled = set(), [], []
    for quarter in skeleton:
        rows = []
        for index, slot in enumerate(quarter["slots"]):
            if slot["kind"] in ("core", "fixed"):
                course = catalog[slot["course_id"]]
                used.add(course["id"])
                is_core = slot["kind"] == "core"
                rows.append(_entry(
                    course, "core" if is_core else "elective", swappable=False,
                    reasons=["required core course for the MSBA"] if is_core else
                            ["scheduled elective — the only offering that fits this "
                             "slot in Summer"],
                    cautions=prerequisite_cautions(course, answers),
                    note="" if is_core else "fixed by the published plan of study",
                ))
                continue

            chosen_id = (selections.get(quarter["key"]) or {}).get(str(index))
            candidates = [
                row for row in ranked
                if row["course"]["units"] == slot["units"]
                and _offered_in(row["course"], quarter["season"])
                and row["course"]["id"] not in used
                and row["course"]["id"] not in taken_ids
            ]
            course = None
            if chosen_id and chosen_id in catalog and chosen_id not in used:
                picked = catalog[chosen_id]
                # An override still has to be a legal course for this hole.
                if (picked["units"] == slot["units"]
                        and _offered_in(picked, quarter["season"])
                        and chosen_id not in taken_ids):
                    course = picked
            if course is None:
                course = _pick(candidates, profile)

            if course is None:
                unfilled.append({
                    "quarter": quarter["key"], "slot": index, "units": slot["units"],
                    "why": f"no {slot['units']}-unit elective is offered in "
                           f"{quarter['label']} that you have not already used",
                })
                rows.append({
                    "courseId": None, "code": None, "title": None,
                    "units": slot["units"], "kind": "elective",
                    "requirement": "Elective", "swappable": True,
                    "skills": [], "reasons": [], "cautions": [],
                    "note": "nothing available for this slot",
                })
                continue

            used.add(course["id"])
            rows.append(_entry(
                course, "elective", swappable=True,
                reasons=(fit.get(course["id"]) or {}).get("reasons", []),
                cautions=prerequisite_cautions(course, answers),
                note="your choice" if chosen_id == course["id"] else "",
                stretch=_stretch_notes(course, profile),
                on_goal=bool(set(course.get("career_tags") or []) & goal_tags),
            ))

        quarters.append({
            "key": quarter["key"], "label": quarter["label"],
            "season": quarter["season"],
            "unitsPlanned": sum(r["units"] for r in rows),
            "unitsExpected": quarter["units"],
            "courses": rows,
        })

    core_units = sum(r["units"] for q in quarters for r in q["courses"]
                     if r["kind"] == "core")
    elective_units = sum(r["units"] for q in quarters for r in q["courses"]
                         if r["kind"] == "elective")
    return {
        "track": track,
        "quarters": quarters,
        "totals": {
            "core": core_units,
            "elective": elective_units,
            "total": core_units + elective_units,
            "coreRequired": CORE_UNITS,
            "electiveRequired": ELECTIVE_UNITS,
            "totalRequired": TOTAL_UNITS,
        },
        "profile": profile,
        "unfilled": unfilled,
        "links": ACTION_LINKS,
        # Set when most of this plan's electives are breadth rather than aimed
        # at the goal. The plan is complete either way; saying so is what stops
        # a broad plan reading as a targeted one.
        "targeting": targeting_note(quarters, profile["career_roles"]),
        "disclaimer": ("This is a sample plan built from Rady's published plan of "
                       "study. Confirm your schedule with MSBA advising before you "
                       "book — course offerings and quarters can change."),
    }


# ---------------------------------------------------------------------------
# Swapping a course for one that teaches the same thing
# ---------------------------------------------------------------------------

def _locate(plan, quarter_key, slot):
    for quarter in plan["quarters"]:
        if quarter["key"] != quarter_key:
            continue
        if 0 <= slot < len(quarter["courses"]):
            return quarter, quarter["courses"][slot]
    return None, None


def alternatives_for(plan, answers, quarter_key, slot, taken_ids=frozenset(), limit=4):
    """Other courses that would fill the same hole and teach much the same thing.

    Ranked by similarity to the course currently in the slot FIRST and personal
    fit second. That order is deliberate: a student asking to change a course
    they dislike wants a different way to learn the same material, not the
    next-best course for their career — the second is what the planner already
    gave them.

    Each option carries what it shares with the current course and what the
    current course teaches that it does not, so the trade is visible instead of
    being taken on trust.
    """
    catalog = _catalog_by_id()
    quarter, current = _locate(plan, quarter_key, slot)
    if quarter is None:
        raise ValueError(f"no slot {slot} in quarter {quarter_key!r}")
    if not current["swappable"]:
        return {"quarter": quarter_key, "slot": slot, "current": current,
                "swappable": False, "options": [],
                "why": current.get("note") or "this slot is fixed"}

    in_plan = {row["courseId"] for q in plan["quarters"] for row in q["courses"]
               if row["courseId"]}
    profile = profile_from_intake(answers)
    fit = {row["course"]["id"]: row
           for row in rank_electives(load_catalog(), profile, load_careers())}
    current_course = catalog.get(current["courseId"]) if current["courseId"] else None

    options = []
    for course in load_catalog():
        if course["is_core"] or course["units"] != current["units"]:
            continue
        if not _offered_in(course, quarter["season"]):
            continue
        if course["id"] in in_plan or course["id"] in taken_ids:
            continue
        sim = similarity(current_course, course) if current_course else 0.0
        row = fit.get(course["id"]) or {}
        options.append({
            "courseId": course["id"], "code": display_code(course),
            "baseCode": course["code"],
            "title": course["title"], "units": course["units"],
            "technicalLevel": course.get("technical_level"),
            "workload": course.get("workload"),
            "similarity": sim,
            "fitScore": row.get("score", 0.0),
            "sharedSkills": shared_skills(current_course, course) if current_course else [],
            "losesFromCurrent": distinct_skills(current_course, course) if current_course else [],
            # Two courses can serve the same career without sharing skill
            # wording — an NLP course and an ML-theory course overlap in what
            # they are FOR more than in how they describe themselves. Without
            # this, such an option arrives with an empty rationale and the
            # student has to guess why it was offered.
            "sharedFocus": sorted(
                set(course.get("career_tags") or [])
                & set((current_course or {}).get("career_tags") or [])),
            "reasons": row.get("reasons", []),
            "cautions": prerequisite_cautions(course, answers),
        })
    options.sort(key=lambda o: (-o["similarity"], -o["fitScore"], o["code"]))
    # "No options" is a fact about the timetable, not a failure, and a bare
    # empty list reads as the feature being broken. Say which constraint bit.
    why = ""
    if not options:
        why = (f"no other {current['units']}-unit elective is offered in "
               f"{quarter['label']} that is not already in your plan — this "
               f"slot is effectively fixed by the timetable")
    return {"quarter": quarter_key, "slot": slot, "current": current,
            "swappable": True, "options": options[:limit], "why": why}


def apply_swap(answers, selections, quarter_key, slot, course_id, taken_ids=frozenset()):
    """Record a swap and hand back the updated selections.

    Validated against the skeleton rather than against the current plan: the
    replacement has to fit the hole (same units, offered that season, not
    already somewhere else in the plan), so a stale or hand-made request cannot
    write a schedule that would not be approved.

    Every auto-filled elective is PINNED as part of the swap, and that is the
    subtle part. Electives are picked greedily from a shared pool, so replacing
    one course frees the course it displaced and the later quarters re-pick
    around it: swapping a Fall elective for Deep Learning released Machine
    Learning back into the pool, which then displaced two Winter courses the
    student never touched. A plan that rearranges itself when you change one
    thing is not a plan you can reason about. Pinning turns the first swap into
    the moment the whole schedule becomes the student's own — after it, only the
    slot they act on moves.
    """
    catalog = _catalog_by_id()
    track = answers.get("track") or "11 month"
    skeleton = TRACK_SKELETONS.get(track)
    if skeleton is None:
        raise ValueError(f"unknown track {track!r}")
    quarter = next((q for q in skeleton if q["key"] == quarter_key), None)
    if quarter is None:
        raise ValueError(f"unknown quarter {quarter_key!r}")
    if not (0 <= slot < len(quarter["slots"])):
        raise ValueError(f"no slot {slot} in {quarter_key!r}")
    if quarter["slots"][slot]["kind"] != "elective":
        raise ValueError("that slot is fixed by the published plan of study")

    course = catalog.get(course_id)
    if course is None:
        raise ValueError(f"unknown course {course_id!r}")
    if course["is_core"]:
        raise ValueError("a core course cannot fill an elective slot")
    if course["units"] != quarter["slots"][slot]["units"]:
        raise ValueError(
            f"{course['code']} is {course['units']} units and that slot is "
            f"{quarter['slots'][slot]['units']}")
    if not _offered_in(course, quarter["season"]):
        raise ValueError(f"{course['code']} is not offered in {quarter['label']}")
    if course_id in taken_ids:
        raise ValueError(f"you have already taken {course['code']}")

    updated = {key: dict(value) for key, value in (selections or {}).items()}

    # Pin what the planner chose automatically BEFORE changing anything, so the
    # rest of the schedule cannot shift in response to this edit.
    current_plan = build_plan(answers, taken_ids, updated)
    for built_quarter, spec in zip(current_plan["quarters"], skeleton):
        for index, row in enumerate(built_quarter["courses"]):
            if spec["slots"][index]["kind"] != "elective" or not row["courseId"]:
                continue
            updated.setdefault(built_quarter["key"], {}).setdefault(
                str(index), row["courseId"])
    # The same course twice is the one duplicate a plan must never contain. If
    # the incoming course is pinned in another slot, that is the student asking
    # to move it, so say where it already is rather than silently relocating it.
    for other_key, slots in updated.items():
        for other_slot, other_id in list(slots.items()):
            if other_id != course_id:
                continue
            if other_key == quarter_key and other_slot == str(slot):
                continue
            label = next((q["label"] for q in skeleton if q["key"] == other_key),
                         other_key)
            raise ValueError(f"{course['code']} is already in your {label} quarter")

    updated.setdefault(quarter_key, {})[str(slot)] = course_id
    return updated


def taken_course_ids(user):
    """Catalog ids for courses the student has already enrolled in."""
    codes = {enrollment.course.code for enrollment
             in Enrollment.objects.filter(user=user).select_related("course")}
    return {course["id"] for course in load_catalog() if course["code"] in codes}


# ---------------------------------------------------------------------------
# Presenting a plan
# ---------------------------------------------------------------------------

def render_plan_markdown(plan):
    """A plan as Markdown the app already knows how to render.

    Tables and links rather than prose: a plan of study is a grid, and
    `RichMessage` renders Markdown tables and links as real `<table>` and `<a>`
    elements, so this arrives formatted instead of as a wall of pipes.

    Every quarter lists its CORE courses alongside its electives and marks
    which is which, because "what am I taking in Winter" is the question a plan
    exists to answer, and an elective-only list cannot answer it.
    """
    totals = plan["totals"]
    lines = [
        f"# Your {plan['track']} MSBA plan of study",
        "",
        f"**{totals['total']} units** — {totals['core']} core and "
        f"{totals['elective']} elective, which is what the degree requires "
        f"({totals['totalRequired']} units: {totals['coreRequired']} core, "
        f"{totals['electiveRequired']} elective).",
        "",
    ]
    for quarter in plan["quarters"]:
        lines += [
            f"## {quarter['label']} — {quarter['unitsPlanned']} units",
            "",
            "| Course | Title | Units | Requirement |",
            "|---|---|---|---|",
        ]
        for row in quarter["courses"]:
            if not row["courseId"]:
                lines.append(f"| — | _{row['note']}_ | {row['units']} | "
                             f"{row['requirement']} |")
                continue
            lines.append(f"| **{row['code']}** | {row['title']} | "
                         f"{row['units']} | {row['requirement']} |")
        lines.append("")
        notes = []
        for row in quarter["courses"]:
            if row.get("stretch"):
                notes.append(f"- **{row['code']}** — {row['stretch'][0]}")
            for caution in row.get("cautions") or []:
                notes.append(f"- **{row['code']}** — {caution}")
        if notes:
            lines += ["Worth knowing before you book:", "", *notes, ""]

    goal_rows = [r for q in plan["quarters"] for r in q["courses"]
                 if r["requirement"] == "Elective" and r.get("onGoal")]
    breadth = [r for q in plan["quarters"] for r in q["courses"]
               if r["requirement"] == "Elective" and r.get("onGoal") is False]
    if goal_rows or breadth:
        lines += ["## Why these electives", ""]
        if goal_rows:
            lines.append("Chosen for your stated goal: "
                         + ", ".join(f"**{r['code']}**" for r in goal_rows) + ".")
        if breadth:
            lines.append("")
            lines.append("Filling the remaining elective units for breadth: "
                         + ", ".join(f"**{r['code']}**" for r in breadth)
                         + ". Any of these can be swapped for something closer "
                           "to your interests.")
        lines.append("")

    targeting = plan.get("targeting")
    if targeting:
        lines += [
            "## Worth a conversation with advising", "",
            f"Only **{targeting['onGoal']} of {targeting['electiveSlots']}** "
            f"elective slots line up with "
            f"{' and '.join(targeting['goals'])} — the rest are breadth, because "
            f"the courses aimed at that path are not all offered in the quarters "
            f"and sizes this plan needs. It is still a complete 50-unit plan, and "
            f"MSBA advising can advise on getting closer to that goal — book them "
            f"from the **Appointments** tab.", ""]

    lines += ["## Booking and detail", ""]
    for link in plan["links"]:
        lines.append(f"- [{link['label']}]({link['url']}) — {link['note']}")
    lines += ["", f"_{plan['disclaimer']}_"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The interview, run as a conversation
# ---------------------------------------------------------------------------

# Asked in this order, and grouped so the student is not interrogated one field
# at a time. Track comes first because it decides how many quarters exist and
# which quarter every course lands in — asking anything else before it risks
# building toward a plan that then has to change shape.
INTAKE_STEPS = [
    {"key": "track", "fields": ["track"]},
    {"key": "goals", "fields": ["goals"]},
    {"key": "skills", "fields": [f"skill_{area['key']}" for area in SKILL_AREAS]},
    {"key": "workload", "fields": ["workload"]},
]

# `interests` is deliberately absent above: it improves a plan and is not
# required to build one, so it is never a gate between a student and their plan.
OPTIONAL_FIELDS = {"interests"}


def _allowed_values():
    allowed = {}
    for question in intake_questions():
        allowed[question["key"]] = {opt["value"] for opt in question["options"]}
    return allowed


# Below this share of a plan's elective slots actually targeting the student's
# goal, the plan is mostly breadth and should say so.
#
# Measured from the BUILT PLAN rather than from catalog tag counts, because the
# two disagree badly. Counting tagged electives said healthcare-analyst was
# well served (15 courses) and operations-supply-chain was not (5) — but the
# plans land at 4/7 and 3/7 on-goal respectively, nearly the same. What decides
# it is which of those courses are offered in the right quarter at the right
# unit size, not how many exist. So the old proxy excluded one role while
# shipping another that was barely better.
MIN_ON_GOAL_SHARE = 0.5


def matched_elective_count(role_id):
    """How many electives share a career tag with this role."""
    role = load_careers().get(role_id) or {}
    tags = set(role.get("career_tags") or [])
    if not tags:
        return 0
    return sum(1 for course in load_catalog()
               if not course["is_core"]
               and set(course.get("career_tags") or []) & tags)


def targeting_note(quarters, goals):
    """Whether this plan is mostly breadth, judged from the plan itself.

    Every role gets a plan — there are 28 elective units to fill and the catalog
    can always fill them. What varies is how much of that fill actually targets
    the student's goal, and that is knowable exactly once the plan exists: each
    elective row already records whether it matched a goal tag. No proxy, no
    threshold on a number that turned out not to predict the outcome.
    """
    electives = [row for quarter in quarters for row in quarter["courses"]
                 if row["requirement"] == "Elective" and row["swappable"]]
    if not electives or not goals:
        return None
    on_goal = sum(1 for row in electives if row.get("onGoal"))
    if on_goal / len(electives) >= MIN_ON_GOAL_SHARE:
        return None
    careers = load_careers()
    return {
        "onGoal": on_goal,
        "electiveSlots": len(electives),
        "goals": [careers.get(role_id, {}).get("label", role_id) for role_id in goals],
    }


def uncovered_career_reply(named):
    """What to say when the student's target job is not one the catalog serves.

    Deliberately NOT the list of ten roles. Answering "I want to be an esports
    analyst" with "pick one of these instead" spams a menu at someone whose
    actual question — does this degree get me there — has just been answered
    with no. The honest reply is that the MSBA electives are not built for it
    and that a human should weigh in, with the concrete way to reach one.

    One line does offer a way forward, because a dead end is its own failure,
    but it names no roles: a student who wants to proceed can say so and the
    interview picks up from there.
    """
    subject = f"**{named}**" if named else "that career"
    return (
        f"I don't have MSBA course material built around {subject}, so I'd be "
        f"guessing if I put a plan together for it — and a plan built on a guess "
        f"is worse than no plan.\n\n"
        f"**Please check with MSBA advising.** They can tell you whether the "
        f"programme supports that path and which electives would come closest. "
        f"You can book time with them from the **Appointments** tab.\n\n"
        f"If you'd rather I build a plan around a role the catalog does cover, "
        f"tell me which one you're closest to and I'll carry on from there."
    )


def unmatched_goal_of(raw):
    """The student's own words when they named a career we have no track for."""
    if not isinstance(raw, dict):
        return ""
    value = raw.get("unmatched_goal")
    return value.strip()[:60] if isinstance(value, str) and value.strip() else ""


def normalise_intake(raw):
    """Keep only the answers an extractor produced that are actually valid.

    The extractor is an LLM reading a free-text conversation, so it will
    occasionally return "17 months", a role that does not exist, or a skill
    level it invented. Dropping those rather than repairing them means the
    interview asks the question again, which is the right outcome: a guessed
    answer becomes a plan the student never agreed to.
    """
    if not isinstance(raw, dict):
        return {}
    allowed = _allowed_values()
    answers = {}
    for key, values in allowed.items():
        value = raw.get(key)
        if key in ("goals", "interests"):
            chosen = [v for v in (value or []) if isinstance(v, str) and v in values]
            if chosen:
                answers[key] = chosen[:3] if key == "goals" else chosen
        elif key.startswith("skill_"):
            # Stored as 1-5 whatever it arrived as, so everything downstream
            # reads one type: an extractor may send 4, "4" or "comfortable".
            score = skill_score(value)
            if score is not None:
                answers[key] = score
        elif isinstance(value, str) and value in values:
            answers[key] = value
    return answers


# After this many attempts at the same step, assume a middling answer for what
# is still blank rather than asking again. Measured over 50 conversations: a
# student who answered "I've never written code, stats basic, I present well"
# left SQL and machine learning unstated, and the interview asked for them three
# times in a row and never produced a plan. An interview with no exit is worse
# than an assumption the student can see and correct.
MAX_STEP_ATTEMPTS = 2

# What an unanswered skill area is assumed to be. Deliberately low-middle: it is
# better to under-claim a skill (the scorer keeps courses in reach and the plan
# says what it assumed) than to over-claim and put someone in a course they
# cannot pass.
ASSUMED_SKILL = "basic"


def fill_assumed_skills(answers, missing):
    """Assume the unanswered skill areas, and report what was assumed."""
    filled = dict(answers)
    assumed = []
    for field in missing:
        if field.startswith("skill_") and not filled.get(field):
            filled[field] = ASSUMED_SKILL
            area = next(a for a in SKILL_AREAS if f"skill_{a['key']}" == field)
            assumed.append(area["label"])
    return filled, assumed


def next_intake_step(answers):
    """The next group of questions still unanswered, or None when complete."""
    for step in INTAKE_STEPS:
        missing = [field for field in step["fields"]
                   if field not in OPTIONAL_FIELDS and not answers.get(field)]
        if missing:
            return {"key": step["key"], "missing": missing}
    return None


def _question(key):
    return next(q for q in intake_questions() if q["key"] == key)


def step_position(step):
    """Where the question being asked sits in the interview, 1-based.

    The position of THIS step, not a count of finished ones. Counting finished
    steps looked equivalent and was not: a student who names a career before
    stating a track has answered step 2 and not step 1, so the header read
    "Step 2 of 4" above the track question.
    """
    for index, candidate in enumerate(INTAKE_STEPS, start=1):
        if candidate["key"] == step["key"]:
            return index
    return 1


def render_question(step, answers, unmatched_goal=""):
    """The next question, as Markdown the chat already renders.

    Bullet lists rather than prose: these are choices, and `RichMessage` turns
    `- ` lines into a real list. The step counter is there because an interview
    with no visible end is one students abandon.
    """
    lines = [f"**Step {step_position(step)} of {len(INTAKE_STEPS)}.**", ""]
    # A student who names a career the catalog has no track for should be told
    # that, not shown the same list again as though they had said nothing.
    if unmatched_goal and step["key"] == "goals":
        lines += [f"I don't have a track built around **{unmatched_goal}** — the "
                  f"roles below are the ones the elective scoring knows about. "
                  f"Pick whichever comes closest and I'll work from that.", ""]

    if step["key"] == "skills":
        lines += ["To keep the plan in reach, how would you rate yourself in each "
                  "of these right now?", ""]
        for field in step["missing"]:
            area = next(a for a in SKILL_AREAS if f"skill_{a['key']}" == field)
            lines.append(f"- **{area['label']}**")
        lines += ["",
                  "Rate each one **1-5** ("
                  + ", ".join(f"{lvl['value']} = {lvl['help'].lower()}"
                              for lvl in SKILL_SCALE)
                  + "). Use the sliders below, or just say something like "
                    "\"python 4, sql 2\" — words work too."]
        return "\n".join(lines)

    question = _question(step["missing"][0])
    lines.append(question["prompt"])
    if question.get("help"):
        lines += ["", f"_{question['help']}_"]

    # The options are printed ONLY when this step has no buttons to carry them.
    # Every step that does (`quick_replies_for`) now puts each option's
    # explanation on its own button, and printing the same list above them made
    # one question into five stacked blocks — a step counter, a prompt, a help
    # line, a bullet list, and a button row saying the list again.
    #
    # The fallback still matters: a client that ignores `quickReplies` has to
    # render a usable question, and this is the message body it renders.
    if not quick_replies_for(step):
        lines.append("")
        for option in question["options"]:
            label = option["label"]
            description = option.get("description")
            lines.append(f"- **{label}**" + (f" — {description}" if description else ""))
    return "\n".join(lines)


def merge_intake(stored, extracted):
    """Accumulate interview answers across turns.

    Newly extracted values win, so a student correcting themselves ("actually
    the 11 month") is respected; anything the latest turn did not mention keeps
    the value already on file. This is the piece that makes the interview
    stateful without a state machine — and without trusting a language model to
    remember what it was told three messages ago.
    """
    merged = dict(stored or {})
    for key, value in (extracted or {}).items():
        if value in (None, "", []):
            continue
        merged[key] = value
    return merged


def load_session_intake(conversation):
    """Answers gathered so far in THIS conversation, possibly none.

    Per-conversation on purpose: a new chat must start the interview over, both
    so it can be re-run and so a student's new goal is not silently overridden
    by an answer they gave last week.
    """
    from rsm_thrive.models import PlannerSession

    session = PlannerSession.objects.filter(conversation=conversation).first()
    return dict(session.intake) if session else {}


def interview_answers():
    """Every closed-set answer a student can send as a single message.

    Used to recognise a conversation TITLE that is really a button press. The
    title is taken from the student's first message, and on this destination
    that message is usually one tap — so the saved list filled up with rows
    called "17 month", several of them, none of which say what the plan was
    for. See `conversation_title`.
    """
    values = {choice["value"].lower() for choice in TRACK_CHOICES}
    values |= {choice["value"].lower() for choice in WORKLOAD_CHOICES}
    values |= {role["label"].lower() for role in load_careers().values()}
    return values


def conversation_title(answers):
    """What to call a saved plan conversation, or "" if it is too early to say.

    Named after the two answers that identify the plan — the goal it targets
    and the track it runs on — because those are what a student is looking for
    when they come back to a list of them a week later. The track alone is not
    enough: it is the first question, so titling on it would name every
    conversation before any of them had a subject.
    """
    goals = answers.get("goals") or []
    if not goals:
        return ""
    careers = load_careers()
    label = careers.get(goals[0], {}).get("label") or goals[0]
    track = answers.get("track")
    return f"Course plan — {label}" + (f", {track}" if track else "")


def supported_roles():
    """Every role a path can be built for, best-supported first.

    All of them, because a path can be built for all of them. An earlier version
    dropped a role whose tagged-elective count fell below a threshold — but
    measured against the plans that actually get built, that count does not
    predict how targeted the plan is: operations-supply-chain (5 tagged
    electives) lands 3 of 7 elective slots on-goal, and healthcare-analyst (15)
    lands 4 of 7. Excluding the first while offering the second was a
    distinction the data does not support, and it hid a job the courses can
    genuinely serve.

    Where a plan does come out mostly breadth, `targeting_note` says so on the
    plan itself — which is the honest place for it, because it is a fact about
    that plan rather than about the role.

    Ordering is by how many courses each role has boosted for it. That is NOT a
    claim about which jobs graduates most often take: this repo carries no
    placement or outcomes data, and inventing an order and calling it "most
    common" would be a statistic with nothing behind it. Course support is
    measurable and is a real signal of what the programme is built to serve.
    Swap the ordering for placement data the moment there is any.
    """
    careers = load_careers()
    return sorted(careers,
                  key=lambda rid: (-len(careers[rid].get("boost_courses") or {}),
                                   careers[rid]["label"]))


def rating_form_for(step):
    """A pre-filled 1-5 rating per area, so the skills step needs no typing.

    The one step with no useful quick replies: it asks about five areas at once,
    and a flat row of twenty-five buttons is a wall, not a shortcut. A form
    keeps it one control per area, starts every row at the middle so nothing is
    claimed on the student's behalf, and sends a single message when submitted.

    Returned as data rather than rendered here for the usual reason — the
    backend owns what is asked, the frontend owns how it looks.
    """
    if step["key"] != "skills":
        return None
    missing = set(step["missing"])
    rows = [{"key": f"skill_{area['key']}", "label": area["label"]}
            for area in SKILL_AREAS
            if f"skill_{area['key']}" in missing or not missing]
    if not rows:
        return None
    return {
        "kind": "rating",
        "rows": rows,
        "scale": [{"value": s["value"], "label": s["label"], "help": s["help"]}
                  for s in SKILL_SCALE],
        "default": DEFAULT_SKILL_RATING,
        # camelCase ON PURPOSE, and the one place Python emits it. This dict is
        # stored verbatim in ChatMessage.form and served straight through the
        # serializer, so the key IS the wire name the frontend reads. Renaming
        # it to snake_case "for consistency" would silently unlabel the button.
        "submitLabel": "Submit ratings",
    }


def compose_rating_message(ratings):
    """The message a submitted rating form sends, as a student would phrase it.

    NO PRODUCTION CALLER TODAY: the browser composes this same sentence in
    ChatWindow.svelte, because the form is submitted client-side. The two
    formats are character-identical and this one is the tested copy — keep
    them in step, and prefer calling this from any future server-side path.

    Words, not a payload: the transcript then reads like something a person
    said, and the extractor sees the same kind of input whether the student
    used the form or typed "python 4, sql 2".
    """
    labels = {f"skill_{area['key']}": area["label"] for area in SKILL_AREAS}
    parts = [f"{labels.get(key, key)} {value}"
             for key, value in ratings.items() if key in labels]
    return ", ".join(parts)


def _choice_button(option):
    """One closed-set option as a button, label split from its explanation.

    The published labels are written as "11 month — Summer through Spring":
    a name, an em dash, and what it means. The button face takes the name and
    the `description` carries the rest, so the explanation travels WITH the
    control instead of being repeated in a bullet list above it (see
    `render_question`, which no longer prints one).
    """
    label, _, description = option["label"].partition(" — ")
    return {"label": label, "send": option["value"],
            "description": description or option.get("description", "")}


def quick_replies_for(step):
    """Buttons to offer with a question, so a fixed choice need not be typed.

    Only for questions whose answers are a closed set. The skills step is left
    to free text on purpose: it asks about five areas at once, and thirty
    buttons is not a shortcut.
    """
    careers = load_careers()
    if step["key"] == "track":
        return [_choice_button(option) for option in TRACK_CHOICES]
    if step["key"] == "goals":
        # `short_label` comes from careers.json rather than being derived. A
        # slash means two different things in these labels — an alias in
        # "Marketing Analyst / Marketing Data Scientist", part of the name in
        # "Finance / Quantitative Analyst" — so splitting on it turned the
        # latter into a button reading "Finance". The button text is data.
        #
        # `send` stays the FULL label so the extractor still sees every alias it
        # might match on; only the button face is shortened.
        return [{"label": careers[role_id].get("short_label")
                          or careers[role_id]["label"],
                 "send": careers[role_id]["label"],
                 "description": careers[role_id].get("description", "")}
                for role_id in supported_roles()]
    if step["key"] == "workload":
        return [_choice_button(option) for option in WORKLOAD_CHOICES]
    return []


def opening_prompt():
    """The interview's first question, for a chat that has not started yet.

    So the courses surface opens ON the first question with its buttons rather
    than on an empty box the student has to type into to discover that a
    question was coming. Rendered by the same `render_question` the bot uses, so
    the opening the student sees and the reply they get after answering are the
    same text from the same place — not a frontend copy that drifts.
    """
    step = next_intake_step({})
    if step is None:
        return None
    # Same shape as a real reply, form included. The opening step happens to be
    # the track question, which has buttons and no form — but hard-coding that
    # here would silently drop the form if the interview order ever changed.
    return {"body": render_question(step, {}),
            "quickReplies": quick_replies_for(step),
            "form": rating_form_for(step)}


def load_session_review(conversation):
    """Where this conversation is in the walk-through, or None."""
    from rsm_thrive.models import PlannerSession

    session = PlannerSession.objects.filter(conversation=conversation).first()
    return session.review if session and session.review else None


def save_session_intake(conversation, answers):
    """Persist this conversation's in-progress interview.

    Accumulating rather than re-deriving keeps the interview steady if one
    extraction call comes back thin: a question already answered in this chat
    stays answered.
    """
    from rsm_thrive.models import PlannerSession

    session, created = PlannerSession.objects.get_or_create(
        conversation=conversation, defaults={"intake": answers})
    if not created:
        session.intake = answers
        session.save(update_fields=["intake", "updated_at"])
    return session


def save_intake(user, answers):
    """Persist a completed interview so the chat and the /plan API agree.

    Without this the two surfaces would each hold their own idea of the
    student's answers, and a swap made through one would be invisible to the
    other. Existing swaps are cleared because they were chosen against a plan
    built from different answers.
    """
    from rsm_thrive.models import CoursePlan

    record, created = CoursePlan.objects.get_or_create(
        user=user,
        defaults={"track": answers["track"], "intake": answers, "selections": {}},
    )
    if not created and record.intake != answers:
        record.track = answers["track"]
        record.intake = answers
        record.selections = {}
        record.save(update_fields=["track", "intake", "selections", "updated_at"])
    return record


def intake_extract_placeholders():
    """The vocabularies the extractor prompt has to be told about."""
    allowed = _allowed_values()
    return {
        "tracks": ", ".join(sorted(allowed["track"])),
        "role_ids": ", ".join(sorted(allowed["goals"])),
        "levels": ("an integer 1-5, where "
                   + ", ".join(f"{lvl['value']} means {lvl['help'].lower()}"
                               for lvl in SKILL_SCALE)),
        "workloads": ", ".join(sorted(allowed["workload"])),
        "interest_tags": ", ".join(sorted(allowed["interests"])),
        "skill_keys": ", ".join(f"skill_{area['key']}" for area in SKILL_AREAS),
    }


# ---------------------------------------------------------------------------
# Talking about a plan that already exists
# ---------------------------------------------------------------------------

# "MGTA 451", "CSE 251A", "MGT 477", "MGTF 405" — the shapes the catalog uses.
COURSE_CODE = re.compile(r"\b([A-Z]{2,4})\s*(\d{3}[A-Z]?)\b", re.IGNORECASE)


def mentioned_codes(text):
    """Course codes named in a message, normalised to catalog spelling."""
    known = {course["code"].upper() for course in load_catalog()}
    found = []
    for department, number in COURSE_CODE.findall(text or ""):
        code = f"{department.upper()} {number.upper()}"
        if code in known and code not in found:
            found.append(code)
    return found


def locate_code(plan, code):
    """Where a course sits in a plan: (quarter_key, slot, row).

    Matches the displayed code first and the bare catalog code second, so both
    "MGTA 495 (GENAI)" and "MGTA 495" find something. Returns
    (None, None, None) when nothing matches.
    """
    wanted = code.upper()
    for field in ("code", "baseCode"):
        for quarter in plan["quarters"]:
            for index, row in enumerate(quarter["courses"]):
                if (row.get(field) or "").upper() == wanted:
                    return quarter["key"], index, row
    return None, None, None


def rows_matching_code(plan, code):
    """Every plan row a bare code could mean — more than one when ambiguous."""
    wanted = code.upper()
    found = []
    for quarter in plan["quarters"]:
        for index, row in enumerate(quarter["courses"]):
            if wanted in {(row.get("code") or "").upper(),
                          (row.get("baseCode") or "").upper()}:
                found.append((quarter["key"], index, row))
    return found


def render_alternatives_markdown(result):
    """Alternatives as a table, with what each shares and what it costs."""
    current = result["current"]
    if not result["swappable"]:
        return (f"**{current['code']} — {current['title']}** cannot be changed: "
                f"{result['why']}.")
    if not result["options"]:
        return (f"There is no alternative for **{current['code']}**. "
                f"{result['why'].capitalize()}.")
    lines = [
        f"Other ways to fill that slot instead of **{current['code']} — "
        f"{current['title']}**:", "",
        "| Course | Title | Teaches some of the same | You would give up |",
        "|---|---|---|---|",
    ]
    for option in result["options"]:
        same = ", ".join(option["sharedSkills"][:2]) or \
            (", ".join(option["sharedFocus"]) or "a different angle on the same goal")
        lost = ", ".join(option["losesFromCurrent"][:2]) or "nothing important"
        lines.append(f"| **{option['code']}** | {option['title']} | {same} | {lost} |")
    lines += ["", "Reply with the code you want (for example "
              f"\"swap {current['code']} for {result['options'][0]['code']}\") "
              "and I'll update the plan."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Walking the plan, one quarter at a time
# ---------------------------------------------------------------------------

# Alternatives shown per slot during the review. Three is enough to make a real
# choice and few enough to read; the full list is always a question away.
REVIEW_ALTERNATIVES = 3


def _teaches(course, limit=2):
    """A short line on what a course actually gives you."""
    skills = (course.get("skills") or [])[:limit]
    if skills:
        return "; ".join(skills)
    return (course.get("description") or "").split(".")[0]


def review_quarter(plan, answers, index, taken_ids=frozenset()):
    """One quarter of the plan, with the alternatives for each elective slot.

    The plan arrives as a finished thing, which is the right way to arrive but
    the wrong way to be checked: a student handed twelve courses at once has no
    natural place to start disagreeing. Walking it a quarter at a time turns it
    into a sequence of small, answerable questions — here is what you are taking
    in Fall, here is why, here is what else would fit that slot and what each of
    those teaches instead.

    Returns (markdown, quick_replies, is_last).
    """
    quarters = plan["quarters"]
    index = max(0, min(index, len(quarters) - 1))
    quarter = quarters[index]
    catalog = _catalog_by_id()

    lines = [f"# {quarter['label']} — {quarter['unitsPlanned']} units",
             f"_Quarter {index + 1} of {len(quarters)}._", ""]

    core = [row for row in quarter["courses"] if row["requirement"] == "Core"]
    if core:
        lines += ["**Required this quarter — these are fixed:**", ""]
        lines += [f"- **{row['code']}** {row['title']} ({row['units']} units)"
                  for row in core]
        lines.append("")

    replies = []
    swappable = [(slot, row) for slot, row in enumerate(quarter["courses"])
                 if row["swappable"] and row["courseId"]]
    fixed_electives = [row for row in quarter["courses"]
                       if row["requirement"] == "Elective" and not row["swappable"]]
    if fixed_electives:
        lines += ["**Scheduled electives — no alternative is offered this quarter:**",
                  ""]
        lines += [f"- **{row['code']}** {row['title']} ({row['units']} units)"
                  for row in fixed_electives]
        lines.append("")

    for slot, row in swappable:
        course = catalog.get(row["courseId"])
        lines += [f"## Your {row['units']}-unit elective: {row['code']} — "
                  f"{row['title']}", ""]
        if row.get("reasons"):
            lines.append(f"Recommended because it {row['reasons'][0]}.")
        lines.append(f"**Teaches:** {_teaches(course)}." if course else "")
        for caution in row.get("cautions") or []:
            lines.append(f"> Heads up: it {caution}.")
        for stretch in row.get("stretch") or []:
            lines.append(f"> Heads up: {stretch}.")
        lines.append("")

        options = alternatives_for(plan, answers, quarter["key"], slot,
                                   taken_ids, REVIEW_ALTERNATIVES)["options"]
        if options:
            lines += ["Other courses that fit this slot:", ""]
            for option in options:
                alt = catalog.get(option["courseId"])
                shared = ", ".join(option["sharedSkills"][:1])
                lines.append(
                    f"- **{option['code']}** {option['title']} — teaches "
                    f"{_teaches(alt, 1)}."
                    + (f" Shares *{shared}* with {row['code']}." if shared else ""))
                # The label names the swap, not just the course. A quarter with
                # two elective slots can offer the SAME alternative for both —
                # Spring offered "Take MGT 451" twice — and two identical
                # buttons doing different things is a coin toss, not a choice.
                replies.append({
                    "label": f"{option['code']} instead of {row['code']}",
                    "send": f"swap {row['code']} for {option['code']}"})
            lines.append("")
        else:
            lines += ["Nothing else is offered at this size in this quarter, so "
                      "this slot is effectively fixed.", ""]

    is_last = index >= len(quarters) - 1
    replies.append({"label": "Finalise my plan" if is_last else "Next quarter",
                    "send": "finalise" if is_last else "next quarter"})
    return "\n".join(line for line in lines if line is not None), replies, is_last


def review_intent(text):
    """What a message is asking of the review, if anything.

    Deterministic word matching rather than another model call: these arrive
    from buttons, and the two or three ways a student types them by hand are
    easy to list. An LLM here would add a round trip and a failure mode to a
    decision that has three outcomes.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return None
    if any(phrase in lowered for phrase in
           ("finalise", "finalize", "looks good", "that works", "i'm happy",
            "im happy", "confirm")):
        return "finalise"
    if any(phrase in lowered for phrase in
           ("next quarter", "next", "continue", "keep going", "go on")):
        return "next"
    if any(phrase in lowered for phrase in
           ("walk me through", "go through", "review", "one at a time",
            "quarter by quarter", "step through")):
        return "start"
    return None


def review_intro_replies():
    """Offered with a finished plan: walk it, or take it as it stands."""
    return [{"label": "Walk me through it", "send": "walk me through it"},
            {"label": "Looks good", "send": "finalise"}]


def finalised_markdown(plan):
    """The closing message once the student is happy with the plan."""
    return ("# Your plan is set\n\n"
            + render_plan_markdown(plan)
            + "\n\nNothing here is booked yet — use the links above when "
              "enrolment opens, and come back any time to change a course.")
