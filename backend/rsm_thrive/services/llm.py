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
import threading
import time
from abc import ABC, abstractmethod

from django.conf import settings

logger = logging.getLogger("rsm_thrive.llm")

BASE_URL = "https://tritonai-api.ucsd.edu/v1"


class LLM(ABC):
    @abstractmethod
    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...] -> reply text."""

    def search_chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        """Like `chat`, but the model may look things up on the web.

        Separate from `chat` rather than a flag on it, because it is a different
        promise: slower, and grounded in something outside this codebase. A
        backend that cannot search answers exactly as `chat` does, so a caller
        gets the model's own knowledge instead of an error -- degraded, not
        broken.
        """
        return self.chat(system, messages, json_mode)


class FakeLLM(LLM):
    """Scripted replies, recorded calls. The only LLM pytest ever runs.

    Thread-safe: the results page's parallel match-report scoring (see
    `feed._score_top_candidates_with_llm`) calls one `FakeLLM` instance from
    several worker threads at once in tests, so `calls` and `_replies` are
    guarded by a lock rather than assumed single-threaded.
    """

    def __init__(self, replies: list):
        self._replies = list(replies)
        self.calls = []
        self._lock = threading.Lock()

    def chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        with self._lock:
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


class SharedCodexCredentials:
    """One OAuth credential, shared by every request on the server.

    On a laptop each developer authenticates as themselves and the vendored
    script's own load-refresh-or-login is exactly right. A hosted TEST instance
    is different: one credential file serves the whole cohort, nobody signs in,
    and three things that never matter for one person start mattering.

    **Refreshes must not race.** `ensure_openai_codex_credentials()` runs on
    every turn, and OpenAI's refresh tokens are single-use -- the vendored
    script recognises `refresh_token_reused` and `already been used` for that
    reason. Two concurrent turns arriving after expiry would both refresh, and
    the loser's token would be dead for EVERYONE. One lock, one refresh.

    **A server must never try to log in.** On failure the script falls back to
    `login_openai_codex_oauth()`, which calls `webbrowser.open()` and then
    blocks on `input()`. On a headless box that hangs the worker for good. Here
    interactive login is allowed only when someone is actually at a terminal,
    and otherwise raises something a log will explain.

    **Re-reading and re-parsing a file every turn is waste.** The credential is
    held in memory and only touched again near expiry.

    Provision the server by copying a developer's `~/.codex/auth.json` to the
    box and pointing `CODEX_CREDENTIALS_PATH` at it. Treat that file as a
    secret: it carries a long-lived refresh token for a personal ChatGPT
    account, and anyone who can read it can use that account.
    """

    _lock = threading.Lock()
    _cached = None

    # Refresh this far before the token actually expires, so a request never
    # races the expiry itself.
    MARGIN_MS = 5 * 60 * 1000

    @classmethod
    def _path(cls):
        configured = (getattr(settings, "CODEX_CREDENTIALS_PATH", "") or "").strip()
        return configured or None

    @classmethod
    def _interactive_allowed(cls):
        """Only when a human is present to complete a browser sign-in."""
        explicit = getattr(settings, "CODEX_ALLOW_BROWSER_LOGIN", None)
        if explicit is not None:
            return bool(explicit)
        try:
            import sys
            return sys.stdin is not None and sys.stdin.isatty()
        except Exception:
            return False

    @classmethod
    def get(cls):
        from rsm_thrive.services import codex_oauth

        now_ms = int(time.time() * 1000)
        cached = cls._cached
        if cached and cached.expires > now_ms + cls.MARGIN_MS:
            return cached

        with cls._lock:
            # Re-check inside the lock: another thread may have refreshed while
            # this one waited, and refreshing again would burn a single-use
            # token for no reason.
            cached = cls._cached
            now_ms = int(time.time() * 1000)
            if cached and cached.expires > now_ms + cls.MARGIN_MS:
                return cached

            path = cls._path()
            current = codex_oauth.load_openai_codex_credentials(path)
            if current is None:
                current = codex_oauth._load_codex_cli_credentials()

            if current is None:
                if cls._interactive_allowed():
                    current = codex_oauth.login_openai_codex_oauth()
                    codex_oauth.save_openai_codex_credentials(current, path)
                else:
                    raise RuntimeError(
                        "No Codex credentials on this host and no terminal to "
                        "sign in from. Copy a developer's ~/.codex/auth.json to "
                        "the server and set CODEX_CREDENTIALS_PATH to it.")
            elif current.expires <= now_ms + cls.MARGIN_MS:
                try:
                    current = codex_oauth.refresh_openai_codex_token(current.refresh)
                    codex_oauth.save_openai_codex_credentials(current, path)
                    logger.info("codex credentials refreshed")
                except RuntimeError as error:
                    # A refresh token that is expired or already spent cannot be
                    # recovered without a person. Say so plainly rather than
                    # letting the vendored fallback open a browser nobody sees.
                    if not cls._interactive_allowed():
                        raise RuntimeError(
                            "Codex credentials could not be refreshed and this "
                            "host cannot sign in interactively. Re-authenticate "
                            "on a workstation and copy the credential file over. "
                            f"Underlying error: {error}") from error
                    current = codex_oauth.login_openai_codex_oauth()
                    codex_oauth.save_openai_codex_credentials(current, path)

            cls._cached = current
            return current

    @classmethod
    def reset(cls):
        """Drop the in-memory copy. For tests and for a credential swap."""
        with cls._lock:
            cls._cached = None


class CodexOAuthLLM(LLM):
    """LOCAL DEVELOPMENT ONLY: a personal ChatGPT/Codex subscription over OAuth.

    Exists because the TritonAI keys this project runs on carry a fixed one-time
    budget with no reset, so an exhausted key stops all local work on the
    chatbots. This backend needs no API key at all -- it reuses the Codex CLI's
    stored credentials (`~/.codex/auth.json`), refreshing them as needed, and
    falls back to a browser sign-in if there are none.

    NOT a production backend, and deliberately not the default. It authenticates
    as a person rather than as a metered service, it talks to an endpoint that
    carries no compatibility promise, and the deployed service must stay on
    `TritonAiLLM`. `THRIVE_LLM=codex` is a laptop switch.

    It provides COMPLETIONS ONLY -- no embeddings, and its token reaches
    api.openai.com but the account has no API billing, so `/v1/embeddings`
    answers 429. Retrieval therefore needs a provider of its own, which is why
    `get_embeddings()` reads `THRIVE_EMBEDDINGS` separately and resolves this
    backend to `LocalEmbeddings` (on-machine, keyless). With that in place the
    FAQ bot scores 6/9 on the golden eval -- the same as the documented
    TritonAI baseline -- so nothing here is degraded by the switch.
    """

    # The interview is extraction and short prose, not reasoning work. Leaving
    # effort unset keeps turns fast; the default of "high" made each extraction
    # take tens of seconds for no gain in answer quality.
    def __init__(self, model=None, reasoning_effort=None):
        self._model = model or getattr(settings, "CODEX_MODEL", "gpt-5.4")
        self._effort = reasoning_effort

    def search_chat(self, system: str, messages: list, json_mode: bool = False) -> str:
        return self.chat(system, messages, json_mode, search=True)

    def chat(self, system: str, messages: list, json_mode: bool = False,
             search: bool = False) -> str:
        from rsm_thrive.services import codex_oauth

        instructions = system
        if json_mode:
            # The Responses API's structured-output field is not relied on here:
            # `parse_llm_json` already tolerates fences and surrounding prose, so
            # an instruction plus that parser is the combination that cannot
            # fail closed on an endpoint whose schema support is undocumented.
            instructions = (f"{system}\n\nReturn ONLY a single JSON object. "
                            "No prose, no explanation, no code fences.")
        credentials = SharedCodexCredentials.get()
        return self._with_retries(credentials, list(messages), instructions, search)

    # One retry, on TRANSIENT failures only. `TritonAiLLM` has had this from the
    # start and this backend went without, which showed up as soon as it was
    # exercised at volume: one probe in 120 died on "read operation timed out"
    # -- a flaky socket, not a bad request. The view would turn that into the
    # degraded reply, so a student loses a turn to something a second attempt
    # answers. Not retried: anything that will fail again the same way.
    _TRANSIENT = ("timed out", "timeout", "connection reset", "connection aborted",
                  "temporarily unavailable", "bad gateway", "502", "503", "504")

    def _with_retries(self, credentials, messages, instructions, search=False):
        from rsm_thrive.services import codex_oauth

        last = None
        for attempt in range(2):
            try:
                return self._create(codex_oauth, credentials, messages, instructions,
                                    search)
            except Exception as error:
                last = error
                text = str(error).lower()
                if attempt == 0 and any(s in text for s in self._TRANSIENT):
                    logger.warning("codex turn failed transiently, retrying: %s",
                                   str(error)[:120])
                    continue
                raise
        raise last

    def _create(self, codex_oauth, credentials, messages, instructions, search=False):
        return codex_oauth.create_codex_chat(
            messages, credentials=credentials, model=self._model,
            instructions=instructions, reasoning_effort=self._effort, search=search,
            # Well above a normal turn (~2.5s) and well below anything a user
            # or a batch run should wait on. See the deadline in
            # `create_codex_chat` for why the module default is not enough.
            timeout=float(getattr(settings, "CODEX_TIMEOUT_SECONDS", 90)))


def get_llm() -> LLM:
    """The configured backend. Views hold this behind an injectable seam."""
    backend = getattr(settings, "THRIVE_LLM", "tritonai")
    if backend == "fake":
        raise RuntimeError(
            "THRIVE_LLM=fake requires the test to inject a FakeLLM explicitly.")
    if backend == "codex":
        return CodexOAuthLLM()
    return TritonAiLLM()
