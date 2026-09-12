"""Console admins: courses, syllabi, degree, and planner records."""

from django.contrib import admin

from rsm_thrive.models import (Assignment, Course, CourseMeeting, CoursePlan,
                               DegreeGap, DegreeRequirement, Enrollment,
                               PlannerSession, ProgramPhaseRow, StudentAssignment,
                               Syllabus)

from .base import ConsoleModelAdmin, FacultyReadableConsoleAdmin


class CourseMeetingInline(admin.TabularInline):
    model = CourseMeeting
    extra = 0


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0


@admin.register(Course)
class CourseAdmin(FacultyReadableConsoleAdmin):
    list_display = ("code", "title", "instructor", "term", "units")
    list_filter = ("term",)
    search_fields = ("code", "title", "instructor")
    inlines = [CourseMeetingInline, AssignmentInline]


@admin.register(Syllabus)
class SyllabusAdmin(FacultyReadableConsoleAdmin):
    list_display = ("course", "last_updated", "source_url")
    search_fields = ("course__code", "course__title")


@admin.register(Assignment)
class AssignmentAdmin(ConsoleModelAdmin):
    list_display = ("title", "course", "due_date", "weight")
    search_fields = ("title", "course__code")


@admin.register(Enrollment)
class EnrollmentAdmin(ConsoleModelAdmin):
    list_display = ("user", "course", "bucket", "progress", "standing",
                    "current_grade", "completed")
    list_filter = ("bucket", "completed", "standing")
    search_fields = ("user__username", "course__code", "course__title")


@admin.register(StudentAssignment)
class StudentAssignmentAdmin(ConsoleModelAdmin):
    list_display = ("user", "assignment", "status", "grade")
    list_filter = ("status",)
    search_fields = ("user__username", "assignment__title")


@admin.register(ProgramPhaseRow)
class ProgramPhaseRowAdmin(ConsoleModelAdmin):
    list_display = ("track", "phase_id", "label", "term", "start", "end", "optional")
    list_filter = ("track", "optional")
    search_fields = ("label", "phase_id")


@admin.register(DegreeRequirement)
class DegreeRequirementAdmin(ConsoleModelAdmin):
    list_display = ("track", "units_required", "core_required", "elective_required")


@admin.register(DegreeGap)
class DegreeGapAdmin(ConsoleModelAdmin):
    list_display = ("user", "label", "severity")
    list_filter = ("severity",)
    search_fields = ("user__username", "label")


@admin.register(CoursePlan)
class CoursePlanAdmin(ConsoleModelAdmin):
    list_display = ("user", "track")
    search_fields = ("user__username",)


@admin.register(PlannerSession)
class PlannerSessionAdmin(ConsoleModelAdmin):
    list_display = ("conversation", "updated_at")
