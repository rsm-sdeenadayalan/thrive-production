"""Completeness + operations tests for the THRIVE Console."""

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse


def _admin_client(username="ops-admin"):
    user = get_user_model().objects.create_user(username, is_staff=True)
    user.groups.add(Group.objects.get(name="THRIVE Admin"))
    c = Client()
    c.force_login(user)
    return c


def _plain_client(username="ops-plain"):
    user = get_user_model().objects.create_user(username, is_staff=True)
    c = Client()
    c.force_login(user)
    return c


def test_every_app_model_is_registered():
    """The backend must cover the whole system — no unmanaged gaps."""
    missing = [m.__name__ for m in apps.get_app_config("rsm_thrive").get_models()
               if not admin.site.is_registered(m)]
    assert missing == [], f"models with no console admin: {missing}"


@pytest.mark.django_db
def test_operations_hub_gated():
    url = reverse("admin:rsm_thrive_operation_changelist")
    assert _admin_client("ops-a1").get(url).status_code == 200
    assert _plain_client("ops-p1").get(url).status_code == 403


@pytest.mark.django_db
def test_operations_run_whitelisted_command(monkeypatch):
    from rsm_thrive.admin_modules import operations

    calls = []
    monkeypatch.setattr(operations, "call_command",
                        lambda *a, **k: calls.append((a, k)))
    url = reverse("admin:operation_run")
    resp = _admin_client("ops-a2").post(url, {"command": "build_catalog"})
    assert resp.status_code == 302
    assert len(calls) == 1 and calls[0][0][0] == "build_catalog"


@pytest.mark.django_db
def test_operations_run_rejects_unknown_command(monkeypatch):
    from rsm_thrive.admin_modules import operations

    calls = []
    monkeypatch.setattr(operations, "call_command",
                        lambda *a, **k: calls.append((a, k)))
    url = reverse("admin:operation_run")
    resp = _admin_client("ops-a3").post(url, {"command": "rm_minus_rf"})
    assert resp.status_code == 302
    assert calls == []  # not whitelisted, nothing ran


@pytest.mark.django_db
def test_operations_run_blocked_for_plain_staff(monkeypatch):
    from rsm_thrive.admin_modules import operations

    calls = []
    monkeypatch.setattr(operations, "call_command",
                        lambda *a, **k: calls.append((a, k)))
    url = reverse("admin:operation_run")
    resp = _plain_client("ops-p2").post(url, {"command": "build_catalog"})
    assert resp.status_code == 403
    assert calls == []
