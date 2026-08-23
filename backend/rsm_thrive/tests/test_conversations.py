import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_conversation, make_message, make_student

pytestmark = pytest.mark.django_db


def test_conversations_newest_first_with_messages(client):
    me = make_student()
    other = make_student(username="other")
    now = timezone.now()
    old = make_conversation(me, title="Old", updated_at=now - dt.timedelta(days=2))
    new = make_conversation(me, title="New", destination="courses", updated_at=now)
    make_message(old, role="student", body="hi", sent_at=now - dt.timedelta(days=2))
    make_message(old, role="thrive", body="hello", sent_at=now - dt.timedelta(days=2, hours=-1))
    make_conversation(other, title="Theirs")

    client.force_login(me.user)
    body = client.get("/api/thrive/conversations").json()
    assert [c["title"] for c in body] == ["New", "Old"]
    assert body[1]["destination"] == "resources"
    msgs = body[1]["messages"]
    assert [m["body"] for m in msgs] == ["hi", "hello"]  # sent_at asc
    assert msgs[0]["role"] == "student" and msgs[0]["id"].startswith("msg-")
    assert body[0]["messages"] == []


def test_single_conversation_and_404s(client):
    me = make_student()
    other = make_student(username="other")
    mine = make_conversation(me)
    theirs = make_conversation(other)
    client.force_login(me.user)

    ok = client.get(f"/api/thrive/conversations/conv-{mine.pk}").json()
    assert ok["id"] == f"conv-{mine.pk}"
    for bad in (f"conv-{theirs.pk}", "conv-99999", "banana", "conv-²"):
        resp = client.get(f"/api/thrive/conversations/{bad}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "unknown_conversation"
