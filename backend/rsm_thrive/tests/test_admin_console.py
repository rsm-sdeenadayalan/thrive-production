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


def test_core_models_are_registered():
    from django.contrib import admin as dj_admin
    from rsm_thrive.models import (Advisor, Appointment, Course, CourseRequest,
                                   Document, DocumentChunk, Enrollment, Event,
                                   JobPosting, ResourceLink, StudentProfile,
                                   Syllabus)
    for model in (Course, Enrollment, Syllabus, Document, DocumentChunk,
                  ResourceLink, Advisor, Appointment, Event, JobPosting,
                  StudentProfile, CourseRequest):
        assert dj_admin.site.is_registered(model), model


@pytest.mark.django_db
def test_admin_opens_changelist_plain_staff_blocked():
    from django.contrib.auth.models import Group
    from django.urls import reverse

    User = get_user_model()
    url = reverse("admin:rsm_thrive_course_changelist")

    admin_user = User.objects.create_user("adm2", is_staff=True)
    admin_user.groups.add(Group.objects.get(name="THRIVE Admin"))
    admin_client = _client()
    admin_client.force_login(admin_user)
    assert admin_client.get(url).status_code == 200

    plain = User.objects.create_user("plainstaff2", is_staff=True)
    plain_client = _client()
    plain_client.force_login(plain)
    assert plain_client.get(url).status_code == 403
