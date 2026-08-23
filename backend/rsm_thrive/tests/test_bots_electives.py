import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.services.bots import CLARIFY_FALLBACK, answer_electives
from rsm_thrive.services.llm import FakeLLM

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user("stu")


def _extract(ready, roles, reply="Got it.", interests=None):
    return json.dumps({"reply": reply, "ready": ready, "career_roles": roles,
                       "interests": interests or []})


class TestElectivesBot:
    def test_unclear_goal_asks_to_clarify(self, user):
        fake = FakeLLM(replies=[_extract(False, [], reply="Which role?")])
        reply = answer_electives(fake, user, "hello", [])
        assert reply.body == "Which role?"
        assert reply.model_note == "clarify"
        assert len(fake.calls) == 1
        assert fake.calls[0][2] is True  # extraction runs in json mode

    def test_invalid_roles_are_dropped_then_clarify(self, user):
        fake = FakeLLM(replies=[_extract(True, ["astronaut"])])
        reply = answer_electives(fake, user, "I want to be an astronaut", [])
        assert reply.model_note == "clarify"
        assert reply.body  # fallback clarify copy is non-empty

    def test_clear_goal_runs_engine_then_explains(self, user):
        fake = FakeLLM(replies=[
            _extract(True, ["data-scientist"]),
            "Take MGTA 466 first [1].",
        ])
        reply = answer_electives(fake, user, "I want to be a data scientist", [])
        assert reply.model_note == "engine+llm"
        assert reply.body.startswith("Take MGTA 466 first")
        explain_system = fake.calls[1][0]
        assert "Ranked recommendations" in explain_system
        assert "deterministic" in explain_system

    def test_engine_block_lists_real_courses_with_reasons(self, user):
        fake = FakeLLM(replies=[_extract(True, ["data-scientist"]), "ok"])
        answer_electives(fake, user, "data scientist please", [])
        explain_system = fake.calls[1][0]
        assert "MGTA" in explain_system and "reasons:" in explain_system

    def test_role_ids_are_offered_to_the_extractor(self, user):
        fake = FakeLLM(replies=[_extract(False, [])])
        answer_electives(fake, user, "hi", [])
        assert "data-scientist" in fake.calls[0][0]

    def test_non_string_reply_falls_back_to_clarify_copy(self, user):
        fake = FakeLLM(replies=[json.dumps(
            {"reply": {"x": 1}, "ready": False, "career_roles": []})])
        reply = answer_electives(fake, user, "hello", [])
        assert reply.model_note == "clarify"
        assert reply.body == CLARIFY_FALLBACK
