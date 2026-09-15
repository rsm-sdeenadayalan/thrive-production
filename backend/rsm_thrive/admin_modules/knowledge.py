"""Console admins: the RAG corpus (Documents/chunks) and resource links.

Documents are editable (e.g. to rescope which bots see them), but chunks are
view-only here: their text and embeddings are rebuilt by `ingest_corpus`, so
hand-editing a chunk would silently drift from the source and skip re-embedding.
The corpus content-management view (with a re-ingest action) is the write path.
"""

from django.contrib import admin

from rsm_thrive.models import Document, DocumentChunk, ResourceLink

from .base import ConsoleModelAdmin, ReadOnlyConsoleAdmin


@admin.register(Document)
class DocumentAdmin(ConsoleModelAdmin):
    list_display = ("title", "kind", "source", "fetched_at")
    list_filter = ("kind",)
    search_fields = ("title", "source")
    date_hierarchy = "fetched_at"


@admin.register(DocumentChunk)
class DocumentChunkAdmin(ReadOnlyConsoleAdmin):
    list_display = ("document", "seq", "heading")
    search_fields = ("heading", "text", "document__title")
    list_select_related = ("document",)
    exclude = ("embedding",)


@admin.register(ResourceLink)
class ResourceLinkAdmin(ConsoleModelAdmin):
    list_display = ("title", "category", "owner", "url")
    list_filter = ("category",)
    search_fields = ("title", "description")
