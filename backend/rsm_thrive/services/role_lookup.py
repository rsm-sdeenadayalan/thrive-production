"""Careers the catalog has no profile for.

`careers.json` covers fourteen job profiles. A student who names something else
-- "esports analyst", "climate risk modeller", "sports scientist" -- used to be
told their career was not covered and handed a menu of ten roles they had not
asked about. That is a refusal dressed as help: the courses that serve those
jobs are in the catalog, they just are not filed under that name.

Two stages, which is the same shape the electives bot already uses:

1. **What does that job need?** Asked of the model, which knows far more job
   titles than we will ever curate. It answers with skills, tools and topics --
   NOT with courses, because it does not know our catalog and would invent
   plausible-sounding ones.
2. **Which of our courses teach that?** Matched here, deterministically, against
   the catalog's own `skills` / `topics` / `tools` fields. The model never picks
   a course, so it can never name one that does not exist.

## It really does search the web

Stage 1 uses the model's built-in web search rather than its training memory,
so a role that appeared last year is described from what employers are asking
for now. Verified against the endpoint: the response stream carries
`response.web_search_call.searching` and `.completed`.

A backend that cannot search still works -- `LLM.search_chat` falls back to
`chat`, so the answer comes from the model's own knowledge instead of an error.
Degraded, not broken.
"""

import json

from rsm_thrive.services.electives import load_catalog
from rsm_thrive.services.llm import parse_llm_json

ROLE_SYSTEM = (
    "You describe what a job actually requires, for a graduate advising tool. "
    "Search the web for current postings and skill guides for this role before "
    "answering, so the skills reflect what employers are asking for now. "
    "Reply with JSON only: {\"known\": <true if this is a real job you can "
    "describe, false otherwise>, \"role\": \"<the job's common name>\", "
    "\"summary\": \"<one sentence on what the work is>\", \"skills\": [<6-10 "
    "concrete skills, lowercase, e.g. 'sql', 'causal inference', 'demand "
    "forecasting'>], \"tools\": [<software and languages, lowercase>], "
    "\"topics\": [<subject areas, lowercase>]}. "
    "Use plain skill names a course catalog would recognise, not job jargon. "
    "If the input is not a job at all, set known=false and leave the lists "
    "empty.")

# Below this, the match is incidental rather than real -- one shared word
# between a job and a course means little when both mention "data".
MIN_MATCH_SCORE = 2


def skills_for_role(llm, role_name):
    """What this job needs, as skills/tools/topics. None when it is not a job.

    Searches the web. The model is asked for SKILLS rather than courses because
    it does not know this catalog and would invent plausible-sounding codes --
    the mapping to real courses happens in `courses_for_role`, where it can only
    return rows that exist.
    """
    try:
        raw = llm.search_chat(ROLE_SYSTEM,
                              [{"role": "user", "content": str(role_name)}],
                              json_mode=True)
    except Exception:
        return None
    parsed = parse_llm_json(raw)
    if not isinstance(parsed, dict) or not parsed.get("known"):
        return None
    lists = {key: [str(v).lower() for v in (parsed.get(key) or [])
                   if isinstance(v, (str, int, float))]
             for key in ("skills", "tools", "topics")}
    if not any(lists.values()):
        return None
    return {
        "role": str(parsed.get("role") or role_name),
        "summary": str(parsed.get("summary") or ""),
        **lists,
    }


def _course_terms(course):
    """The catalog's own words for what a course teaches."""
    parts = []
    for key in ("skills", "topics", "tools"):
        parts.extend(str(v).lower() for v in (course.get(key) or []))
    parts.append(str(course.get("title", "")).lower())
    parts.append(str(course.get("description", "")).lower())
    return " ".join(parts)


def _overlap(needle, haystack):
    """Does this requirement appear in what the course teaches?

    Substring in both directions: the catalog says "designing and building
    interactive dashboards" where a job needs "dashboards", and the job may say
    "sql" where the catalog says "sql and etl". Neither contains the other
    exactly, and both are the same skill.
    """
    needle = needle.strip()
    if len(needle) < 3:
        return False
    if needle in haystack:
        return True
    words = [w for w in needle.split() if len(w) > 3]
    return bool(words) and all(word in haystack for word in words)


def courses_for_role(profile, limit=6):
    """Catalog courses that teach what this job needs, best first.

    Returns [{course, score, matched}] so the reply can say WHY a course is
    there -- "MGTA 458 for experiment design and A/B testing" is a
    recommendation; "MGTA 458" is an assertion.
    """
    wanted = list(dict.fromkeys(
        (profile.get("skills") or []) + (profile.get("tools") or [])
        + (profile.get("topics") or [])))
    scored = []
    for course in load_catalog():
        if course["is_core"]:
            continue          # nothing to recommend: everyone takes these
        haystack = _course_terms(course)
        matched = [need for need in wanted if _overlap(need, haystack)]
        if len(matched) >= MIN_MATCH_SCORE:
            scored.append({"course": course, "score": len(matched),
                           "matched": matched[:4]})
    scored.sort(key=lambda row: (-row["score"], row["course"]["code"]))
    return scored[:limit]


EXPLAIN_SYSTEM = (
    "You are THRIVE, the Rady MSBA course planner, talking to a student whose "
    "target career has no ready-made bundle in this programme. You are given "
    "what that job needs and the courses from OUR catalog that teach those "
    "things, already matched. Write a short, warm, conversational reply: say "
    "you do not have a prepared path for that role but here is what the "
    "catalog does offer for it, then name each course by code with one line on "
    "which requirement it covers. Recommend ONLY the courses given to you — "
    "never invent one. Finish by inviting them to go with this or name a "
    "closer-fitting role. At most 150 words. Do not use headings.")


def explain_fit(llm, profile, matches):
    """The conversational recommendation, grounded in the matched courses."""
    lines = [f"Target role: {profile['role']}",
             f"What it needs: {', '.join(profile.get('skills') or [])}"]
    for row in matches:
        course = row["course"]
        lines.append(
            f"{course['code']} — {course['title']} ({course['units']} units): "
            f"covers {', '.join(row['matched'])}")
    try:
        return (llm.chat(EXPLAIN_SYSTEM,
                         [{"role": "user", "content": "\n".join(lines)}])
                or "").strip()
    except Exception:
        return ""


def recommend_for_unknown_role(llm, role_name):
    """(reply, matches) for a career the catalog has no profile for.

    (None, []) when the role cannot be described or nothing in the catalog
    teaches it -- the caller then falls back to asking the student to pick a
    covered role, which is the honest answer when it is the true one.
    """
    profile = skills_for_role(llm, role_name)
    if not profile:
        return None, []
    matches = courses_for_role(profile)
    if not matches:
        return None, []
    reply = explain_fit(llm, profile, matches)
    return (reply or None), matches
