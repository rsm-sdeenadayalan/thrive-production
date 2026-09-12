"""Console admins: student profiles, course requests, and the task overlay.

Student records carry PII, so these stay admin-only (via ConsoleModelAdmin).
Faculty scoping for specific surfaces (e.g. answer review) is handled in its
own module, not here.
"""

from django.contrib import admin

from rsm_thrive.models import (CalendarPrefs, CourseRequest, CustomCalendarEvent,
                               QuickListItem, SharedTask, StudentProfile,
                               StudentTask, TaskNote, TaskOverride)

from .base import ConsoleModelAdmin


@admin.register(StudentProfile)
class StudentProfileAdmin(ConsoleModelAdmin):
    list_display = ("user", "display_name", "program", "track", "current_term",
                    "standing")
    list_filter = ("program", "track")
    search_fields = ("user__username", "display_name")


@admin.register(CourseRequest)
class CourseRequestAdmin(ConsoleModelAdmin):
    list_display = ("user", "type", "course", "status", "created_at")
    list_filter = ("type", "status")
    search_fields = ("user__username", "course")
    date_hierarchy = "created_at"


@admin.register(SharedTask)
class SharedTaskAdmin(ConsoleModelAdmin):
    list_display = ("title", "source", "priority", "due_date", "active", "course")
    list_filter = ("source", "priority", "active")
    search_fields = ("title",)


@admin.register(StudentTask)
class StudentTaskAdmin(ConsoleModelAdmin):
    list_display = ("title", "user", "source", "priority", "due_date")
    list_filter = ("source", "priority")
    search_fields = ("title", "user__username")


@admin.register(TaskOverride)
class TaskOverrideAdmin(ConsoleModelAdmin):
    list_display = ("user", "task_key", "done", "priority", "due_date")
    search_fields = ("user__username", "task_key")


@admin.register(TaskNote)
class TaskNoteAdmin(ConsoleModelAdmin):
    list_display = ("user", "task_key")
    search_fields = ("user__username", "task_key", "note")


@admin.register(QuickListItem)
class QuickListItemAdmin(ConsoleModelAdmin):
    list_display = ("title", "user", "done", "due_date")
    list_filter = ("done",)
    search_fields = ("title", "user__username")


@admin.register(CustomCalendarEvent)
class CustomCalendarEventAdmin(ConsoleModelAdmin):
    list_display = ("title", "user", "day_key", "time", "urgent")
    list_filter = ("urgent",)
    search_fields = ("title", "user__username")


@admin.register(CalendarPrefs)
class CalendarPrefsAdmin(ConsoleModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username",)
