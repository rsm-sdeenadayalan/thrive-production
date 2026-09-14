import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from django.core import signing
from django.utils import timezone

from rsm_thrive.services import graph
from rsm_thrive.testing import (
    make_advisor,
    make_calendar_connection,
    make_slot,
    make_student,
)

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


def test_graph_enabled_requires_all_three(monkeypatch):
    for var in GRAPH_ENV:
        monkeypatch.delenv(var, raising=False)
    assert graph.graph_enabled() is False
    monkeypatch.setenv("MS_GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("MS_GRAPH_TENANT_ID", "t")
    assert graph.graph_enabled() is False
    monkeypatch.setenv("MS_GRAPH_CLIENT_SECRET", "s")
    assert graph.graph_enabled() is True


def test_sign_and_verify_state_roundtrip():
    state = graph.sign_state("a1")
    assert graph.verify_state(state) == "a1"


def test_verify_state_rejects_tampered_value():
    state = graph.sign_state("a1")
    assert graph.verify_state(state + "x") is None


def test_verify_state_rejects_wrong_salt():
    state = signing.dumps("a1", salt="something-else")
    assert graph.verify_state(state) is None


def test_build_auth_url_delegates_to_msal(monkeypatch):
    _set_graph_env(monkeypatch)
    fake_app = MagicMock()
    fake_app.get_authorization_request_url.return_value = (
        "https://login.microsoftonline.com/authorize?x=1")
    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app):
        url = graph.build_auth_url("a1", "signed-state")
    assert url == "https://login.microsoftonline.com/authorize?x=1"
    _args, kwargs = fake_app.get_authorization_request_url.call_args
    assert kwargs["state"] == "signed-state"
    assert kwargs["redirect_uri"] == GRAPH_ENV["MS_GRAPH_REDIRECT_URI"]


def test_exchange_code_success(monkeypatch):
    _set_graph_env(monkeypatch)
    fake_app = MagicMock()
    fake_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "tok", "refresh_token": "ref", "expires_in": 3600,
    }
    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app), \
         patch("rsm_thrive.services.graph._account_email", return_value="casey@ucsd.edu"):
        result = graph.exchange_code("auth-code")
    assert result["access_token"] == "tok"
    assert result["refresh_token"] == "ref"
    assert result["account_email"] == "casey@ucsd.edu"
    assert result["expires_at"] > timezone.now()


def test_exchange_code_failure_raises_graph_error(monkeypatch):
    _set_graph_env(monkeypatch)
    fake_app = MagicMock()
    fake_app.acquire_token_by_authorization_code.return_value = {
        "error_description": "bad code",
    }
    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app), \
         pytest.raises(graph.GraphError, match="bad code"):
        graph.exchange_code("auth-code")


def test_refresh_updates_connection(monkeypatch):
    _set_graph_env(monkeypatch)
    conn = make_calendar_connection(make_advisor())
    fake_app = MagicMock()
    fake_app.acquire_token_by_refresh_token.return_value = {
        "access_token": "new-tok", "refresh_token": "new-ref", "expires_in": 3600,
    }
    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app):
        access_token = graph.refresh(conn)
    conn.refresh_from_db()
    assert access_token == "new-tok"
    assert conn.access_token == "new-tok"
    assert conn.refresh_token == "new-ref"
    assert conn.expires_at > timezone.now()


def test_refresh_failure_raises_graph_error(monkeypatch):
    _set_graph_env(monkeypatch)
    conn = make_calendar_connection(make_advisor())
    fake_app = MagicMock()
    fake_app.acquire_token_by_refresh_token.return_value = {
        "error_description": "refresh denied",
    }
    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app), \
         pytest.raises(graph.GraphError, match="refresh denied"):
        graph.refresh(conn)


def test_get_busy_periods_noops_when_graph_disabled_despite_stale_connection(monkeypatch):
    for var in GRAPH_ENV:
        monkeypatch.delenv(var, raising=False)
    advisor = make_advisor()
    make_calendar_connection(advisor)
    now = timezone.now()
    assert graph.get_busy_periods(advisor, now, now + dt.timedelta(days=1)) == []


def test_create_event_noops_when_graph_disabled_despite_stale_connection(monkeypatch):
    for var in GRAPH_ENV:
        monkeypatch.delenv(var, raising=False)
    me = make_student()
    advisor = make_advisor()
    make_calendar_connection(advisor)
    slot = make_slot(advisor)
    from rsm_thrive.models import Appointment
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    assert graph.create_event(advisor, appt) is None


def test_get_busy_periods_not_connected_returns_empty():
    advisor = make_advisor()
    now = timezone.now()
    assert graph.get_busy_periods(advisor, now, now + dt.timedelta(days=1)) == []


def test_get_busy_periods_filters_free_events(monkeypatch):
    _set_graph_env(monkeypatch)
    advisor = make_advisor()
    make_calendar_connection(advisor, expires_at=timezone.now() + dt.timedelta(hours=1))
    now = timezone.now()
    body = {"value": [
        {"start": {"dateTime": "2026-09-15T10:00:00"},
         "end": {"dateTime": "2026-09-15T10:30:00"}, "showAs": "busy"},
        {"start": {"dateTime": "2026-09-15T11:00:00"},
         "end": {"dateTime": "2026-09-15T11:30:00"}, "showAs": "free"},
    ]}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return body

    with patch("requests.get", return_value=FakeResponse()):
        periods = graph.get_busy_periods(advisor, now, now + dt.timedelta(days=1))
    assert len(periods) == 1
    assert periods[0][0].hour == 10


def test_get_busy_periods_http_failure_raises_graph_error(monkeypatch):
    import requests
    _set_graph_env(monkeypatch)
    advisor = make_advisor()
    make_calendar_connection(advisor, expires_at=timezone.now() + dt.timedelta(hours=1))
    now = timezone.now()
    with patch("requests.get", side_effect=requests.ConnectionError("down")), \
         pytest.raises(graph.GraphError):
        graph.get_busy_periods(advisor, now, now + dt.timedelta(days=1))


def test_create_event_not_connected_returns_none():
    me = make_student()
    slot = make_slot(make_advisor())
    from rsm_thrive.models import Appointment
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    assert graph.create_event(slot.advisor, appt) is None


def test_create_event_success(monkeypatch):
    _set_graph_env(monkeypatch)
    me = make_student()
    advisor = make_advisor()
    make_calendar_connection(advisor, expires_at=timezone.now() + dt.timedelta(hours=1))
    slot = make_slot(advisor)
    from rsm_thrive.models import Appointment
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "graph-event-1"}

    with patch("requests.post", return_value=FakeResponse()):
        event_id = graph.create_event(advisor, appt)
    assert event_id == "graph-event-1"


def test_create_event_http_failure_raises_graph_error(monkeypatch):
    import requests
    _set_graph_env(monkeypatch)
    me = make_student()
    advisor = make_advisor()
    make_calendar_connection(advisor, expires_at=timezone.now() + dt.timedelta(hours=1))
    slot = make_slot(advisor)
    from rsm_thrive.models import Appointment
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    with patch("requests.post", side_effect=requests.ConnectionError("down")), \
         pytest.raises(graph.GraphError):
        graph.create_event(advisor, appt)


def test_expired_token_triggers_refresh_before_use(monkeypatch):
    _set_graph_env(monkeypatch)
    advisor = make_advisor()
    make_calendar_connection(advisor, expires_at=timezone.now() - dt.timedelta(minutes=5))
    fake_app = MagicMock()
    fake_app.acquire_token_by_refresh_token.return_value = {
        "access_token": "refreshed-tok", "refresh_token": "r2", "expires_in": 3600,
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": []}

    with patch("rsm_thrive.services.graph._msal_app", return_value=fake_app), \
         patch("requests.get", return_value=FakeResponse()) as mocked_get:
        now = timezone.now()
        graph.get_busy_periods(advisor, now, now + dt.timedelta(days=1))
    headers = mocked_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer refreshed-tok"
