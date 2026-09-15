"""Create the two THRIVE Console access groups.

Net-new roles the console introduces. Assigned by a superuser today (or a
future LDAP mapping). Permissions are attached by the console modules, not
here; this only guarantees the groups exist on every deployment.
"""

from django.db import migrations

ADMIN_GROUP = "THRIVE Admin"
FACULTY_GROUP = "THRIVE Faculty"


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in (ADMIN_GROUP, FACULTY_GROUP):
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=[ADMIN_GROUP, FACULTY_GROUP]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rsm_thrive", "0027_plannersession_asked"),
        ("auth", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
