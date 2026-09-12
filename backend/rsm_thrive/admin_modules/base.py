"""Shared base for THRIVE Console model admins."""

from django.contrib import admin

from .access import AdminOnly


class ConsoleModelAdmin(AdminOnly, admin.ModelAdmin):
    """Default console admin: admin-only access, sensible list ergonomics."""

    save_on_top = True
    list_per_page = 50


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
