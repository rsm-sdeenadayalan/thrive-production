"""LLM backends behind one small interface.

`GeminiClient` is the working default (free tier, retry + sibling-model
fallback, ported from the prior Rady Recommender project). `FakeLLM` is the
test double. When Vincent grants `ai_service` access (VINCENT-ASKS #4), an
`AiServiceLLM` subclass slots in here without touching any bot.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod

from django.conf import settings

logger = logging.getLogger("rsm_thrive.llm")

GEMINI_MODEL = "gemini-flash-latest"
# Tried in order when the primary is overloaded (503) or rate-limited (429):
# separate models have separate free-tier quotas.
GEMINI_FALLBACKS = ["gemini-3.5-flash", "gemini-flash-lite-latest"]


class LLM(ABC):
    @abstractmethod
    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...] -> reply text."""


class FakeLLM(LLM):
    """Scripted replies, recorded calls. The only LLM pytest ever runs."""

    def __init__(self, replies: list):
        self._replies = list(replies)
        self.calls = []

    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        self.calls.append((system, messages, json_mode))
        if not self._replies:
            raise RuntimeError("FakeLLM exhausted")
        return self._replies.pop(0)


def parse_llm_json(text: str) -> dict:
    """Extract the assistant's JSON envelope from raw model output.

    Tolerates code fences, surrounding prose, and junk wrappers by scanning
    for any decodable JSON object and preferring one that has "reply". Falls
    back to treating the whole text as a plain chat reply so a malformed
    response degrades instead of crashing the turn.
    """
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL) + [text]
    decoder = json.JSONDecoder()
    found = []
    for cand in candidates:
        try:
            out = json.loads(cand)
            if isinstance(out, dict):
                found.append(out)
                continue
        except (json.JSONDecodeError, ValueError):
            pass
        for i, ch in enumerate(cand):
            if ch != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(cand[i:])
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                found.append(obj)
    for obj in found:
        if "reply" in obj:
            return obj
    if found:
        return found[0]
    return {"reply": text, "action": "chat"}


class GeminiClient(LLM):
    """Gemini backend (GEMINI_API_KEY), with 429/5xx retries and model fallback."""

    def __init__(self, api_key=None, model=None, fallback_models=None,
                 sleep=time.sleep):
        from google import genai  # lazy: tests never import the SDK
        from google.genai.errors import APIError

        key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=key)
        self._api_error = APIError
        self._sleep = sleep
        self._models = [model or GEMINI_MODEL] + list(
            GEMINI_FALLBACKS if fallback_models is None else fallback_models)

    def _generate(self, model, contents, config):
        return self._client.models.generate_content(
            model=model, contents=contents, config=config)

    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        from google.genai import types

        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if json_mode else None,
        )
        return self._chat_with_retries(contents, config)

    def _chat_with_retries(self, contents, config) -> str:
        last_err = None
        for i, model in enumerate(self._models):
            for attempt in range(3):
                try:
                    resp = self._generate(model, contents, config)
                    return resp.text or ""
                except self._api_error as e:
                    last_err = e
                    code = getattr(e, "code", None)
                    if code == 429 and attempt < 2:
                        self._sleep(15 * (attempt + 1))
                        continue
                    if code in (500, 503) and attempt < 2:
                        self._sleep(3 * (attempt + 1))
                        continue
                    break  # this model is out; try the next
            if i < len(self._models) - 1:
                logger.warning("model %s unavailable, falling back to %s",
                               model, self._models[i + 1])
        raise last_err


def get_llm() -> LLM:
    """The configured backend. Views hold this behind an injectable seam."""
    backend = getattr(settings, "THRIVE_LLM", "gemini")
    if backend == "fake":
        raise RuntimeError(
            "THRIVE_LLM=fake requires the test to inject a FakeLLM explicitly.")
    return GeminiClient()
