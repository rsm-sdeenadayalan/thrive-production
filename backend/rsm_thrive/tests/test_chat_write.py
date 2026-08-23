import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import ChatMessage, ChatTurnLog, Conversation
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.views import chat as chat_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(replies):
        fake = FakeLLM(replies=replies)
        monkeypatch.setattr(chat_views, "llm_factory", lambda: fake)
        return fake
    return _install


def _post(client, path, body):
    return client.post(path, json.dumps(body), content_type="application/json")


class TestCreateConversation:
    def test_creates_two_turns_and_returns_payload(self, client, student, fake_llm):
        fake_llm(["Keep it to one page."])
        response = _post(client, "/api/thrive/conversations",
                         {"destination": "career", "body": "resume length?"})
        assert response.status_code == 201
        payload = response.json()
        assert payload["id"].startswith("conv-")
        assert payload["destination"] == "career"
        assert payload["title"] == "resume length?"
        roles = [m["role"] for m in payload["messages"]]
        assert roles == ["student", "thrive"]
        assert payload["messages"][1]["body"] == "Keep it to one page."

    def test_title_truncates_to_60(self, client, student, fake_llm):
        fake_llm(["ok"])
        long_body = "x" * 200
        response = _post(client, "/api/thrive/conversations",
                         {"destination": "career", "body": long_body})
        assert len(response.json()["title"]) == 60

    def test_bad_destination_and_bad_body_are_400(self, client, student):
        for body in ({"destination": "banana", "body": "hi"},
                     {"destination": "career", "body": ""},
                     {"destination": "career", "body": "y" * 4001},
                     {"destination": "career"}):
            response = _post(client, "/api/thrive/conversations", body)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "bad_request"
        assert Conversation.objects.count() == 0

    def test_turn_log_written(self, client, student, fake_llm):
        fake_llm(["answer"])
        _post(client, "/api/thrive/conversations",
              {"destination": "career", "body": "q"})
        log = ChatTurnLog.objects.get()
        assert log.bot == "career"
        assert log.message.role == "thrive"


class TestSendMessage:
    def _conversation(self, user, destination="career"):
        conv = Conversation.objects.create(user=user, destination=destination,
                                           title="t")
        ChatMessage.objects.create(conversation=conv, role="student", body="earlier q")
        ChatMessage.objects.create(conversation=conv, role="thrive", body="earlier a")
        return conv

    def test_appends_and_returns_payload(self, client, student, fake_llm):
        conv = self._conversation(student)
        fake = fake_llm(["follow-up answer"])
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "and a follow-up?"})
        assert response.status_code == 200
        assert [m["role"] for m in response.json()["messages"]] == \
               ["student", "thrive", "student", "thrive"]
        # history reached the bot mapped to user/assistant, question separate
        _, messages, _ = fake.calls[0]
        assert {"role": "user", "content": "earlier q"} in messages
        assert {"role": "assistant", "content": "earlier a"} in messages
        assert messages[-1]["content"] == "and a follow-up?"

    def test_updated_at_bumps(self, client, student, fake_llm):
        conv = self._conversation(student)
        before = conv.updated_at
        fake_llm(["a"])
        _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
              {"body": "q"})
        conv.refresh_from_db()
        assert conv.updated_at > before

    def test_foreign_conversation_404s(self, client, student, fake_llm):
        other = User.objects.create_user("other")
        conv = self._conversation(other)
        fake_llm(["a"])
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "q"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unknown_conversation"

    def test_llm_failure_rescues_the_turn(self, client, student, monkeypatch):
        conv = self._conversation(student)
        monkeypatch.setattr(chat_views, "llm_factory",
                            lambda: FakeLLM(replies=[]))  # first call raises
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "q"})
        assert response.status_code == 200
        last = response.json()["messages"][-1]
        assert last["role"] == "thrive"
        assert "trouble" in last["body"]
        log = ChatTurnLog.objects.get()
        assert log.model_note == "degraded"
        # The student turn must survive a bot crash: it was persisted in its
        # own transaction before the (failing) bot call ran.
        assert ChatMessage.objects.filter(
            conversation=conv, role="student", body="q").exists()

    def test_electives_destination_dispatches_with_user(self, client, student, fake_llm):
        conv = self._conversation(student, destination="courses")
        fake_llm([json.dumps({"reply": "Which role?", "ready": False,
                              "career_roles": []})])
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "recommend me electives"})
        assert response.json()["messages"][-1]["body"] == "Which role?"


class TestMethodGuards:
    def test_get_list_still_works_and_delete_is_405(self, client, student):
        assert client.get("/api/thrive/conversations").status_code == 200
        assert client.delete("/api/thrive/conversations").status_code == 405
