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
