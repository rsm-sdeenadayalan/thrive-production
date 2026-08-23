import json

import pytest

from rsm_thrive.services.bot_config import bot_config, load_bot_config
from rsm_thrive.services.llm import FakeLLM, GeminiClient, parse_llm_json


class TestParseLlmJson:
    def test_plain_json(self):
        assert parse_llm_json('{"reply": "hi", "action": "chat"}') == {
            "reply": "hi", "action": "chat"}

    def test_fenced_json(self):
        text = 'Sure!\n```json\n{"reply": "ok"}\n```\nDone.'
        assert parse_llm_json(text)["reply"] == "ok"

    def test_junk_wrapped_json(self):
        text = '{\\text{ {"reply": "inner"} }}'
        assert parse_llm_json(text)["reply"] == "inner"

    def test_prefers_envelope_with_reply(self):
        text = '{"other": 1} and then {"reply": "the one"}'
        assert parse_llm_json(text)["reply"] == "the one"

    def test_garbage_falls_back_to_chat_reply(self):
        out = parse_llm_json("just prose, no json at all")
        assert out == {"reply": "just prose, no json at all", "action": "chat"}


class TestFakeLLM:
    def test_pops_replies_in_order_and_records_calls(self):
        fake = FakeLLM(replies=["one", "two"])
        assert fake.chat("sys", [{"role": "user", "content": "q"}]) == "one"
        assert fake.chat("sys", [], json_mode=True) == "two"
        assert fake.calls[0] == ("sys", [{"role": "user", "content": "q"}], False)
        assert fake.calls[1][2] is True

    def test_exhaustion_raises(self):
        fake = FakeLLM(replies=[])
        with pytest.raises(RuntimeError):
            fake.chat("sys", [])


class TestGeminiRetries:
    """GeminiClient's retry ladder, with the SDK faked out entirely."""

    def _client(self, script, sleeps):
        """script: list of ('ok', text) | ('err', code) consumed per API call."""
        client = GeminiClient.__new__(GeminiClient)
        client._models = ["m-primary", "m-fallback"]
        client._sleep = sleeps.append  # records requested waits, no real sleep

        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        client._api_error = FakeAPIError

        def generate(model, contents, config):
            kind, value = script.pop(0)
            if kind == "err":
                raise FakeAPIError(value)
            class R: text = value
            return R()

        client._generate = generate
        return client

    def test_retries_503_then_succeeds(self):
        sleeps = []
        client = self._client([("err", 503), ("ok", "answer")], sleeps)
        assert client._chat_with_retries([], None) == "answer"
        assert sleeps == [3]

    def test_falls_to_next_model_after_exhausting_primary(self):
        sleeps = []
        client = self._client(
            [("err", 503), ("err", 503), ("err", 503), ("ok", "rescued")], sleeps)
        assert client._chat_with_retries([], None) == "rescued"

    def test_429_waits_longer(self):
        sleeps = []
        client = self._client([("err", 429), ("ok", "x")], sleeps)
        client._chat_with_retries([], None)
        assert sleeps == [15]


class TestBotConfig:
    def test_defaults_load_and_have_required_keys(self):
        config = load_bot_config()
        for bot in ("faq", "electives", "career"):
            entry = bot_config(bot)
            assert isinstance(entry["system_prompt"], str) and entry["system_prompt"]
            assert isinstance(entry["top_k"], int)
            assert 0.0 <= entry["min_similarity"] <= 1.0
        assert "refusal_reply" in bot_config("faq")

    def test_override_path(self, tmp_path, settings):
        override = {"faq": {"top_k": 99}}
        path = tmp_path / "bots.json"
        path.write_text(json.dumps(override))
        settings.THRIVE_BOT_CONFIG = str(path)
        assert bot_config("faq")["top_k"] == 99
        # unspecified keys fall through to the repo defaults
        assert bot_config("faq")["system_prompt"]
