"""Answer review — the faculty-facing oversight surface.

Faculty (and admins) browse the assistant's course-related turns and record a
correction when the bot says something wrong about a course. Corrections are
stored per turn with their author; wiring a correction back into retrieval/
answers is a later step — capturing it accurately is this one.

The admin.py trace tool remains the deep, admin-only "why did it say that"
surface (retrieved passages inline). This is the lighter, faculty-usable view.
"""

from django.conf import settings
from django.contrib import admin
from django.db import models

from rsm_thrive.models import ChatTurnLog

from .access import FacultyOrAdmin, is_thrive_admin, is_thrive_faculty


class AnswerCorrection(models.Model):
    """A faculty note that an assistant turn was wrong, and what's correct."""

    turn = models.ForeignKey(ChatTurnLog, on_delete=models.CASCADE,
                             related_name="corrections")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="+")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "rsm_thrive"
        ordering = ("-created_at",)

    def __str__(self):
        return f"correction on turn {self.turn_id}"


class AnswerReview(ChatTurnLog):
    """Proxy of ChatTurnLog presenting a faculty-facing review surface."""

    class Meta:
        proxy = True
        app_label = "rsm_thrive"
        verbose_name = "answer review"
        verbose_name_plural = "Answer review"


class AnswerCorrectionInline(admin.TabularInline):
    model = AnswerCorrection
    extra = 1
    fields = ("note", "author", "created_at")
    readonly_fields = ("author", "created_at")

    def has_view_permission(self, request, obj=None):
        return is_thrive_faculty(request.user)

    def has_add_permission(self, request, obj=None):
        return is_thrive_faculty(request.user)

    def has_change_permission(self, request, obj=None):
        return is_thrive_faculty(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_thrive_admin(request.user)


@admin.register(AnswerReview)
class AnswerReviewAdmin(FacultyOrAdmin, admin.ModelAdmin):
    list_display = ("created_at", "bot", "route", "refused", "short_question")
    list_filter = ("bot", "route", "refused")
    search_fields = ("question",)
    date_hierarchy = "created_at"
    inlines = [AnswerCorrectionInline]
    readonly_fields = ("created_at", "bot", "route", "route_confidence",
                       "model_note", "refused", "duration_ms", "question",
                       "message")
    fields = readonly_fields

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("message", "message__conversation"))

    @admin.display(description="question", ordering="question")
    def short_question(self, obj):
        text = (obj.question or "").strip()
        return (text[:90] + "…") if len(text) > 90 else (text or "—")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, AnswerCorrection) and obj.author_id is None:
                obj.author = request.user
            obj.save()
        for obj in getattr(formset, "deleted_objects", []):
            obj.delete()
        formset.save_m2m()
