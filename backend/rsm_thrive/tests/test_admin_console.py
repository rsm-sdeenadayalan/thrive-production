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
