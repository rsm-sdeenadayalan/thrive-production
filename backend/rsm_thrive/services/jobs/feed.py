"""Ranked job feed: search results overlaid with cached match reports and
per-user like/dismiss state, split into tabs.
"""

import logging

from rsm_thrive.models import MatchReport, PostingInteraction, ResumeVersion
from rsm_thrive.services.jobs.report import generate_report
from rsm_thrive.services.jobs.search import search_postings

logger = logging.getLogger("rsm_thrive.jobs")

TABS = {"recommended", "liked", "all"}

# How many of the cheap pre-rank's top candidates get a real LLM assessment
# when `score_with_llm=True`. This is the results page's whole shortlist
# (see `targetResults`'s `cap`), so scoring exactly this many keeps one fresh
# search affordable: cached hits are free, a miss is one LLM call.
LLM_SCORE_TOP_N = 10


def _score_top_candidates_with_llm(user, candidates, llm_factory):
    """Ensure a `MatchReport` exists for each of `candidates` (already the
    cheap pre-rank's top slice -- see `LLM_SCORE_TOP_N`), one real LLM call
    per cache miss.

    Never raises. The LLM backend can be entirely unavailable (bad/missing
    key, network down) or fail on one specific posting (timeout, malformed
    JSON) -- either way that posting simply keeps its cheap-score estimate
    and the caller's request still succeeds. Callers pick up the freshly
    cached reports by re-querying `MatchReport` afterward.
    """
    llm = None
    llm_unavailable = False
    for row in candidates:
        posting = row["posting"]
        if llm is None and not llm_unavailable:
            try:
                llm = llm_factory()
            except Exception:
                logger.warning(
                    "LLM backend unavailable for match-report scoring (user=%s) "
                    "-- results page will show estimates for this search",
                    user.pk, exc_info=True)
                llm_unavailable = True
        if llm is None:
            continue
        try:
            generate_report(llm, user, posting)
        except Exception:
            logger.warning(
                "match-report generation failed (posting=%s, user=%s) "
                "-- falling back to that posting's estimate",
                posting.pk, user.pk, exc_info=True)


def feed_for(user, *, query="", tab="recommended", min_score=0, limit=50, embeddings=None,
             score_with_llm=False, llm_factory=None):
    """Rank postings for `user`, overlay report/interaction state, and split into tabs.

    `score_with_llm=True` is the results page's opt-in: the top
    `LLM_SCORE_TOP_N` candidates from the cheap pre-rank each get a real
    `generate_report` call (cache-first, so a repeat search against the same
    resume version costs nothing).

    That scoring pass changes what `tab="recommended"` returns, and ONLY
    that tab: Recommended is rebuilt from just that scored candidate
    window, re-sorted by the report's score (the cheap estimate only as a
    fallback for a posting whose report generation failed), with the floor
    (`min_score`) re-applied against that same score. Crucially, Recommended
    does NOT fall back to the next-best cheap-rank candidates outside that
    window -- a posting the LLM never actually looked at competing on an
    unverified proxy score is exactly the bug this whole feature exists to
    fix, one rank down. `all` and `liked` are untouched by `score_with_llm`:
    they still mean "everything matching the search," so they keep showing
    every candidate in the cheap pre-rank's own order, picking up whatever
    report happens to be cached (same overlay this function always did).
    """
    if tab not in TABS:
        tab = "recommended"

    outcome = search_postings(user, query, limit=200, embeddings=embeddings)
    rows = outcome["results"]
    posting_ids = [row["posting"].pk for row in rows]

    scored_pks = set()
    if score_with_llm and outcome["profile_available"] and llm_factory is not None:
        candidates = rows[:LLM_SCORE_TOP_N]
        scored_pks = {row["posting"].pk for row in candidates}
        _score_top_candidates_with_llm(user, candidates, llm_factory)

    interactions = {
        i.posting_id: i
        for i in PostingInteraction.objects.filter(user=user, posting_id__in=posting_ids)
    }

    current_version = ResumeVersion.objects.filter(user=user, is_current=True).first()
    reports = {}
    if current_version is not None:
        reports = {
            r.posting_id: r
            for r in MatchReport.objects.filter(
                user=user, resume_version=current_version, posting_id__in=posting_ids)
        }

    entries = []
    for row in rows:
        posting = row["posting"]
        interaction = interactions.get(posting.pk)
        report = reports.get(posting.pk)
        score = int(round(row["score"] * 100))
        report_score = report.score if report is not None else None
        display = report_score if report_score is not None else score
        if display < min_score:
            continue
        entries.append({
            "posting": posting,
            "score": score,
            "report_score": report_score,
            "competency": report.competency if report is not None else None,
            "matched_skills": row["matched_skills"],
            "missing_skills": row["missing_skills"],
            "liked": interaction.liked if interaction is not None else False,
            "dismissed": interaction.dismissed if interaction is not None else False,
        })

    if score_with_llm:
        recommended = [e for e in entries
                      if e["posting"].pk in scored_pks and not e["dismissed"]]
        recommended.sort(key=lambda e: (
            -(e["report_score"] if e["report_score"] is not None else e["score"]),
            e["posting"].title))
    else:
        recommended = [e for e in entries if not e["dismissed"]]
    liked = [e for e in entries if e["liked"]]

    counts = {"recommended": len(recommended), "liked": len(liked), "all": len(entries)}
    selected = {"recommended": recommended, "liked": liked, "all": entries}[tab]

    return {
        "results": selected[:limit],
        "counts": counts,
        "profile_available": outcome["profile_available"],
    }
