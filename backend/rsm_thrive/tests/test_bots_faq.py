import pytest

from rsm_thrive.models import Document, DocumentChunk
from rsm_thrive.services.bots import answer_career, answer_faq, build_context
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.llm import FakeLLM

pytestmark = pytest.mark.django_db


def _seed(destinations, text="Students may drop a course before week two."):
    doc = Document.objects.create(source=f"t:{destinations[0]}", title="MSBA Handbook",
                                  kind="policy", destinations=destinations)
    [vector] = FakeEmbeddings().embed([text])
    return DocumentChunk.objects.create(document=doc, seq=0, heading="Drops",
                                        text=text, embedding=vector)


class TestFaqBot:
    def test_thin_retrieval_refuses_without_llm(self):
        fake = FakeLLM(replies=[])  # any call would raise "exhausted"
        reply = answer_faq(fake, "what is the meaning of life", [])
        assert "advising" in reply.body.lower()
        assert reply.chunk_ids == [] and reply.model_note == "refusal"
        assert fake.calls == []

    def test_grounded_answer_carries_context_and_sources(self):
        chunk = _seed(["resources"])
        fake = FakeLLM(replies=["You can drop before week two [1]."])
        reply = answer_faq(fake, "when can I drop a course", [])
        assert reply.chunk_ids == [chunk.pk]
        assert reply.body.startswith("You can drop before week two")
        assert "Sources: MSBA Handbook" in reply.body
        system, messages, json_mode = fake.calls[0]
        assert "[1] MSBA Handbook" in system
        assert messages[-1] == {"role": "user",
                                "content": "when can I drop a course"}
        assert json_mode is False

    def test_history_is_forwarded_and_truncated(self):
        _seed(["resources"], "drop a course before week two of the quarter")
        fake = FakeLLM(replies=["answer"])
        history = [{"role": "user", "content": f"turn {i}"} for i in range(30)]
        answer_faq(fake, "drop a course when", history)
        _, messages, _ = fake.calls[0]
        assert len(messages) <= 13  # 12 history + the question


class TestCareerBot:
    def test_no_context_still_answers(self):
        fake = FakeLLM(replies=["Keep it to one page."])
        reply = answer_career(fake, "resume length?", [])
        assert reply.body == "Keep it to one page."
        assert reply.chunk_ids == [] and reply.model_note == "llm"
        assert "Sources:" not in reply.body

    def test_context_used_when_available(self):
        chunk = _seed(["career"], "Keep the resume to one page for analytics roles.")
        fake = FakeLLM(replies=["One page [1]."])
        reply = answer_career(fake, "how long should my resume for analytics be", [])
        assert reply.chunk_ids == [chunk.pk]
        assert "Sources: MSBA Handbook" in reply.body


class TestBuildContext:
    def test_numbered_titled_passages(self):
        chunk = _seed(["resources"])
        context = build_context([(chunk, 0.9)])
        assert context.startswith("[1] MSBA Handbook — Drops\n")
