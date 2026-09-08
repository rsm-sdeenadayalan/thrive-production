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
2. **Which of our courses teach that?** `services/skill_match.py`, the same
   deterministic matcher the industry route uses. The model never picks a
   course, so it can never name one that does not exist.

   The matching used to be done here, by `_overlap`, and a second and different
   implementation lived in `grounded_course_advisor`. They disagreed: on one
   food-industry requirement set this one returned six courses and that one
   four, with three courses appearing in only one of them. Worse, `_overlap`
   accepted a match when every word LONGER THAN THREE CHARACTERS was present,
   so "cpg analytics" matched on "analytics" alone and picked up four courses
   on that basis. See `skill_match` for what replaced it and the measurements.

## It really does search the web

Stage 1 uses the model's built-in web search rather than its training memory,
so a role that appeared last year is described from what employers are asking
for now. Verified against the endpoint: the response stream carries
`response.web_search_call.searching` and `.completed`.

A backend that cannot search still works -- `LLM.search_chat` falls back to
`chat`, so the answer comes from the model's own knowledge instead of an error.
Degraded, not broken.
"""

from rsm_thrive.services import skill_match
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


def skills_for_role(llm, role_name):
    """What this job needs, as skills/tools/topics. None when it is not a job.

    Searches the web. The model is asked for SKILLS rather than courses because
    it does not know this catalog and would invent plausible-sounding codes --
    the mapping to real courses happens in `courses_for_role`, where it can only
    return rows that exist.

    The pages behind those skills come back under "sources" whenever the search
    was ours to run, so the reply can show where it read them. That list is
    empty, not missing, when the backend searched natively or could not search
    at all; `cite` renders nothing in either case rather than implying a lookup
    that did not happen.
    """
    sources = []
    try:
        raw = llm.search_chat(ROLE_SYSTEM,
                              [{"role": "user", "content": str(role_name)}],
                              json_mode=True, sources_out=sources,
                              search_query=f"{role_name} job required skills")
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
        # What the skills were read off, when we did the reading ourselves.
        # Empty for a natively-searching backend -- see `LLM.search_chat`.
        "sources": [{"title": r.title, "url": r.url} for r in sources[:4]],
        **lists,
    }


def courses_for_role(profile, limit=6):
    """Catalog courses that teach what this job needs, best first.

    Returns [{course, score, matched, reasons}] so the reply can say WHY a
    course is there -- "MGTA 495 for experiment design and A/B testing" is a
    recommendation; "MGTA 495" is an assertion.
    """
    wanted = ((profile.get("skills") or []) + (profile.get("tools") or [])
              + (profile.get("topics") or []))
    fits = skill_match.rank(wanted, limit=limit)
    return [{"course": fit.course, "score": round(fit.score, 2),
             "matched": fit.covered[:4],
             "reasons": skill_match.reasons(fit)}
            for fit in fits]


def coverage_for_role(profile, limit=6):
    """How much of this job the catalog actually covers. See `skill_match`.

    Re-ranks rather than taking `courses_for_role`'s output, because that
    flattens each `Fit` into a dict and loses the per-match evidence coverage
    is computed from. The ranking is deterministic and the catalog is 31 rows,
    so recomputing it costs nothing and cannot drift from what was recommended.
    """
    wanted = ((profile.get("skills") or []) + (profile.get("tools") or [])
              + (profile.get("topics") or []))
    return skill_match.coverage(wanted, skill_match.rank(wanted, limit=limit))


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


def explain_fit(llm, profile, matches, cover=None):
    """The conversational recommendation, grounded in the matched courses.

    The model is handed the matcher's own reasons, phrased in the CATALOG's
    words, plus what the catalog does not cover. Both halves are given because
    a recommendation that names only what it found reads as complete, and for a
    role we have no bundle for it usually is not.
    """
    from rsm_thrive.services.planner import display_code

    lines = [f"Target role: {profile['role']}",
             f"What it needs: {', '.join(profile.get('skills') or [])}"]
    for row in matches:
        course = row["course"]
        lines.append(
            f"{display_code(course)} — {course['title']} ({course['units']} "
            f"units): {'; '.join(row['reasons'])}")
    if cover and cover.get("unmet"):
        lines.append("NOT covered by any of these, say so plainly: "
                     + ", ".join(cover["unmet"][:5]))
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
    reply = explain_fit(llm, profile, matches, coverage_for_role(profile))
    if not reply:
        return None, matches
    return f"{reply}{cite(profile)}", matches


def cite(profile):
    """This role's sources line. See `websearch.cite`."""
    from rsm_thrive.services import websearch

    return websearch.cite(profile.get("sources"),
                          "What this role needs was read from the web just now")
