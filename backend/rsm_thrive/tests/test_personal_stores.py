import json

import pytest
from django.utils import timezone

from rsm_thrive.models import (
    CalendarItemLabel, CalendarItemUrgent, CustomCalendarEvent, QuickListItem,
    TaskOverride,
)
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _put(client, path, body=None):
    return client.put(path, data=json.dumps(body if body is not None else {}),
                      content_type="application/json")


def test_label_and_urgent_roundtrip(client):
    me = make_student()
    client.force_login(me.user)
    key = "custom-custom-1712345678901-ab3"   # double-prefixed ids fit verbatim
    assert _put(client, f"/api/thrive/calendar-items/{key}/label",
                {"label": "  Study group  "}).status_code == 204
    assert CalendarItemLabel.objects.get(item_key=key).label == "Study group"
    assert _put(client, f"/api/thrive/calendar-items/{key}/label",
                {"label": "  "}).status_code == 204        # empty = delete
    assert not CalendarItemLabel.objects.exists()

    assert _put(client, f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert _put(client, f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert CalendarItemUrgent.objects.count() == 1          # idempotent
    assert client.delete(f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert not CalendarItemUrgent.objects.exists()


def test_custom_event_upsert_validation_and_cascade(client):
    me = make_student()
    client.force_login(me.user)
    good = {"title": "Study jam", "dayKey": "2026-09-01", "time": "18:30",
            "urgent": True, "createdAt": 1712345678901}
    assert _put(client, "/api/thrive/custom-events/custom-x1", good).status_code == 204
    good["title"] = "Study jam 2"
    assert _put(client, "/api/thrive/custom-events/custom-x1", good).status_code == 204
    row = CustomCalendarEvent.objects.get()
    assert row.title == "Study jam 2" and row.day_key == "2026-09-01"

    for bad in ({**good, "dayKey": "2026-9-1"}, {**good, "time": "6pm"},
                {**good, "title": " "}, {**good, "createdAt": "now"}):
        assert _put(client, "/api/thrive/custom-events/custom-x2", bad).status_code == 400

    # delete cascades the item-key-space annotations
    _put(client, "/api/thrive/calendar-items/custom-custom-x1/label", {"label": "L"})
    _put(client, "/api/thrive/calendar-items/custom-custom-x1/urgent")
    assert client.delete("/api/thrive/custom-events/custom-x1").status_code == 204
    assert not CustomCalendarEvent.objects.exists()
    assert not CalendarItemLabel.objects.exists()
    assert not CalendarItemUrgent.objects.exists()


def test_quick_item_upsert_and_delete(client):
    me = make_student()
    client.force_login(me.user)
    item = {"title": "Buy poster board", "done": False, "createdAt": 1712345678901,
            "copiedFrom": "asg:a1"}
    assert _put(client, "/api/thrive/quick-items/q-abc", item).status_code == 204
    item["done"] = True
    assert _put(client, "/api/thrive/quick-items/q-abc", item).status_code == 204
    assert QuickListItem.objects.get().done is True
    assert client.delete("/api/thrive/quick-items/q-abc").status_code == 204
    assert not QuickListItem.objects.exists()
    assert _put(client, "/api/thrive/quick-items/q-bad", {"title": "", "done": False,
                "createdAt": 1}).status_code == 400


def test_bulk_order(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    make_assignment(course, id="a2", due=timezone.now() + timezone.timedelta(days=2))
    client.force_login(me.user)

    resp = client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": 2, "asg:a2": 1,
                                                    "asg:ghost": 3}}),
                        content_type="application/json")
    assert resp.status_code == 204
    stored = {o.task_key: o.sort_order for o in TaskOverride.objects.all()}
    assert stored == {"asg:a1": 2, "asg:a2": 1}   # unknown key silently skipped

    resp = client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": None}}),
                        content_type="application/json")
    assert resp.status_code == 204
    assert "asg:a1" not in {o.task_key for o in TaskOverride.objects.all()}

    assert client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": True}}),
                        content_type="application/json").status_code == 400


def test_custom_event_null_optionals_treated_as_absent(client):
    me = make_student()
    client.force_login(me.user)
    good = {"title": "Study jam", "dayKey": "2026-09-01", "createdAt": 1712345678901}

    # time: null → treated as absent, stored as ""
    assert _put(client, "/api/thrive/custom-events/custom-null-time",
                {**good, "time": None}).status_code == 204
    row = CustomCalendarEvent.objects.get(key="custom-null-time")
    assert row.time == ""

    # time: non-string (e.g., 123) → 400
    assert _put(client, "/api/thrive/custom-events/custom-bad-time",
                {**good, "time": 123}).status_code == 400

    # label: null → treated as absent, stored as ""
    assert _put(client, "/api/thrive/custom-events/custom-null-label",
                {**good, "label": None}).status_code == 204
    row = CustomCalendarEvent.objects.get(key="custom-null-label")
    assert row.label == ""


def test_quick_item_null_optionals_treated_as_absent(client):
    me = make_student()
    client.force_login(me.user)
    item = {"title": "Buy poster board", "done": False, "createdAt": 1712345678901}

    # copiedFrom: null, note: null → treated as absent, stored as ""
    assert _put(client, "/api/thrive/quick-items/q-null-fields",
                {**item, "copiedFrom": None, "note": None, "dueDate": None}).status_code == 204
    row = QuickListItem.objects.get(key="q-null-fields")
    assert row.copied_from == ""
    assert row.note == ""
    assert row.due_date == ""
