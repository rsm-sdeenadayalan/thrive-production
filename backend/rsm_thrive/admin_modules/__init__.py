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
from . import (academic, careers, content, knowledge, oversight,  # noqa: E402,F401
               people, scheduling)
