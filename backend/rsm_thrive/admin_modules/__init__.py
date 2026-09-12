"""THRIVE Console — the admin/faculty backend UI.

Registered on the DEFAULT admin site so the existing trace admin
(`rsm_thrive/admin.py`) and these modules live in one place. `admin.py`
imports this package, and Django's admin autodiscovery loads `admin.py`
for the app — so importing this here is enough to register everything.

Submodules are added to the import list below as each is built; every
submodule registers its own models/views on import.
"""

from django.contrib import admin

admin.site.site_header = "THRIVE Console"
admin.site.site_title = "THRIVE Console"
admin.site.index_title = "Program administration"

# Access groups the console recognizes. Login (THRIVE_AUTH=ucsd_ldap) maps a
# user into one of these; is_superuser stays the maintainer override.
ADMIN_GROUP = "THRIVE Admin"
FACULTY_GROUP = "THRIVE Faculty"

# Submodules register on import; each registers its own models/views.
from . import (academic, careers, content, knowledge, operations,  # noqa: E402,F401
               oversight, people, scheduling)


def _register_remaining_models():
    """Completeness guarantee: any rsm_thrive model a submodule didn't register
    explicitly still gets a console admin, so the backend covers the WHOLE
    system (and any model added later) with no silent gaps."""
    from django.apps import apps as _apps
    from django.contrib.admin.sites import AlreadyRegistered

    from .base import ConsoleModelAdmin

    for model in _apps.get_app_config("rsm_thrive").get_models():
        if admin.site.is_registered(model):
            continue
        try:
            admin.site.register(model, ConsoleModelAdmin)
        except AlreadyRegistered:
            pass


_register_remaining_models()
