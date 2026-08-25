"""Stage-1 ranking and the role benchmark.

Portable by construction: term filtering via the ORM, similarity in Python
over stored embeddings (same pattern as chatbot retrieval — the posting set
is small). Postgres FTS is an F5 swap inside `_matching_postings` only.
"""

import logging
from collections import Counter

from django.db.models import Q

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import cosine, get_embeddings

logger = logging.getLogger("rsm_thrive.jobs")


def profile_of(user):
    version = ResumeVersion.objects.filter(user=user, is_current=True).first()
    if version is None:
        return None
    skills = {(s.get("name") or "").lower() for s in version.skills if s.get("name")}
    parts = [version.summary]
    parts += sorted(skills)
    for exp in version.experience:
        # Title alone used to be all that reached the embedding and the LLM
        # report -- organization and period (tenure) were silently dropped,
        # so nothing that scores a match could ever see "6 years as a Senior
        # Business Analyst." Both ride along now, e.g.
        # "Senior Business Analyst, Acme Corp (2019-2025)".
        header = ", ".join(p for p in (exp.get("title", ""), exp.get("organization", "")) if p)
        period = exp.get("period", "")
        if period:
            header = f"{header} ({period})" if header else period
        parts.append(header)
        parts += exp.get("bullets", [])
    return {"text": "\n".join(p for p in parts if p),
            "skills": skills, "version": version}


def _matching_postings(query):
    postings = JobPosting.objects.filter(active=True)
    for term in query.split():
        postings = postings.filter(Q(title__icontains=term)
                                   | Q(company__icontains=term)
                                   | Q(description__icontains=term))
    return postings


def search_postings(user, query, limit=20, embeddings=None):
    profile = profile_of(user)
    postings = list(_matching_postings(query))

    profile_vector = None
    if profile is not None and postings:
        embeddings = embeddings or get_embeddings()
        [profile_vector] = embeddings.embed([profile["text"]])
        for posting in postings:
            if posting.embedding:
                if len(posting.embedding) != len(profile_vector):
                    logger.warning(
                        "embedding dimension mismatch (profile %d vs postings %d) "
                        "— ranking degrades to skill overlap; re-run ingest_jobs "
                        "under the current THRIVE_LLM",
                        len(profile_vector), len(posting.embedding))
                break

    results = []
    for posting in postings:
        posting_skills = [s.lower() for s in posting.skills]
        if profile is not None:
            matched = sorted(set(posting_skills) & profile["skills"])
            missing = sorted(set(posting_skills) - profile["skills"])
            overlap = len(matched) / max(1, len(set(posting_skills)))
            score = 0.6 * cosine(profile_vector, posting.embedding) + 0.4 * overlap
        else:
            matched, missing, score = [], sorted(set(posting_skills)), 0.0
        results.append({"posting": posting, "score": score,
                        "matched_skills": matched, "missing_skills": missing})

    if profile is not None:
        results.sort(key=lambda r: (-r["score"], r["posting"].title))
    else:
        results.sort(key=lambda r: (r["posting"].posted_at is None,
                                    -(r["posting"].posted_at.timestamp()
                                      if r["posting"].posted_at else 0),
                                    r["posting"].title))
    return {"results": results[:limit],
            "benchmark": role_benchmark(query),
            "profile_available": profile is not None}


def role_benchmark(query):
    if not query.split():
        return {"sampleSize": 0, "topSkills": []}
    postings = JobPosting.objects.filter(active=True)
    for term in query.split():
        postings = postings.filter(title__icontains=term)
    rows = list(postings.values_list("skills", flat=True))
    if not rows:
        return {"sampleSize": 0, "topSkills": []}
    counts = Counter()
    for skills in rows:
        counts.update({s.lower() for s in skills})
    top = [{"name": name, "share": round(count / len(rows), 2)}
           for name, count in counts.most_common(10)]
    return {"sampleSize": len(rows), "topSkills": top}
