"""Ranked job feed: search results overlaid with cached match reports and
per-user like/dismiss state, split into tabs.
"""

from rsm_thrive.models import MatchReport, PostingInteraction, ResumeVersion
from rsm_thrive.services.jobs.search import search_postings

TABS = {"recommended", "liked", "all"}


def feed_for(user, *, query="", tab="recommended", min_score=0, limit=50, embeddings=None):
    """Rank postings for `user`, overlay report/interaction state, and split into tabs."""
    if tab not in TABS:
        tab = "recommended"

    outcome = search_postings(user, query, limit=200, embeddings=embeddings)
    rows = outcome["results"]
    posting_ids = [row["posting"].pk for row in rows]

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

    recommended = [e for e in entries if not e["dismissed"]]
    liked = [e for e in entries if e["liked"]]

    counts = {"recommended": len(recommended), "liked": len(liked), "all": len(entries)}
    selected = {"recommended": recommended, "liked": liked, "all": entries}[tab]

    return {
        "results": selected[:limit],
        "counts": counts,
        "profile_available": outcome["profile_available"],
    }
