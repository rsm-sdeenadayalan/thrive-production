"""Foundation tests for the THRIVE Console (Django admin backend UI)."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model


def test_console_branding_is_set():
    assert admin.site.site_header == "THRIVE Console"
    assert admin.site.site_title == "THRIVE Console"
    assert admin.site.index_title == "Program administration"


@pytest.mark.django_db
def test_admin_index_loads_for_staff():
    User = get_user_model()
    staff = User.objects.create_user(
        username="console-staff", password="x", is_staff=True, is_superuser=True)
    client = _client()
    client.force_login(staff)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"THRIVE Console" in resp.content


@pytest.mark.django_db
def test_admin_index_denies_anonymous():
    resp = _client().get("/admin/")
    # Admin redirects anonymous users to its login page.
    assert resp.status_code in (301, 302)
    assert "/admin/login" in resp.headers.get("Location", "")


def _client():
    from django.test import Client
    return Client()


@pytest.mark.django_db
def test_console_groups_exist():
    from django.contrib.auth.models import Group
    assert Group.objects.filter(name="THRIVE Admin").exists()
    assert Group.objects.filter(name="THRIVE Faculty").exists()


@pytest.mark.django_db
def test_role_helpers_distinguish_admin_faculty_plain():
    from django.contrib.auth.models import Group
    from rsm_thrive.admin_modules.access import is_thrive_admin, is_thrive_faculty

    User = get_user_model()
    admin_group = Group.objects.get(name="THRIVE Admin")
    faculty_group = Group.objects.get(name="THRIVE Faculty")

    superuser = User.objects.create_user("su", is_superuser=True, is_staff=True)
    admin_user = User.objects.create_user("admin1", is_staff=True)
    admin_user.groups.add(admin_group)
    faculty_user = User.objects.create_user("faculty1", is_staff=True)
    faculty_user.groups.add(faculty_group)
    plain = User.objects.create_user("plain1", is_staff=True)

    # Admin role: superuser and Admin-group members only.
    assert is_thrive_admin(superuser)
    assert is_thrive_admin(admin_user)
    assert not is_thrive_admin(faculty_user)
    assert not is_thrive_admin(plain)

    # Faculty role is a superset: admins count as faculty for read access.
    assert is_thrive_faculty(superuser)
    assert is_thrive_faculty(admin_user)
    assert is_thrive_faculty(faculty_user)
    assert not is_thrive_faculty(plain)
