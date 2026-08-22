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

    client.delete("/api/thrive/events/evt-1/ignore")
    _put(client, "/api/thrive/tasks/asg:a1/note", {"note": "  "})  # empty deletes
    body = client.get("/api/thrive/overlay").json()
    assert body["ignoredEventIds"] == [] and body["taskNotes"] == {}
