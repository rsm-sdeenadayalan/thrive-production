"""Industry -> current requirements -> our catalog. The web never names a course.

Two stages, and the boundary between them is the whole design:

1. **What does this field ask for?** One web-backed model call
   (`REQUIREMENTS_SYSTEM`), asked ONLY for skills, tools and topics. The prompt
   forbids it from recommending a course or discussing the catalog, because it
   does not know the catalog and would invent plausible-sounding codes.
2. **Which of our courses teach that?** `services/skill_match.py`, which is
   deterministic and can only ever return rows that exist.

Course names, units, prerequisites, offerings and descriptions come exclusively
from the structured MSBA catalog.

The matching itself used to live here, in `_matches` and `_requirement_matches`,
and a second copy of it lived in `role_lookup`. They disagreed on identical
input, and both weighted "python" the same as "cost effectiveness analysis" --
so an aerospace question came back with the three courses that share the most
generic tooling with it. `skill_match` replaced both; see its docstring for the
measurements. What stays here is this route's own question (an INDUSTRY, not a
job), its cache, and how the answer reads.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

from rsm_thrive.services import skill_match
from rsm_thrive.services.llm import parse_llm_json
from rsm_thrive.services.skill_match import THIN_COVERAGE

_COURSE_WORDS = frozenset(
    "course courses class classes elective electives msba program take teach "
    "study learn units credits prerequisite prerequisites"
    .split()
)
_TARGET_MARKERS = frozenset(
    "industry field sector domain career role job profession pathway"
    .split()
)
_GENERIC_TARGETS = frozenset(
    "industry field sector domain career role job profession pathway the msba "
    "program course courses class classes elective electives"
    .split()
)
_TARGET_PHRASE = re.compile(
    r"\b(?:in|for|toward|towards|within|support|assist(?:ing)?|help(?:ing)?)\s+"
    r"(?:the\s+)?([a-z][a-z0-9/& -]{2,70}?)(?=\s+(?:industry|field|sector|domain|career|role|job)\b|[?.!,]|$)",
    re.IGNORECASE,
)

MAX_RESULTS = 6

# What a field's requirements are worth caching for. The promise is "current",
# not "live": hiring patterns move over months, and re-searching the same field
# for every student who asks costs 8s to arrive at the same answer. Measured on
# this backend: the lookup is 8.3s median, of which the web search is 3.4s.
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_FIELDS = 128
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()

# Keeps "c++", "c#" and ".net" in one piece rather than splitting them to noise.
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.]*")

REQUIREMENTS_SYSTEM = (
    "You support an MSBA course recommender. Use web search for a quick, current "
    "view of the skills, tools, and topics used in the student's target industry "
    "or field. Do not recommend courses and do not discuss the MSBA catalog. "
    "Return JSON only with exactly these keys: {\"summary\": string, "
    "\"skills\": [6-10 concrete lowercase skills], \"tools\": [software or "
    "languages], \"topics\": [subject areas]}. Prefer requirements that recur "
    "in current job postings and reputable industry skill guides. Keep it concise."
)


def is_industry_course_question(question: str) -> bool:
    """Return true for a course question that names any target field."""
    words = set(re.findall(r"[a-z]+", (question or "").lower()))
    if not words & _COURSE_WORDS:
        return False
    phrase = _TARGET_PHRASE.search(question or "")
    if phrase:
        target_words = set(re.findall(r"[a-z]+", phrase.group(1).lower()))
        if target_words - _GENERIC_TARGETS:
            return True
    # Also support concise forms such as "electives for healthcare" or
    # "courses, data science" while excluding a bare generic catalog request.
    if words & _TARGET_MARKERS:
        return len(words - _COURSE_WORDS - _GENERIC_TARGETS) >= 1
    return False


def _requirements(llm: Any, question: str,
                  field: str | None = None) -> dict[str, Any] | None:
    sources: list = []
    try:
        raw = llm.search_chat(
            REQUIREMENTS_SYSTEM,
            [{"role": "user", "content": question}],
            json_mode=True,
            sources_out=sources,
            # The FIELD, not the sentence it arrived in. See `LLM.search_chat`:
            # searching "what should I take if I want to work in esports?"
            # verbatim grounds a question about hiring in course-marketing
            # pages, which is worse than not searching at all.
            search_query=(f"{field} jobs required skills" if field
                          else f"{question} required skills"),
        )
    except Exception:
        return None
    parsed = parse_llm_json(raw)
    if not isinstance(parsed, dict):
        return None
    result: dict[str, Any] = {
        "summary": str(parsed.get("summary") or ""),
        # Travels with the requirements, and therefore through the cache: a
        # cached field replays the pages its own lookup read, which is the
        # honest answer for an answer that is itself being replayed.
        "sources": [{"title": r.title, "url": r.url} for r in sources[:4]],
    }
    for key in ("skills", "tools", "topics"):
        values = parsed.get(key) or []
        if not isinstance(values, list):
            return None
        result[key] = list(dict.fromkeys(
            str(value).strip().lower() for value in values
            if isinstance(value, (str, int, float)) and str(value).strip()
        ))
    if not any(result[key] for key in ("skills", "tools", "topics")):
        return None
    return result


# Function words and generic verbs that can land inside a captured field.
# "help me work in healthcare analytics" matches at "help" and captures
# "me work in healthcare analytics"; the field is the last two words.
_FIELD_STOPWORDS = frozenset(
    "a an the me my mine i we us our you your it its that this these those to "
    "into toward towards of on at in for with and or work working works "
    "get getting go going want wanting like want need needs help helping "
    "assist assisting support supporting be been being do doing does "
    "would could should can may might will after later someday"
    .split()
)


def _target_field(question: str) -> str | None:
    """The field the student named, e.g. "healthcare analytics". None if unsure.

    Every capture the pattern can make is considered, and the SHORTEST one that
    still names something survives. A single question yields several: "help me
    work in healthcare analytics" matches at both "help" and "in", giving "me
    work in healthcare analytics" and "healthcare analytics". The longer one is
    noise, and since the field is matched as a whole -- every token has to be
    present -- one stray word is enough to credit nothing at all.

    Only what the pattern captures is trusted. `is_industry_course_question` has
    a looser branch that routes on leftover words, and words like "work" do
    appear in course descriptions, so crediting them would hand a domain match
    to most of the catalog. When the field cannot be named confidently, no
    credit is awarded and behaviour is exactly what it was.

    The field comes from the student's own question, never from the web, so the
    module's grounding boundary is untouched.
    """
    candidates = []
    for phrase in _TARGET_PHRASE.finditer(question or ""):
        tokens = [token for token in _TOKEN.findall(phrase.group(1).lower())
                  if token not in _GENERIC_TARGETS and token not in _FIELD_STOPWORDS]
        if tokens:
            candidates.append(tokens)
    if not candidates:
        return None
    return " ".join(min(candidates, key=len))


def _cached_requirements(llm: Any, question: str, field: str | None) -> dict[str, Any] | None:
    """`_requirements`, but a field is looked up once a day rather than a turn.

    Keyed on the FIELD, not the question, so "electives for healthcare" and
    "which electives help me work in healthcare?" share one lookup -- they are
    the same question about the same industry, and the prompt only ever asks
    about the industry.

    The network call is deliberately made OUTSIDE the lock. Holding it across an
    8-second request would serialise every student on the box behind whichever
    one asked first, turning a latency win into a queue. Two turns racing the
    same cold field both search, and the second overwrites the first with an
    equivalent answer -- cheaper than the alternative.
    """
    key = field or " ".join(_TOKEN.findall((question or "").lower()))
    if not key:
        return _requirements(llm, question, field)

    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]

    result = _requirements(llm, question, field)
    if result is None:
        return None

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_FIELDS:
            # Unbounded growth is the risk: the key comes from student text, so
            # typos and odd phrasings each make an entry. Drop the oldest.
            oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
            _CACHE.pop(oldest, None)
        _CACHE[key] = (now, result)
    return result


def reset_requirements_cache() -> None:
    """For tests, and for a deploy that wants a cold start."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _cite(requirements):
    """This field's sources line. See `websearch.cite`.

    Rendered on the no-match answer too: that one opens "I searched for the
    skills this field is hiring for", and a claim to have searched owes the
    same evidence whether or not the search led anywhere.
    """
    from rsm_thrive.services import websearch

    return websearch.cite(requirements.get("sources"),
                          "What this field needs was read from the web just now")


def _render(requirements, fits, cover, field):
    """The answer, in the catalog's words, with what is missing said out loud.

    The coverage line is the half that was absent and it is what turns the
    aerospace case from unhelpful into useful. Measured on an aerospace
    requirement set, this catalog meets 30% of what the field asks for
    (weighted by how much each requirement discriminates) -- it has the Excel,
    the forecasting and the visualisation, and nothing at all for systems
    engineering, reliability analysis, predictive maintenance or statistical
    process control. Three courses with no caveat reads as "these will get you
    there". Three courses plus that sentence reads as what it is.
    """
    from rsm_thrive.services.planner import display_code

    summary = str(requirements.get("summary") or "").strip()
    named = f"**{field}**" if field else "that field"
    if not fits:
        return "\n\n".join(filter(None, (
            summary,
            f"I searched for the skills {named} is currently hiring for and "
            f"matched them against the MSBA elective catalog. Nothing in the "
            f"catalog matches enough of it for me to recommend a course "
            f"honestly"
            + (f" — what that field asks for and we don't teach: "
               f"{', '.join(cover['unmet'][:5])}." if cover["unmet"] else ".")
            + "\n\nI won't name a course without a catalog match. **MSBA "
              "advising** can tell you whether the programme supports that "
              "direction; you can book time from the **Appointments** tab.",
        ))) + _cite(requirements)

    lines = []
    if summary:
        lines += [summary, ""]
    thin = cover["metShare"] < THIN_COVERAGE
    if thin:
        lines.append(
            f"Before the list: this catalog covers roughly "
            f"**{cover['metShare']:.0%}** of what {named} is currently asking "
            f"for. What matched is largely general analytics skill and tooling; "
            f"what it has nothing for is "
            f"{', '.join(cover['unmet'][:4])}. These are the closest we have, "
            f"not a route into that field.")
    else:
        lines.append(
            f"I checked what {named} is currently asking for, then matched it "
            f"only against electives in this catalog — about "
            f"**{cover['metShare']:.0%}** of it is covered here. The closest "
            f"matches:")
    lines.append("")
    for fit in fits:
        course = fit.course
        why = "; ".join(skill_match.reasons(fit))
        lines.append(f"- **{display_code(course)} — {course['title']}** "
                     f"({course['units']} units): {why}.")
    if cover["unmet"] and not thin:
        lines += ["", "_Not covered by anything here: "
                      + ", ".join(cover["unmet"][:5]) + "._"]
    lines += ["", "These are relevance matches, not a guarantee of employment "
                  "in that field or of course availability. Confirm "
                  "prerequisites, offering terms and approval requirements in "
                  "the catalog or with MSBA advising."]
    return "\n".join(lines) + _cite(requirements)


def recommend_for_question(llm: Any, question: str) -> tuple[str | None, list[str]]:
    """Search the field's requirements once, then return only catalog matches.

    Returns ``(None, [])`` when the question is not this route's responsibility
    or the web lookup cannot produce usable requirements — the caller then
    continues its own flow. A lookup that SUCCEEDS and matches nothing returns
    a body and an empty code list, which is a different thing: it is an answer,
    and it says the catalog does not serve that field.
    """
    if not is_industry_course_question(question):
        return None, []
    field = _target_field(question)
    requirements = _cached_requirements(llm, question, field)
    if not requirements:
        return None, []
    wanted = [value for key in ("skills", "tools", "topics")
              for value in requirements.get(key, [])]
    fits = skill_match.rank(wanted, domain=field, limit=MAX_RESULTS)
    cover = skill_match.coverage(wanted, fits)
    return _render(requirements, fits, cover, field), [
        fit.course["code"] for fit in fits]
