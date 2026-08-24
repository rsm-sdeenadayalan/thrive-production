"""LLM backends behind one small interface.

`TritonAiLLM` is the working default — UCSD's TritonAI proxy
(https://tritonai-api.ucsd.edu/v1), OpenAI-compatible, model
`claude-sonnet-4-6` (live-verified 2026-08-23; ids drift — the portal's models page is the source of truth). Retries are same-model only (429/5xx), no
model fallback: TritonAI is the single sanctioned backend, so a
failure here is meant to surface honestly and feed the existing
degraded/503 paths rather than silently swap models. `FakeLLM` is
the test double.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod

from django.conf import settings

logger = logging.getLogger("rsm_thrive.llm")

BASE_URL = "https://tritonai-api.ucsd.edu/v1"


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


class TritonAiLLM(LLM):
    """TritonAI backend (TRITONAI_API_KEY), OpenAI-compatible, with 429/5xx retries.

    Same-model retry only — deliberate, no fallback model list.
    """

    def __init__(self, api_key=None, model=None, sleep=time.sleep):
        from openai import OpenAI  # lazy: tests never import the SDK

        key = api_key or getattr(settings, "TRITONAI_API_KEY", "")
        if not key:
            raise RuntimeError("TRITONAI_API_KEY is not set.")
        self._model = model or getattr(settings, "TRITONAI_MODEL", "claude-sonnet-4-6")
        self._client = OpenAI(api_key=key, base_url=BASE_URL)
        self._sleep = sleep

    def _create(self, **kwargs):
        return self._client.chat.completions.create(**kwargs)

    def _status_of(self, exc):
        return getattr(exc, "status_code", None)

    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        full_messages = [{"role": "system", "content": system}] + list(messages)
        kwargs = {
            "model": self._model,
            "messages": full_messages,
            "temperature": 0.4,
            "max_tokens": 4000,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return self._chat_with_retries(kwargs)

    def _chat_with_retries(self, kwargs) -> str:
        last_err = None
        for attempt in range(3):
            try:
                resp = self._create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                status = self._status_of(e)
                if status == 429 and attempt < 2:
                    self._sleep(15 * (attempt + 1))
                    continue
                if status in (500, 502, 503) and attempt < 2:
                    self._sleep(3 * (attempt + 1))
                    continue
                raise
        raise last_err


def get_llm() -> LLM:
    """The configured backend. Views hold this behind an injectable seam."""
    backend = getattr(settings, "THRIVE_LLM", "tritonai")
    if backend == "fake":
        raise RuntimeError(
            "THRIVE_LLM=fake requires the test to inject a FakeLLM explicitly.")
    return TritonAiLLM()
