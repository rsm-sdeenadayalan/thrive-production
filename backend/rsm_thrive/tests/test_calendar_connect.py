import datetime as dt
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from rsm_thrive.models import AdvisorCalendarConnection
from rsm_thrive.services import graph
from rsm_thrive.testing import make_advisor, make_student

pytestmark = pytest.mark.django_db

GRAPH_ENV = {
    "MS_GRAPH_CLIENT_ID": "client-id",
    "MS_GRAPH_TENANT_ID": "tenant-id",
    "MS_GRAPH_CLIENT_SECRET": "client-secret",
    "MS_GRAPH_REDIRECT_URI": "http://localhost:8000/api/thrive/calendar/callback",
}


def _set_graph_env(monkeypatch):
    for key, value in GRAPH_ENV.items():
        monkeypatch.setenv(key, value)


def _make_staff(username="staffer"):
    return get_user_model().objects.create_user(
        username=username, email=f"{username}@ucsd.edu", is_staff=True)


def test_connect_requires_staff(client):
    make_student()  # non-staff logged-in user
    student = get_user_model().objects.get(username="ada")
    client.force_login(student)
    resp = client.get("/api/thrive/advisors/a1/calendar/connect")
    assert resp.status_code == 403


def test_connect_disabled_when_graph_not_configured(client, monkeypatch):
    for var in GRAPH_ENV:
        monkeypatch.delenv(var, raising=False)
    client.force_login(_make_staff())
    adv = make_advisor(id="a1")
    resp = client.get(f"/api/thrive/advisors/{adv.id}/calendar/connect")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "graph_disabled"


def test_connect_unknown_advisor_404(client, monkeypatch):
    _set_graph_env(monkeypatch)
    client.force_login(_make_staff())
    resp = client.get("/api/thrive/advisors/nope/calendar/connect")
    assert resp.status_code == 404


def test_connect_redirects_to_microsoft(client, monkeypatch):
    _set_graph_env(monkeypatch)
    client.force_login(_make_staff())
    adv = make_advisor(id="a1")
    with patch("rsm_thrive.services.graph.build_auth_url",
              return_value="https://login.microsoftonline.com/authorize?x=1"):
        resp = client.get(f"/api/thrive/advisors/{adv.id}/calendar/connect")
    assert resp.status_code == 302
    assert resp.url == "https://login.microsoftonline.com/authorize?x=1"


def test_callback_bad_state_400(client, monkeypatch):
    _set_graph_env(monkeypatch)
    client.force_login(_make_staff())
    resp = client.get("/api/thrive/calendar/callback", {"state": "garbage", "code": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_state"


def test_callback_exchange_failure_502(client, monkeypatch):
    _set_graph_env(monkeypatch)
    client.force_login(_make_staff())
    adv = make_advisor(id="a1")
    state = graph.sign_state(adv.id)
    with patch("rsm_thrive.services.graph.exchange_code",
              side_effect=graph.GraphError("boom")):
        resp = client.get("/api/thrive/calendar/callback", {"state": state, "code": "x"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "graph_exchange_failed"


def test_callback_success_upserts_connection_and_redirects(client, monkeypatch):
    _set_graph_env(monkeypatch)
    client.force_login(_make_staff())
    adv = make_advisor(id="a1")
    state = graph.sign_state(adv.id)
    tokens = {
        "access_token": "tok", "refresh_token": "ref",
        "expires_at": timezone.now() + dt.timedelta(hours=1),
        "account_email": "casey@ucsd.edu",
    }
    with patch("rsm_thrive.services.graph.exchange_code", return_value=tokens):
        resp = client.get("/api/thrive/calendar/callback", {"state": state, "code": "x"})
    assert resp.status_code == 302
    assert "connected=1" in resp.url
    conn = AdvisorCalendarConnection.objects.get(advisor=adv)
    assert conn.access_token == "tok"
    assert conn.account_email == "casey@ucsd.edu"

    # Reconnecting the same advisor upserts rather than duplicating.
    with patch("rsm_thrive.services.graph.exchange_code", return_value=tokens):
        client.get("/api/thrive/calendar/callback", {"state": state, "code": "y"})
    assert AdvisorCalendarConnection.objects.filter(advisor=adv).count() == 1
