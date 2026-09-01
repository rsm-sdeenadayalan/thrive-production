"""Deterministic elective scoring against a structured student profile.

Ported from the Rady Recommender prototype's ``matcher.py``. The scoring
arithmetic is kept identical to the original; only the output shape and
the Django-facing helpers (``load_catalog``, ``load_careers``,
``recommend_for``) are new.

Produces a ranked list with human-readable reasons; the LLM may present or
lightly adjust this ranking but the base ordering is reproducible.
"""
import json
from functools import lru_cache
from pathlib import Path

from rsm_thrive.models import Enrollment

_DATA = Path(__file__).resolve().parent.parent / "data" / "catalog"

WORKLOAD_LEVEL = {"light": 1, "moderate": 2, "heavy": 3}


@lru_cache(maxsize=1)
def load_catalog():
    return json.loads((_DATA / "courses.json").read_text())


@lru_cache(maxsize=1)
def load_careers():
    return json.loads((_DATA / "careers.json").read_text())


@lru_cache(maxsize=1)
def _role_aliases():
    """Old role id -> the profile that absorbed it.

    The taxonomy moved from ten roles to the design document's fourteen
    profiles, and a saved `CoursePlan.intake` or an in-flight conversation may
    still carry an old id. The alias is declared on the profile itself
    (`legacy_ids`), so the mapping is stated once, in the data, beside the
    thing it maps to -- rather than in a second table that can drift out of
    step with the first.
    """
    return {old: new
            for new, role in load_careers().items()
            for old in role.get("legacy_ids") or []}


def resolve_role(role_id):
    """The current id for a role id that may predate the taxonomy change.

    Returns None for an id that is neither current nor a known alias, which is
    what keeps `normalise_intake` dropping an invented role rather than
    repairing it into something the student never said.
    """
    if role_id in load_careers():
        return role_id
    return _role_aliases().get(role_id)


# Words that make a question a COURSE question even when it names no course.
# "what can I take?" and "which classes are hands-on?" are both about the
# catalog and neither mentions a code or a title.
COURSE_WORDS = frozenset("""
course courses class classes elective electives core catalog curriculum
unit units credit credits prerequisite prerequisites prereq syllabus
offered offering quarter term seasons teach teaches taught instructor
workload difficulty hard easy technical topic topics skill skills tool tools
take taking enrol enroll enrolled study learn cover covers
""".split())

_COURSE_CODE = __import__("re").compile(r"\b([A-Z]{2,4})\s*(\d{3}[A-Z]?)\b", __import__("re").IGNORECASE)


def _searchable(course):
    """Everything about a course a student might name it by."""
    seasons = {o.get("season") for o in course.get("offerings") or []}
    # Season NAMES as well as codes: a student asks "which electives run in
    # winter", never "which run in WI".
    spelled = {"SU": "summer", "FA": "fall autumn", "WI": "winter",
               "SP": "spring"}
    parts = [course.get("code", ""), course.get("title", ""),
             course.get("description", ""), course.get("department", ""),
             course.get("workload", "")]
    parts.extend(spelled.get(season, "") for season in seasons if season)
    for key in ("topics", "skills", "tools", "career_tags"):
        parts.extend(course.get(key) or [])
    return " ".join(parts).lower()


def search_catalog(question, limit=6):
    """Courses this question is plausibly about, best first.

    Deterministic term overlap rather than embeddings: the catalog is 31 rows,
    the fields are short and specific, and a student asking about "Tableau" or
    "fraud" is naming something that appears literally. A vector search over
    thirty items would add a dependency and a failure mode to a lookup.

    A course named by CODE always wins -- "what is MGTA 458" is not a fuzzy
    question and should not be answered with six neighbours.
    """
    text = (question or "").lower()
    catalog = load_catalog()

    named = set()
    for department, number in _COURSE_CODE.findall(question or ""):
        named.add(f"{department.upper()} {number.upper()}")
    if named:
        hits = [c for c in catalog if c["code"].upper() in named]
        if hits:
            return hits

    # Without a course code, the question has to use the vocabulary of the
    # catalog before a term match counts. "What are the tuition fees?" shares
    # the word "tuition" with a course description and was being answered from
    # that course -- a confident answer to a question this bot was not asked.
    if not is_course_question(question):
        return []

    terms = {word.strip(".,/-?!") for word in text.split()}
    terms = {t for t in terms if len(t) > 3 and t not in COURSE_WORDS}
    if not terms:
        return []

    scored = []
    for course in catalog:
        haystack = _searchable(course)
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            scored.append((hits, course["code"], course))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [course for _hits, _code, course in scored[:limit]]


def is_course_question(question):
    """Does this ask about the catalog at all?

    True when it names a course, or uses the vocabulary of one. Everything else
    belongs to a different surface -- this bot plans courses and should say so
    rather than answer from whatever it can find.
    """
    text = (question or "").lower()
    if _COURSE_CODE.search(question or ""):
        return True
    words = {word.strip(".,/-?!") for word in text.split()}
    return bool(words & COURSE_WORDS)


# What each course prefix actually IS. Read off the catalog's own notes, which
# say it plainly -- "Pre-approved MSBA elective (MBA course -- enrollment by
# consent)" and so on. Asked "what courses do you have access to", a list of
# codes is not an answer: a student wants to know they can reach beyond the
# MSBA's own courses into CSE, MBA and MFin ones, and on what terms.
DEPARTMENT_LABELS = {
    "MGTA": ("Rady MSBA", "the programme's own courses — core and electives"),
    "CSE": ("UCSD Computer Science & Engineering",
            "pre-approved MSBA electives; CSE majors have enrolment priority, "
            "so seats go as space permits"),
    "MGT": ("Rady MBA",
            "pre-approved MSBA electives; enrolment by consent"),
    "MGTF": ("Rady MS Finance (MFin)",
             "pre-approved MSBA electives; enrolment by consent"),
}

# Up to 16 units of the 28 may come from outside the MSBA's own courses.
NON_MSBA_UNIT_CAP = 16


def departments_available():
    """Every programme this catalog reaches into, with counts and terms."""
    catalog = load_catalog()
    out = []
    for prefix in sorted({c.get("department", "") for c in catalog if c.get("department")}):
        rows = [c for c in catalog if c.get("department") == prefix]
        name, terms = DEPARTMENT_LABELS.get(prefix, (prefix, ""))
        out.append({
            "prefix": prefix, "name": name, "terms": terms,
            "total": len(rows),
            "core": sum(1 for r in rows if r["is_core"]),
            "electives": sum(1 for r in rows if not r["is_core"]),
            "codes": sorted(r["code"] for r in rows),
        })
    return out


def catalog_overview():
    """A summary for "what have you got?" -- a question no single course answers."""
    catalog = load_catalog()
    electives = [c for c in catalog if not c["is_core"]]
    departments = sorted({c.get("department", "") for c in catalog if c.get("department")})
    return {
        "total": len(catalog),
        "core": len(catalog) - len(electives),
        "electives": len(electives),
        "departments": departments,
        "programmes": departments_available(),
        "nonMsbaCap": NON_MSBA_UNIT_CAP,
        "codes": sorted(c["code"] for c in electives),
    }


def rank_electives(catalog, profile, careers=None):
    """Return electives sorted by descending fit score.

    profile: {
        "career_roles": [..],           # role ids from careers.json (e.g. "product-manager")
        "career_tags": [..],            # from the catalog's career-tag vocabulary
        "technical_comfort": 1-5,
        "workload_preference": "light" | "moderate" | "heavy",
        "interests": [..],              # free-text keywords
    }
    careers: careers.json dict mapping role id -> {label, career_tags, boost_courses}.

    Each result is {"course": dict, "score": float, "reasons": [str]},
    sorted descending by score with ties broken by course code.
    """
    careers = careers or {}
    # roles expand into ordered tags + direct course boosts; the first role
    # is the student's primary objective
    roles = [r for r in (profile.get("career_roles") or []) if r in careers]
    ordered_tags = list(profile.get("career_tags") or [])
    course_boosts = {}   # course_id -> [(points, role label), ...]
    for pos, role_id in enumerate(roles):
        role = careers[role_id]
        role_w = 1.0 / (1 + 0.5 * pos)
        for tag in role.get("career_tags") or []:
            if tag not in ordered_tags:
                ordered_tags.append(tag)
        for cid, pts in (role.get("boost_courses") or {}).items():
            course_boosts.setdefault(cid, []).append((pts * role_w, role["label"]))

    # profile tag order matters: the first tag is the student's primary goal
    tag_weight = {
        tag: 1.0 / (1 + 0.5 * pos) for pos, tag in enumerate(ordered_tags)
    }
    career_tags = set(tag_weight)
    tech = profile.get("technical_comfort", 3)
    workload_pref = WORKLOAD_LEVEL.get(profile.get("workload_preference"), 2)
    interests = [i.lower() for i in (profile.get("interests") or [])]

    results = []
    for course in catalog:
        if course["is_core"]:
            continue
        score = 0.0
        reasons = []

        # career-tag matches weighted by position: a course's first tag is its
        # primary focus, later tags are secondary
        course_tags = course.get("career_tags") or []
        matched = [(pos, tag) for pos, tag in enumerate(course_tags) if tag in career_tags]
        if matched:
            score += sum(3.0 / (1 + pos) * tag_weight[tag] for pos, tag in matched)
            reasons.append(
                "builds your " + ", ".join(tag for _, tag in matched) + " focus"
            )

        for pts, label in course_boosts.get(course["id"], []):
            score += pts
            reasons.insert(0, f"directly relevant for {label}")

        gap = course.get("technical_level", 3) - tech
        if gap > 0:
            score -= 1.5 * gap
            reasons.append(f"more technical than your comfort level (+{gap})")
        else:
            score += 0.5
            reasons.append("matches your technical level")

        # workload preference is a tolerance cap: only penalize courses that
        # demand more than the student wants to take on
        wl_over = WORKLOAD_LEVEL[course.get("workload", "moderate")] - workload_pref
        if wl_over > 0:
            score -= 0.75 * wl_over
            reasons.append(f"workload is {course['workload']} — above your preference")
        else:
            reasons.append(f"{course['workload']} workload fits your preference")

        haystack = " ".join(
            [course.get("title", ""), course.get("description", "")]
            + (course.get("topics") or [])
            + (course.get("skills") or [])
            + (course.get("tools") or [])
        ).lower()
        hits = [kw for kw in interests if kw in haystack]
        if hits:
            score += 2.0 * len(hits)
            reasons.append("covers your interest in " + ", ".join(hits))

        results.append({
            "course": course,
            "score": round(score, 2),
            "reasons": reasons,
        })

    results.sort(key=lambda r: (-r["score"], r["course"]["code"]))
    return results


def recommend_for(user, career_roles, interests=None, limit=5):
    profile = {
        "career_roles": career_roles,
        "career_tags": [],
        "technical_comfort": 3,
        "workload_preference": "moderate",
        "interests": interests or [],
    }
    ranked = rank_electives(load_catalog(), profile, load_careers())
    taken = _taken_codes(user)
    ranked = [r for r in ranked if r["course"]["code"] not in taken]
    return ranked[:limit]


def _taken_codes(user):
    return {
        enrollment.course.code
        for enrollment in Enrollment.objects.filter(user=user)
                                             .select_related("course")
    }
