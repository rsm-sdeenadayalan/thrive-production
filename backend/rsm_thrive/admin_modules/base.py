"""Shared base for THRIVE Console model admins."""

from django.contrib import admin

from .access import AdminOnly, is_thrive_faculty


class ConsoleModelAdmin(AdminOnly, admin.ModelAdmin):
    """Default console admin: admin-only access, sensible list ergonomics."""

    save_on_top = True
    list_per_page = 50


class FacultyReadableConsoleAdmin(ConsoleModelAdmin):
    """Faculty may view; only admins may add/change/delete.

    For reference records faculty legitimately need to see (the curriculum),
    without letting them edit it.
    """

    def has_module_permission(self, request):
        return is_thrive_faculty(request.user)

    def has_view_permission(self, request, obj=None):
        return is_thrive_faculty(request.user)


class ReadOnlyConsoleAdmin(ConsoleModelAdmin):
    """View-only console admin, for records edited through another path
    (e.g. corpus chunks, which are rebuilt by re-ingest, not hand-edited)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow opening the detail page (view) but not saving.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return self._ok(request)
