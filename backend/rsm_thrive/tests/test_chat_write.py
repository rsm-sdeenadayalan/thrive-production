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

    def test_electives_destination_runs_the_planner_interview(self, client, student,
                                                              fake_llm):
        """The courses destination asks for the track before naming any course."""
        conv = self._conversation(student, destination="courses")
        fake_llm([json.dumps({"track": None, "goals": [], "skill_python": None,
                              "skill_sql": None, "skill_stats": None,
                              "skill_ml": None, "skill_communication": None,
                              "workload": None, "interests": []})])
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "recommend me electives"})
        last = response.json()["messages"][-1]
        assert "MGTA" not in last["body"]
        # The track question is a closed set: it comes with buttons, not a form,
        # and each button carries its own explanation so the body does not
        # repeat the list above them.
        assert {"label": "11 month", "send": "11 month",
                "description": "Summer through Spring"} in last["quickReplies"]
        assert {"label": "17 month", "send": "17 month",
                "description": "finishes the following Fall"} in last["quickReplies"]
        assert last["form"] is None

    def test_electives_skills_step_returns_a_rating_form(self, client, student,
                                                          fake_llm):
        """The skills step asks about five areas at once, so it comes as a
        form rather than a row of buttons — see `planner.rating_form_for`."""
        conv = self._conversation(student, destination="courses")
        fake_llm([json.dumps({"track": "11 month", "goals": ["data-scientist"],
                              "skill_python": None, "skill_sql": None,
                              "skill_stats": None, "skill_ml": None,
                              "skill_communication": None, "workload": None,
                              "interests": []})])
        response = _post(client, f"/api/thrive/conversations/conv-{conv.pk}/messages",
                         {"body": "recommend me electives"})
        last = response.json()["messages"][-1]
        assert last["quickReplies"] == []
        assert last["form"]["kind"] == "rating"
        assert {"key": "skill_python", "label": "Python programming"} in \
            last["form"]["rows"]


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
