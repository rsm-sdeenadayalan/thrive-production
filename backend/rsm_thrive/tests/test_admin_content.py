"""Tests for the console's content-management tool (catalog editor + re-ingest)."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse


def _admin_client():
    User = get_user_model()
    user = User.objects.create_user("content-admin", is_staff=True)
    user.groups.add(Group.objects.get(name="THRIVE Admin"))
    client = Client()
    client.force_login(user)
    return client


def _plain_staff_client():
    User = get_user_model()
    user = User.objects.create_user("content-plain", is_staff=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_hub_visible_to_admin_blocked_for_plain_staff():
    url = reverse("admin:rsm_thrive_contenttool_changelist")
    admin_resp = _admin_client().get(url)
    assert admin_resp.status_code == 200
    assert b"Content management" in admin_resp.content
    assert _plain_staff_client().get(url).status_code == 403


@pytest.mark.django_db
def test_catalog_edit_saves_valid_json(tmp_path, monkeypatch):
    from rsm_thrive.admin_modules import content
    monkeypatch.setattr(content, "CATALOG_DIR", tmp_path)
    (tmp_path / "courses.json").write_text("[]", encoding="utf-8")

    url = reverse("admin:content_catalog_edit", args=["courses.json"])
    resp = _admin_client().post(url, {"content": '[{"id": "MGTA 999"}]'})
    assert resp.status_code == 302  # redirect back to hub on success
    saved = json.loads((tmp_path / "courses.json").read_text(encoding="utf-8"))
    assert saved == [{"id": "MGTA 999"}]


@pytest.mark.django_db
def test_catalog_edit_rejects_invalid_json(tmp_path, monkeypatch):
    from rsm_thrive.admin_modules import content
    monkeypatch.setattr(content, "CATALOG_DIR", tmp_path)
    (tmp_path / "courses.json").write_text("[]", encoding="utf-8")

    url = reverse("admin:content_catalog_edit", args=["courses.json"])
    resp = _admin_client().post(url, {"content": "{ not json"})
    assert resp.status_code == 200  # re-renders the form with an error
    # File is untouched.
    assert (tmp_path / "courses.json").read_text(encoding="utf-8") == "[]"


@pytest.mark.django_db
def test_catalog_edit_unknown_file_404():
    url = reverse("admin:content_catalog_edit", args=["secrets.json"])
    assert _admin_client().get(url).status_code == 404


@pytest.mark.django_db
def test_corpus_reingest_invokes_command(tmp_path, monkeypatch):
    from rsm_thrive.admin_modules import content
    monkeypatch.setattr(content, "CORPUS_DIR", tmp_path)
    (tmp_path / "syllabi").mkdir()

    calls = []
    monkeypatch.setattr(content, "call_command",
                        lambda *a, **k: calls.append((a, k)))

    url = reverse("admin:content_corpus_reingest")
    resp = _admin_client().post(url, {"directory": "syllabi"})
    assert resp.status_code == 302
    assert len(calls) == 1
    args, _ = calls[0]
    assert args[0] == "ingest_corpus"
    assert str(args[1]).endswith("syllabi")


@pytest.mark.django_db
def test_corpus_reingest_rejects_unknown_directory(tmp_path, monkeypatch):
    from rsm_thrive.admin_modules import content
    monkeypatch.setattr(content, "CORPUS_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(content, "call_command",
                        lambda *a, **k: calls.append((a, k)))

    url = reverse("admin:content_corpus_reingest")
    resp = _admin_client().post(url, {"directory": "../etc"})
    assert resp.status_code == 302
    assert calls == []  # nothing ran


@pytest.mark.django_db
def test_content_pages_block_plain_staff(tmp_path, monkeypatch):
    from rsm_thrive.admin_modules import content
    monkeypatch.setattr(content, "CATALOG_DIR", tmp_path)
    (tmp_path / "courses.json").write_text("[]", encoding="utf-8")
    edit = reverse("admin:content_catalog_edit", args=["courses.json"])
    reingest = reverse("admin:content_corpus_reingest")
    client = _plain_staff_client()
    assert client.get(edit).status_code == 403
    assert client.post(reingest, {"directory": "syllabi"}).status_code == 403
