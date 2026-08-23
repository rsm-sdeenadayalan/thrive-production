import pytest
from django.test import override_settings

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db
LOGIN = "/api/thrive/dev-login"


def _student_with_password(username="ada", password="pw"):
    profile = make_student(username=username)
    profile.user.set_password(password)
    profile.user.save()
    return profile


def test_login_roundtrip_relative_next(client):
    _student_with_password()
    page = client.get(f"{LOGIN}?next=/after")
    assert page.status_code == 200 and b"<form" in page.content

    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": "/after"})
    assert resp.status_code == 302 and resp["Location"] == "/after"
    assert client.get("/api/thrive/me").status_code == 200  # session established


def test_login_allows_frontend_origin_and_blocks_others(client):
    _student_with_password()
    good = "http://localhost:5173/calendar"
    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": good})
    assert resp["Location"] == good

    client.logout()
    evil = "https://evil.example/phish"
    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": evil})
    assert resp["Location"] == "/"


def test_bad_credentials_reshow_form(client):
    _student_with_password()
    resp = client.post(LOGIN, {"username": "ada", "password": "nope", "next": "/"})
    assert resp.status_code == 200 and b"Wrong username or password" in resp.content


@override_settings(THRIVE_DEV_LOGIN_ENABLED=False)
def test_disabled_login_404s(client):
    assert client.get(LOGIN).status_code == 404


def test_me_sets_csrf_cookie(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/me")
    assert "csrftoken" in resp.cookies
