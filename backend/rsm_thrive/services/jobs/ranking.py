"""Title-aware candidate ranking: pure, deterministic, and unit-tested so the
weights below are pinned rather than tuned by feel.

## The bug this exists to fix

`search_postings` used to rank purely on `0.6*cosine(resume, JD) +
0.4*skill_overlap` -- a resume-fit signal that never looks at the one thing
the student explicitly told the search: the role they typed in. A posting
whose TITLE names the searched role is obviously a stronger candidate than
one that merely shares vocabulary in its description, and the old ranking
had no way to express that. Measured case: a genuine "Data Analyst" posting
that scores 82 ("strong") under the real LLM rubric sat at cheap-pre-rank
#22 for the query "data analyst" -- outside the top-10 scoring window --
while a "Senior Workday Analyst, Payroll" posting (high resume-skill
overlap, unrelated role) occupied a spot inside it.

`rank_score` fixes candidate SELECTION only. It is not the number shown to
the student -- `search_postings` still reports the resume-fit score
(`0.6*cosine + 0.4*overlap`) as `score` for display/estimate purposes, same
as before. `rank_score` exists purely to decide which candidates advance to
the (expensive) LLM scoring window.
"""

import re

# Filler words stripped from both the query and the title before checking
# for a near-exact match, so "Data Analyst" and "Senior Data Analyst II" are
# recognized as the same role rather than merely "related."
_SENIORITY_WORDS = {
    "senior", "sr", "junior", "jr", "lead", "principal", "staff",
    "associate", "entry", "level", "i", "ii", "iii", "iv",
}

# Pinned by `test_job_ranking.py`: title relevance dominates resume fit, but
# a title match with a poor resume fit still loses to a title match with a
# good one -- resume fit remains a real, non-zero tiebreaker.
TITLE_WEIGHT = 0.65
RESUME_FIT_WEIGHT = 0.35


def _tokenize(text):
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split()


def _core_terms(tokens):
    return {t for t in tokens if t not in _SENIORITY_WORDS}


def title_match_score(query, title):
    """How well a posting's TITLE matches a searched role, 0.0-1.0.

    Pure and deterministic. Four tiers, cheapest signal that still separates
    "this posting IS the role" from "this posting merely mentions a word in
    it":

      1.0   -- the title equals the query once seniority/level filler words
               ("senior", "II", ...) are stripped from both sides.
      0.75  -- the title contains every query term as a whole word, but is
               not itself a near-exact match (extra words: a team, a
               product, a locale).
      >0,<0.75 -- the title contains SOME but not all query terms, scored by
               the fraction matched (so more overlap still ranks higher).
      0.0   -- the title contains none of the query's terms.
    """
    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0

    title_tokens = _tokenize(title)
    title_terms = set(title_tokens)

    core_query = _core_terms(query_terms)
    core_title = _core_terms(title_tokens)
    if core_query and core_title == core_query:
        return 1.0

    matched = sum(1 for term in query_terms if term in title_terms)
    if matched == len(query_terms):
        return 0.75
    return 0.5 * (matched / len(query_terms))


def rank_score(query, title, resume_fit):
    """The candidate-selection key: title relevance, then resume fit.

    `resume_fit` is expected in 0.0-1.0 (the existing
    `0.6*cosine + 0.4*skill_overlap` estimate). Not the number shown to a
    student -- see the module docstring.
    """
    return TITLE_WEIGHT * title_match_score(query, title) + RESUME_FIT_WEIGHT * resume_fit
