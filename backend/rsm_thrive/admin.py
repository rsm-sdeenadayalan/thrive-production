"""Staff-facing views of the chat record.

Deliberately narrow. This is not a general admin for the app's thirty-odd
models — it is the one surface a person opens when a tester says "that answer
was bad", and everything on it exists to answer *why did it say that*.

The trace page renders the retrieved passages IN FULL, inline, under the reply
they produced. That is the whole point: the spec's promise is that a wrong
answer is traceable to the exact chunks in one look, and a list of chunk ids
requires a second lookup per id, which in practice means nobody checks. Seeing
the passages next to the answer is what settles the question the chunk ids only
raise — whether a bad answer is a retrieval problem or a model problem.
"""

from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from rsm_thrive.models import (ChatMessage, ChatTurnLog, Conversation,
                               DocumentChunk, TurnFeedback)


class TurnFeedbackInline(admin.StackedInline):
    model = TurnFeedback
    extra = 0
    can_delete = True
    readonly_fields = ("user", "created_at", "updated_at")


@admin.register(ChatTurnLog)
class ChatTurnLogAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    list_display = ("created_at", "bot", "route", "model_note", "refused",
                    "thumb", "duration_ms", "short_question")
    list_filter = ("bot", "route", "model_note", "refused", "feedback__rating")
    search_fields = ("question", "message__body")
    inlines = [TurnFeedbackInline]
    readonly_fields = ("created_at", "message", "bot", "route",
                       "route_confidence", "model_note", "refused",
                       "duration_ms", "question", "reply", "retrieved")
    fields = ("created_at", "bot", "route", "route_confidence", "model_note",
              "refused", "duration_ms", "question", "reply", "retrieved",
              "message")

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("message", "message__conversation", "feedback"))

    @admin.display(description="question", ordering="question")
    def short_question(self, obj):
        text = (obj.question or "").strip()
        return (text[:90] + "…") if len(text) > 90 else (text or "—")

    @admin.display(description="👍/👎")
    def thumb(self, obj):
        feedback = getattr(obj, "feedback", None)
        if feedback is None:
            return "—"
        return "👎" if feedback.rating == "down" else "👍"

    @admin.display(description="reply")
    def reply(self, obj):
        return format_html("<pre style='white-space:pre-wrap;max-width:60em'>{}</pre>",
                           obj.message.body)

    @admin.display(description="retrieved passages")
    def retrieved(self, obj):
        """Every cited chunk, in the order the model saw them, with its text."""
        ids = [cid for cid in (obj.chunk_ids or []) if isinstance(cid, int)]
        if not ids:
            return mark_safe("<em>Nothing was retrieved for this turn — the "
                             "answer did not come from the corpus.</em>")
        found = {chunk.pk: chunk for chunk in
                 DocumentChunk.objects.filter(pk__in=ids).select_related("document")}
        blocks = []
        for position, cid in enumerate(ids, start=1):
            chunk = found.get(cid)
            if chunk is None:
                # Re-ingested since the turn ran. Saying so is the finding.
                blocks.append((position, cid, "(missing)",
                               "This chunk no longer exists — the corpus has been "
                               "re-ingested since this answer was given."))
                continue
            title = chunk.document.title
            head = f"{title} — {chunk.heading}" if chunk.heading else title
            blocks.append((position, cid, head, chunk.text))
        return format_html_join(
            "",
            "<details open style='margin:0 0 .6em'>"
            "<summary><strong>[{}]</strong> chunk {} — {}</summary>"
            "<pre style='white-space:pre-wrap;max-width:60em;background:#f6f6f6;"
            "padding:.6em;border-radius:4px'>{}</pre></details>",
            blocks)

    def has_add_permission(self, request):
        return False


@admin.register(TurnFeedback)
class TurnFeedbackAdmin(admin.ModelAdmin):
    date_hierarchy = "updated_at"
    list_display = ("updated_at", "rating", "user", "bot", "route",
                    "short_note", "short_question")
    list_filter = ("rating", "turn__bot", "turn__route")
    search_fields = ("note", "turn__question")
    readonly_fields = ("turn", "user", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("turn", "user")

    @admin.display(description="bot", ordering="turn__bot")
    def bot(self, obj):
        return obj.turn.bot

    @admin.display(description="route", ordering="turn__route")
    def route(self, obj):
        return obj.turn.route or "—"

    @admin.display(description="what was wrong")
    def short_note(self, obj):
        text = (obj.note or "").strip()
        return (text[:80] + "…") if len(text) > 80 else (text or "—")

    @admin.display(description="question")
    def short_question(self, obj):
        text = (obj.turn.question or "").strip()
        return (text[:70] + "…") if len(text) > 70 else (text or "—")

    def has_add_permission(self, request):
        return False


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("role", "body", "sent_at")
    readonly_fields = ("role", "body", "sent_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "destination", "title", "user")
    list_filter = ("destination",)
    search_fields = ("title", "user__username")
    inlines = [ChatMessageInline]
    readonly_fields = ("user", "destination", "updated_at")

    def has_add_permission(self, request):
        return False
