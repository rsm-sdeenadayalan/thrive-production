from django.db import models
from django.utils import timezone

KIND_CHOICES = [("syllabus", "syllabus"), ("policy", "policy"),
                ("catalog", "catalog"), ("scraped", "scraped")]


class Document(models.Model):
    """One ingested source (a PDF, a page, a catalog entry group)."""
    source = models.CharField(max_length=300, unique=True)  # stable ingest key
    title = models.CharField(max_length=300)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    destinations = models.JSONField(default=list)  # which bots may retrieve it
    # The public page this document came from, when there is one. Answers cite
    # it so a student can open the authoritative source instead of taking the
    # bot's word for a deadline. Blank for fixtures and hand-pasted material.
    source_url = models.URLField(max_length=600, blank=True, default="")
    fetched_at = models.DateTimeField(default=timezone.now)


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE,
                                 related_name="chunks")
    seq = models.IntegerField()
    heading = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    # A JSON list of floats, cosine-scanned in Python: the corpus is a few
    # thousand chunks at most. pgvector is a drop-in swap at F5 if it grows.
    embedding = models.JSONField(default=list)

    class Meta:
        ordering = ["document_id", "seq"]
        constraints = [models.UniqueConstraint(
            fields=["document", "seq"], name="uniq_document_chunk_seq")]
