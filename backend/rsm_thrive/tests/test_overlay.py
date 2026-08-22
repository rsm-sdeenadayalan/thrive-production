import json

import pytest

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _put(client, path, body=None):
    return client.put(path, data=json.dumps(body or {}),
                      content_type="application/json")


def test_overlay_roundtrip(client):
    profile = make_student()
    client.force_login(profile.user)

    assert _put(client, "/api/thrive/events/evt-1/ignore").status_code == 204
    assert _put(client, "/api/thrive/events/evt-1/ignore").status_code == 204  # idempotent
    assert _put(client, "/api/thrive/events/evt-2/join").status_code == 204
    assert _put(client, "/api/thrive/calendar-prefs",
                {"view": "week", "filters": ["rady"]}).status_code == 204
    assert _put(client, "/api/thrive/tasks/asg:a1/note",
                {"note": "ask about rubric"}).status_code == 204

    body = client.get("/api/thrive/overlay").json()
    assert body == {
        "ignoredEventIds": ["evt-1"],
        "joinedEventIds": ["evt-2"],
        "calendarPrefs": {"view": "week", "filters": ["rady"]},
        "taskNotes": {"asg:a1": "ask about rubric"},
    }

    # Delete ignore (idempotent)
    assert client.delete("/api/thrive/events/evt-1/ignore").status_code == 204
    assert client.delete("/api/thrive/events/evt-1/ignore").status_code == 204  # idempotent again

    # Delete join and verify it's gone
    assert client.delete("/api/thrive/events/evt-2/join").status_code == 204

    # Delete task note via whitespace-only
    _put(client, "/api/thrive/tasks/asg:a1/note", {"note": "  "})  # empty deletes
    body = client.get("/api/thrive/overlay").json()
    assert body["ignoredEventIds"] == [] and body["taskNotes"] == {} and body["joinedEventIds"] == []


def test_overlay_unauthenticated(client):
    resp = client.get("/api/thrive/overlay")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


def test_overlay_post_method_not_allowed(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.post("/api/thrive/overlay", data="{}", content_type="application/json")
    assert resp.status_code == 405


def test_calendar_prefs_body_too_large(client):
    profile = make_student()
    client.force_login(profile.user)

    large_body = {"pad": "x" * 9000}
    resp = client.put("/api/thrive/calendar-prefs",
                      data=json.dumps(large_body),
                      content_type="application/json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "too_large"


def test_calendar_prefs_malformed_json(client):
    profile = make_student()
    client.force_login(profile.user)

    resp = client.put("/api/thrive/calendar-prefs",
                      data="not json",
                      content_type="application/json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"
