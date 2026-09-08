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
        # A plain answer offers no buttons and no form.
        assert payload["messages"][1]["quickReplies"] == []
        assert payload["messages"][1]["form"] is None

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

    def test_the_courses_destination_answers_free_text(self, client, student,
                                                       fake_llm):
        """No interview: a sentence naming a track and a goal produces the
        plan, and the reply carries no buttons and no form."""
        conv = self._conversation(student, destination="courses")
        fake_llm([])       # an exhausted FakeLLM raises if anything calls it
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "11 month track, data scientist, python 3 sql 3, moderate load"})
        last = response.json()["messages"][-1]
        assert "MGTA" in last["body"], "it produced a real plan"
        assert last["quickReplies"] == []
        assert last["form"] is None

    def test_the_route_is_recorded_on_the_turn_log(self, client, student, fake_llm):
        """Which path an answer came down is the thing a bad answer is
        diagnosed by. See `models.chat.ChatTurnLog`."""
        from rsm_thrive.models import ChatTurnLog

        conv = self._conversation(student, destination="courses")
        fake_llm([])
        _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
              {"body": "I want to be a data scientist"})
        log = ChatTurnLog.objects.order_by("-pk").first()
        assert log.route == "role"
        assert log.question == "I want to be a data scientist"
        # A rule decided, so there is no probability to record.
        assert log.route_confidence is None


class TestMethodGuards:
    def test_get_list_still_works_and_delete_is_405(self, client, student):
        assert client.get("/api/thrive/conversations").status_code == 200
        assert client.delete("/api/thrive/conversations").status_code == 405

    def test_conversation_detail_put_is_405(self, client, student):
        # DELETE is a real verb on this route now (see TestDeleteConversation);
        # everything else still is not.
        conv = Conversation.objects.create(user=student, destination="career",
                                           title="t")
        assert client.put(f"/api/thrive/conversations/conv-{conv.pk}").status_code == 405


class TestDeleteConversation:
    """A student can throw a saved conversation away."""

    def test_it_deletes_the_conversation_and_its_messages(self, client, student):
        conv = Conversation.objects.create(user=student, destination="career",
                                           title="t")
        ChatMessage.objects.create(conversation=conv, role="student", body="hi")
        ChatMessage.objects.create(conversation=conv, role="thrive", body="hello")

        response = client.delete(f"/api/thrive/conversations/conv-{conv.pk}")

        assert response.status_code == 200
        assert not Conversation.objects.filter(pk=conv.pk).exists()
        assert ChatMessage.objects.filter(conversation_id=conv.pk).count() == 0

    def test_it_takes_this_conversations_planner_session_with_it(self, client, student):
        from rsm_thrive.models import PlannerSession

        conv = Conversation.objects.create(user=student, destination="courses",
                                           title="17 month")
        PlannerSession.objects.create(conversation=conv, intake={"track": "17 month"})

        client.delete(f"/api/thrive/conversations/conv-{conv.pk}")

        assert PlannerSession.objects.count() == 0

    def test_it_leaves_the_students_committed_plan_alone(self, client, student):
        # The plan is keyed to the STUDENT and served by /api/thrive/plan.
        # Tidying the chat list is not a request to throw a plan of study away.
        from rsm_thrive.models import CoursePlan

        CoursePlan.objects.create(user=student, track="17 month",
                                  intake={"track": "17 month"})
        conv = Conversation.objects.create(user=student, destination="courses",
                                           title="17 month")

        client.delete(f"/api/thrive/conversations/conv-{conv.pk}")

        assert CoursePlan.objects.filter(user=student).exists()

    def test_another_students_conversation_is_a_404_and_survives(self, client, student):
        # A 404 rather than a 403: a distinct "forbidden" would confirm that
        # someone else's conversation id is real.
        stranger = User.objects.create_user("other")
        theirs = Conversation.objects.create(user=stranger, destination="career",
                                             title="theirs")

        response = client.delete(f"/api/thrive/conversations/conv-{theirs.pk}")

        assert response.status_code == 404
        assert Conversation.objects.filter(pk=theirs.pk).exists()

    def test_deleting_something_that_is_not_there_is_a_404(self, client, student):
        assert client.delete("/api/thrive/conversations/conv-99999").status_code == 404

    def test_it_requires_login(self, client):
        user = User.objects.create_user("someone")
        conv = Conversation.objects.create(user=user, destination="career",
                                           title="t")

        response = client.delete(f"/api/thrive/conversations/conv-{conv.pk}")

        assert response.status_code in (401, 403)
        assert Conversation.objects.filter(pk=conv.pk).exists()
