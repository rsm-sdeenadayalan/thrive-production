"""Top-k chunk retrieval scoped to a destination."""

from rsm_thrive.models import DocumentChunk
from rsm_thrive.services.embeddings import cosine, get_embeddings


def retrieve(query, destination, top_k, min_similarity, embeddings=None):
    embeddings = embeddings or get_embeddings()
    [query_vector] = embeddings.embed([query])
    scored = []
    rows = DocumentChunk.objects.select_related("document")
    for chunk in rows:
        if destination not in (chunk.document.destinations or []):
            continue
        score = cosine(query_vector, chunk.embedding)
        if score >= min_similarity:
            scored.append((chunk, score))
    scored.sort(key=lambda pair: -pair[1])
    return scored[:top_k]
