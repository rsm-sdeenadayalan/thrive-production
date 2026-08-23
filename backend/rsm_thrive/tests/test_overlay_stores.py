import json

import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_custom_event, make_quick_item,
    make_student, set_override,
)

pytestmark = pytest.mark.django_db


def test_overlay_stores_mirror_localstorage_shapes(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    set_override(me, "asg:a1", done=False, title="Renamed", order=3)
    client.force_login(me.user)

    # server-side personal rows
    client.post("/api/thrive/tasks",
                data=json.dumps({"title": "Mine", "dueDate": "2026-09-01T12:00:00-07:00",
                                 "clientKey": "task-add-1"}),
                content_type="application/json")
    client.put("/api/thrive/events/evt-1/ignore")
    client.put("/api/thrive/events/evt-2/join")
    client.put("/api/thrive/calendar-items/apt-3/label",
               data=json.dumps({"label": "Coffee chat"}),
               content_type="application/json")
    client.put("/api/thrive/calendar-items/apt-3/urgent")
    make_custom_event(me, "custom-x1", urgent=True)
    make_quick_item(me, "q-abc", note="call mom")
    client.put("/api/thrive/tasks/asg:a1/note",
               data=json.dumps({"note": "ask prof"}), content_type="application/json")
    client.put("/api/thrive/calendar-prefs",
               data=json.dumps({"view": "week"}), content_type="application/json")

    stores = client.get("/api/thrive/overlay").json()["stores"]
    assert stores["thrive:task-done"] == {"asg:a1": False}
    assert stores["thrive:task-titles"] == {"asg:a1": "Renamed"}
    assert stores["thrive:task-order"] == {"asg:a1": 3}
    assert stores["thrive:task-priority"] == {} and stores["thrive:task-due"] == {}
    added = stores["thrive:task-added"]["task-add-1"]
    assert added["id"] == "task-add-1" and added["done"] is False
    assert added["subtasks"] == [] and added["source"] == "admin"
    assert stores["thrive:ignored-events"] == {"evt-1": True}
    assert stores["thrive:event-joins"] == {"evt-2": True}
    assert stores["thrive:item-labels"] == {"apt-3": "Coffee chat"}
    assert stores["thrive:item-urgent"] == {"apt-3": True}
    custom = stores["thrive:custom-events"]["custom-x1"]
    assert custom == {"id": "custom-x1", "title": "Custom thing",
                      "dayKey": "2026-09-01", "time": "18:00",
                      "urgent": True, "createdAt": 1712000000000}
    quick = stores["thrive:quicklist"]["q-abc"]
    assert quick == {"id": "q-abc", "title": "Scratch item", "done": False,
                     "createdAt": 1712000000000, "note": "call mom"}
    assert stores["thrive:task-notes"] == {"asg:a1": "ask prof"}
    assert stores["thrive:calendar-prefs"] == {"value": {"view": "week"}}


def test_overlay_stores_empty_world(client):
    me = make_student()
    client.force_login(me.user)
    stores = client.get("/api/thrive/overlay").json()["stores"]
    assert stores["thrive:task-done"] == {}
    assert stores["thrive:calendar-prefs"] == {}
    assert stores["thrive:custom-events"] == {}
