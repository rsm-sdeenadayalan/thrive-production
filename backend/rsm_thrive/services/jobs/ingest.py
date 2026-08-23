"""Idempotent posting ingestion: fetch -> upsert -> skills -> embed -> expire.

A management command today; the F5 cron just schedules the same call.
"""

import logging

from django.utils import timezone

from rsm_thrive.models import JobPosting
from rsm_thrive.services.embeddings import get_embeddings
from rsm_thrive.services.jobs.skills import extract_skills

logger = logging.getLogger("rsm_thrive.jobs")


def ingest_from(sources, embeddings=None):
    embeddings = embeddings or get_embeddings()
    run_started = timezone.now()
    ingested = 0
    succeeded_names = []
    failed = []

    for source in sources:
        try:
            rows = source.fetch()
        except Exception:
            logger.exception("job source %s failed; keeping its postings", source.name)
            failed.append(source.name)
            continue
        good_rows = []
        for row in rows:
            url = row.get("url") or ""
            if (not url or len(url) > 200
                    or not url.startswith(("http://", "https://"))):
                logger.warning(
                    "job source %s row %s has an unusable url %r; skipping",
                    source.name, row.get("external_id"), url)
                continue
            good_rows.append(row)
        rows = good_rows

        texts = [f"{r['title']}\n{r['description'][:2000]}" for r in rows]
        vectors = embeddings.embed(texts) if texts else []
        for row, vector in zip(rows, vectors):
            JobPosting.objects.update_or_create(
                source=source.name, external_id=row["external_id"],
                defaults={
                    "title": (row["title"] or "")[:200],
                    "company": (row["company"] or "")[:120],
                    "location": (row["location"] or "")[:160],
                    "url": row["url"],
                    "description": row["description"],
                    "posted_at": row["posted_at"],
                    "last_seen_at": timezone.now(),
                    "active": True,
                    "skills": extract_skills(f"{row['title']} {row['description']}"),
                    "embedding": vector,
                })
            ingested += 1
        succeeded_names.append(source.name)

    deactivated = (JobPosting.objects
                   .filter(source__in=succeeded_names, active=True,
                           last_seen_at__lt=run_started)
                   .update(active=False))
    return {"ingested": ingested, "deactivated": deactivated,
            "failed_sources": failed}
