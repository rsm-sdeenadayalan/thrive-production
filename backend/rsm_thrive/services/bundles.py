"""Fixed routes: the design document's per-profile elective bundles.

Two ways to fill 28 elective units, and this module is the first:

* **Fixed** -- take the bundle the design document specifies for a job profile
  (`data/catalog/bundles.json`), as an anchor / differentiator / universal set.
  Every student targeting that profile gets the same plan, which is what makes
  it defensible: "this IS the Product Analyst bundle".
* **Custom** -- `planner.build_plan`'s existing behaviour, where the scoring
  engine fills each slot against this student's skills, workload and interests.

## Why a bundle carries its own slot shape

`TRACK_SKELETONS` declares elective slots with fixed unit sizes -- `[4, 2]` in
Fall, `[4, 4]` in Winter -- and `build_plan` requires an exact unit match. That
shape is an invention: the published plans of study
(`data/corpus/program/`) give a UNIT TOTAL per quarter and never say how it
divides. Measured against the real shapes, 0 of 14 bundles could be placed on
the 17-month track and 6 of 14 on the 11-month, because every bundle's
universal layer is MGTA 402 (2u) + MGTA 460 (2u) and the 17-month track has no
2-unit slot at all.

Rather than rework the slot model for every plan, a fixed route derives its own
slots from the courses it already knows it contains, and hands them to
`build_plan` as an override. The custom route is untouched, so nothing about
today's behaviour changes for a student who does not choose a bundle.

The quarter's published unit budget is still the constraint -- a derived shape
must sum to exactly what `TRACK_SKELETONS` says that quarter carries.
"""

import itertools
import json
from functools import lru_cache
from pathlib import Path

from rsm_thrive.services.electives import load_catalog, resolve_role

_DATA = Path(__file__).resolve().parent.parent / "data" / "catalog"

# The Summer slot is pre-placed by the published plan (MGTA 403 + MGTA 464), so
# a bundle never has to find room for 464 -- it is already in every plan.
PRE_PLACED = frozenset({"MGTA 403", "MGTA 464"})


@lru_cache(maxsize=1)
def load_bundles():
    """Profile id -> {anchor, differentiator, universal}. Keys starting with
    `_` are documentation, not profiles."""
    raw = json.loads((_DATA / "bundles.json").read_text())
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def bundle_for(role_id):
    """The bundle for a profile, resolving a retired role id forward."""
    resolved = resolve_role(role_id)
    return load_bundles().get(resolved) if resolved else None


@lru_cache(maxsize=1)
def _by_id():
    return {course["id"]: course for course in load_catalog()}


def _seasons(course_id):
    course = _by_id().get(course_id) or {}
    return {offering["season"] for offering in course.get("offerings") or []}


def _units(course_id):
    return (_by_id().get(course_id) or {}).get("units", 0)


def _quarter_budgets(skeleton):
    """(key, season, elective units) per quarter, from the published totals.

    Derived rather than read off the slots, because the slot shape is what this
    module replaces -- the budget is the part the plan of study actually states.
    """
    budgets = []
    for quarter in skeleton:
        spent = sum(_units(slot["course_id"]) for slot in quarter["slots"]
                    if slot["kind"] in ("core", "fixed"))
        budgets.append((quarter["key"], quarter["season"],
                        quarter["units"] - spent))
    return budgets


# How far a quarter may sit from its published elective load. The TOTAL is
# still exact -- 24 units across the plan, which with the pre-placed Summer pair
# is the 28 the degree requires -- but a quarter may run 2 light or 2 heavy.
#
# Necessary, not cosmetic. Exact per-quarter fill places 5 of 14 bundles on the
# 11-month track and 1 of 14 on the 17-month, because the catalog does not
# offer the shapes it would need: Winter has exactly ONE 2-unit elective
# (MGTA 466), so a Winter budget of 8 can only ever be 4+4, and any bundle
# wanting 466 is unschedulable. With 2 units of give, all 14 place on both
# tracks.
#
# Defensible against the source, too: the plans of study are published as
# SAMPLES -- the app repeats their "confirm your schedule with MSBA advising"
# on every plan it renders -- and students do shift a course between quarters.
QUARTER_FLEX = 2


def _place(courses, budgets):
    """Assign courses to quarters, or None if this set cannot be scheduled.

    The total must be spent exactly; each quarter may vary by `QUARTER_FLEX`.
    Most-constrained course first (fewest seasons, then largest), which keeps
    the search small enough to be exhaustive.
    """
    order = sorted(courses, key=lambda c: (len(_seasons(c)), -_units(c)))
    assigned = {key: [] for key, _season, _budget in budgets}
    load = {key: 0 for key, _season, _budget in budgets}
    ceiling = {key: budget + QUARTER_FLEX for key, _season, budget in budgets}
    floor = {key: max(0, budget - QUARTER_FLEX)
             for key, _season, budget in budgets}
    season_of = {key: season for key, season, _budget in budgets}

    def recurse(index):
        if index == len(order):
            return all(floor[key] <= load[key] <= ceiling[key] for key in load)
        course = order[index]
        for key in load:
            if season_of[key] not in _seasons(course):
                continue
            if load[key] + _units(course) > ceiling[key]:
                continue
            load[key] += _units(course)
            assigned[key].append(course)
            if recurse(index + 1):
                return True
            assigned[key].pop()
            load[key] -= _units(course)
        return False

    return assigned if recurse(0) else None


def choose_courses(role_id, track, taken_ids=frozenset()):
    """The bundle's courses for one track, sized to fit and placeable.

    Anchor and universal are mandatory -- they are what makes the plan that
    profile rather than a neighbouring one. Differentiators are added until the
    elective budget is exactly met, and the design document expects that: most
    bundles list more differentiators than fit, with "drop one" as the
    instruction.

    Returns (courses, placement) or (None, None) when no combination fits,
    which is a real answer rather than a failure -- it means this bundle cannot
    be scheduled on this track once the student's completed courses are
    excluded.
    """
    from rsm_thrive.services.planner import TRACK_SKELETONS

    bundle = bundle_for(role_id)
    skeleton = TRACK_SKELETONS.get(track)
    if not bundle or skeleton is None:
        return None, None

    budgets = _quarter_budgets(skeleton)
    target = sum(units for _key, _season, units in budgets)

    def usable(course_id):
        return (course_id in _by_id() and course_id not in PRE_PLACED
                and course_id not in taken_ids)

    required = [c for c in bundle["anchor"] + bundle["universal"] if usable(c)]
    required = list(dict.fromkeys(required))
    optional = [c for c in bundle["differentiator"]
                if usable(c) and c not in required]
    optional = list(dict.fromkeys(optional))

    needed = target - sum(_units(c) for c in required)
    if needed < 0:
        return None, None

    # Smallest addition first: the anchor is the profile, so a bundle that
    # closes on fewer differentiators is the more faithful one.
    for count in range(len(optional) + 1):
        for combination in itertools.combinations(optional, count):
            if sum(_units(c) for c in combination) != needed:
                continue
            courses = required + list(combination)
            placement = _place(courses, budgets)
            if placement is not None:
                return courses, placement
    return None, None


def skeleton_for(role_id, track, taken_ids=frozenset()):
    """`TRACK_SKELETONS[track]`, with elective slots shaped to this bundle.

    Core and fixed slots are copied through untouched -- the published sequence
    is not this module's to change. Only the elective slots are replaced, by
    one slot per bundle course sized to that course.
    """
    from rsm_thrive.services.planner import TRACK_SKELETONS

    skeleton = TRACK_SKELETONS.get(track)
    if skeleton is None:
        return None, None, None
    courses, placement = choose_courses(role_id, track, taken_ids)
    if courses is None:
        return None, None, None

    shaped, selections = [], {}
    for quarter in skeleton:
        slots = [dict(slot) for slot in quarter["slots"]
                 if slot["kind"] in ("core", "fixed")]
        pinned = placement.get(quarter["key"], [])
        # Largest first, so a quarter reads big-course-then-small rather than
        # in whatever order the search happened to assign.
        pinned = sorted(pinned, key=lambda c: (-_units(c), c))
        for position, course_id in enumerate(pinned):
            slots.append({"kind": "elective", "units": _units(course_id)})
            selections.setdefault(quarter["key"], {})[
                str(len(slots) - 1)] = course_id
        shaped.append({**quarter, "slots": slots})
    return shaped, selections, courses


def divergence(plan, role_id):
    """Bundle courses the student has swapped away from, by code.

    A fixed route the student has edited is no longer quite that bundle, and
    the design document is explicit that a recommendation which does not say
    what it gives up is not a recommendation. This is what the reply uses to
    say so.
    """
    bundle = bundle_for(role_id)
    if not bundle:
        return []
    present = {row["courseId"] for quarter in plan["quarters"]
               for row in quarter["courses"] if row.get("courseId")}
    catalog = _by_id()
    missing = [c for c in bundle["anchor"]
               if c not in present and c not in PRE_PLACED]
    return [catalog[c]["code"] for c in missing if c in catalog]
