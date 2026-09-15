"""Greetings and 'what can you do' get a friendly intro, not a refusal."""

import pytest

from rsm_thrive.services.bots import answer_career, answer_faq


class _BoomLLM:
    """If small-talk short-circuits correctly, the LLM is never called."""
    def chat(self, *a, **k):
        raise AssertionError("LLM should not be called for small talk")

    def search_chat(self, *a, **k):
        raise AssertionError("web search should not be called for small talk")


@pytest.mark.django_db
@pytest.mark.parametrize("text", ["hey", "hi", "hello there", "what can you do?", "help"])
def test_faq_greetings_get_intro_not_refusal(text):
    reply = answer_faq(_BoomLLM(), text, [])
    assert not reply.refused
    assert reply.model_note == "small_talk"
    assert "THRIVE" in reply.body


@pytest.mark.django_db
def test_career_greeting_gets_intro():
    reply = answer_career(_BoomLLM(), "hey", [])
    assert reply.model_note == "small_talk"
    assert not reply.refused


@pytest.mark.django_db
def test_real_question_is_not_treated_as_small_talk(monkeypatch):
    # A genuine question must fall through to retrieval, not the intro.
    seen = {}
    from rsm_thrive.services import bots

    def fake_retrieve(*args, **kwargs):
        seen["called"] = True
        return []

    monkeypatch.setattr(bots, "retrieve", fake_retrieve)
    monkeypatch.setattr(bots, "_answer_from_the_web",
                        lambda *a, **k: bots.BotReply("web", [], "web"))
    reply = answer_faq(_BoomLLM(), "when is the enrollment deadline?", [])
    assert seen.get("called") is True
    assert reply.model_note != "small_talk"
