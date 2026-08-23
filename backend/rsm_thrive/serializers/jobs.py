from rsm_thrive.serialize import iso_instant

SNIPPET_LEN = 220


def serialize_job(posting, full=False) -> dict:
    payload = {
        "id": f"job-{posting.pk}",
        "title": posting.title,
        "company": posting.company,
        "location": posting.location,
        "url": posting.url,
        "source": posting.source,
        "skills": list(posting.skills),
        "postedAt": iso_instant(posting.posted_at) if posting.posted_at else None,
    }
    if full:
        payload["description"] = posting.description
    else:
        description = posting.description
        snippet = description[:SNIPPET_LEN]
        if len(description) > SNIPPET_LEN:
            snippet += "…"
        payload["snippet"] = snippet
    return payload
