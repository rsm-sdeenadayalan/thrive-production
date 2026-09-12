"""Role checks for the THRIVE Console.

Two console roles, plus the maintainer superuser:

- THRIVE Admin   — full console access.
- THRIVE Faculty — scoped access (their course content, answer review,
  read-only oversight). Admins are a superset of faculty for read access.

Login (THRIVE_AUTH=ucsd_ldap) maps a user into a group; is_superuser is the
maintainer override. The groups themselves are created by a data migration so
they exist on every deployment.
"""

from . import ADMIN_GROUP, FACULTY_GROUP


def is_thrive_admin(user) -> bool:
    """A staff administrator with full console access."""
    if not (user and user.is_active and user.is_authenticated):
        return False
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()


def is_thrive_faculty(user) -> bool:
    """Faculty, or an admin (admins can do everything faculty can)."""
    if not (user and user.is_active and user.is_authenticated):
        return False
    return is_thrive_admin(user) or user.groups.filter(name=FACULTY_GROUP).exists()


class AdminOnly:
    """Mixin for ModelAdmins only THRIVE Admins may use.

    Gates every admin permission behind `is_thrive_admin`, so a faculty user or
    a plain staff account cannot see or change the model even if Django-level
    permissions were granted by accident.
    """

    def _ok(self, request):
        return is_thrive_admin(request.user)

    def has_module_permission(self, request):
        return self._ok(request)

    def has_view_permission(self, request, obj=None):
        return self._ok(request)

    def has_add_permission(self, request):
        return self._ok(request)

    def has_change_permission(self, request, obj=None):
        return self._ok(request)

    def has_delete_permission(self, request, obj=None):
        return self._ok(request)
