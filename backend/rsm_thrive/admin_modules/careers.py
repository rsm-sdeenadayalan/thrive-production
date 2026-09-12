"""Console admins: jobs, match reports, resume records, and skills."""

from django.contrib import admin

from rsm_thrive.models import (JobPosting, MatchReport, PostingInteraction,
                               ResumeCourseHighlight, ResumeVersion, Skill)

from .base import ConsoleModelAdmin


@admin.register(JobPosting)
class JobPostingAdmin(ConsoleModelAdmin):
    list_display = ("title", "company", "location", "source", "active", "posted_at")
    list_filter = ("active", "source")
    search_fields = ("title", "company", "location")
    date_hierarchy = "posted_at"
    exclude = ("embedding",)


@admin.register(MatchReport)
class MatchReportAdmin(ConsoleModelAdmin):
    list_display = ("user", "posting", "score", "verdict", "created_at")
    list_filter = ("verdict",)
    search_fields = ("user__username", "posting__title")


@admin.register(PostingInteraction)
class PostingInteractionAdmin(ConsoleModelAdmin):
    list_display = ("user", "posting", "liked", "dismissed", "updated_at")
    list_filter = ("liked", "dismissed")
    search_fields = ("user__username", "posting__title")


@admin.register(Skill)
class SkillAdmin(ConsoleModelAdmin):
    list_display = ("name", "user", "source", "course")
    list_filter = ("source",)
    search_fields = ("name", "user__username")


@admin.register(ResumeCourseHighlight)
class ResumeCourseHighlightAdmin(ConsoleModelAdmin):
    list_display = ("code", "title")
    search_fields = ("code", "title")


@admin.register(ResumeVersion)
class ResumeVersionAdmin(ConsoleModelAdmin):
    list_display = ("user", "label", "is_current")
    list_filter = ("is_current",)
    search_fields = ("user__username", "label")
