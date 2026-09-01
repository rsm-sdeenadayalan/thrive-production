"""Strict industry-to-course matching for the MSBA course recommender.

The web is used only to identify current skills/topics/tools associated with an
industry or target field. It is never used to choose a course. Course names,
units, prerequisites, offerings, and descriptions come exclusively from the
structured MSBA catalog, which is the course RAG source of truth.
"""

from __future__ import annotations

import re
from typing import Any

from rsm_thrive.services.electives import load_catalog
from rsm_thrive.services.llm import parse_llm_json

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

MIN_MATCHES = 2
MAX_RESULTS = 6

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


def _requirements(llm: Any, question: str) -> dict[str, list[str] | str] | None:
    try:
        raw = llm.search_chat(
            REQUIREMENTS_SYSTEM,
            [{"role": "user", "content": question}],
            json_mode=True,
        )
    except Exception:
        return None
    parsed = parse_llm_json(raw)
    if not isinstance(parsed, dict):
        return None
    result: dict[str, list[str] | str] = {
        "summary": str(parsed.get("summary") or ""),
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


def _course_text(course: dict[str, Any]) -> str:
    fields = [course.get("title"), course.get("description")]
    for key in ("skills", "topics", "tools"):
        fields.extend(course.get(key) or [])
    return " ".join(str(value).lower() for value in fields if value)


def _matches(requirements: dict[str, list[str] | str], catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = list(dict.fromkeys(
        value
        for key in ("skills", "tools", "topics")
        for value in requirements.get(key, [])  # type: ignore[union-attr]
    ))
    results = []
    for course in catalog:
        if course.get("is_core"):
            continue
        haystack = _course_text(course)
        matched = []
        for requirement in wanted:
            words = [word for word in re.findall(r"[a-z0-9]+", requirement) if len(word) > 2]
            if requirement in haystack or (words and all(word in haystack for word in words)):
                matched.append(requirement)
        if len(matched) >= MIN_MATCHES:
            results.append({"course": course, "matched": matched[:5], "score": len(matched)})
    results.sort(key=lambda row: (-row["score"], row["course"].get("code", "")))
    return results[:MAX_RESULTS]


def _render(requirements: dict[str, list[str] | str], matches: list[dict[str, Any]]) -> str:
    if not matches:
        return (
            "I searched for current skills used in that field, but I could not "
            "find at least two meaningful matches in the MSBA elective catalog. "
            "I won't recommend a course without a catalog match."
        )
    lines = [
        "I checked current industry requirements, then matched them only against "
        "electives in the MSBA catalog. These are the matches:",
    ]
    for row in matches:
        course = row["course"]
        lines.append(
            f"- **{course['code']} — {course['title']}** ({course['units']} units): "
            f"matches {', '.join(row['matched'])}."
        )
    lines.append(
        "These are relevance matches, not a guarantee of aerospace employment or "
        "course availability. Confirm prerequisites, offering terms, and approval "
        "requirements in the catalog or with MSBA advising."
    )
    return "\n".join(lines)


def recommend_for_question(llm: Any, question: str) -> tuple[str | None, list[str]]:
    """Search industry requirements once, then return only catalog-backed matches.

    Returns ``(None, [])`` when the question is not this segment's responsibility
    or the web lookup cannot produce usable requirements. The caller can then
    continue the normal course-planner flow.
    """
    if not is_industry_course_question(question):
        return None, []
    requirements = _requirements(llm, question)
    if not requirements:
        return None, []
    matches = _matches(requirements, load_catalog())
    body = _render(requirements, matches)
    return body, [row["course"]["code"] for row in matches]
