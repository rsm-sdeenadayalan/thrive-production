# Phase C: Chatbots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real answers behind Ask THRIVE's three destinations — a RAG FAQ bot with citations and a refusal rule (resources), a deterministic electives recommender with a conversational shell (courses), and a career-coach bot (career) — persisted through new chat write endpoints and wired into the SvelteKit composer.

**Architecture:** An `LLM` interface (Gemini client ported from the prior Rady Recommender project, `FakeLLM` for tests, `ai_service` adapter seam deferred to F5) + an embeddings/retrieval layer over `Document`/`DocumentChunk` rows (vectors as JSON, in-Python cosine — pgvector is an F5 swap). `POST /conversations` and `POST /conversations/{id}/messages` persist the student turn, dispatch by destination to a bot, persist the assistant turn, and return the full conversation payload. The frontend composer posts through a same-origin `/ask-sync` proxy in API mode and keeps its current honest placeholder in mock mode.

**Tech Stack:** Django 6.1 (existing `rsm_thrive` app, uv), `google-genai` (lazy import), `pypdf`, SvelteKit 2 / Svelte 5 runes, Vitest, pytest.

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §5 (Chatbots), §3 (chat models), §7 (testing).

## Global Constraints

- Error envelope: every non-2xx JSON body is `{"error": {"code": "<slug>", "message": "<human>"}}` via `json_error`.
- All JSON keys camelCase; instants serialized with `rsm_thrive.serialize.iso_instant` (America/Los_Angeles ISO-8601).
- Id key spaces: conversations `conv-<pk>`, messages `msg-<pk>`. Never invent a new id shape.
- `AskDestination` is the closed union `"resources" | "courses" | "career"` (frontend `types.ts:500`); backend `DESTINATION_CHOICES` already matches. Unknown destination on write = 400 `bad_request`.
- `ChatRole` is `"student" | "thrive"`.
- Auth: every endpoint uses `@api_login_required`; chat endpoints do NOT require a `thrive_profile` (a logged-in user without one may still chat).
- Backend tests: `cd backend && uv run pytest`. All existing tests must stay green.
- Frontend gates: `npm test`, `npm run check` (0 errors 0 warnings), `npm run build` — run from `frontend/`.
- Frontend copy lives in `src/lib/messages.ts`; components never hardcode user-facing strings. No hardcoded colors (repo test enforces design tokens).
- Components never read `Date.now()`/`new Date()` for anything persisted or compared; server loads pass day keys.
- Never `print()` in backend library code — use `logging.getLogger("rsm_thrive.<mod>")`.
- The LLM is NEVER called during pytest with a real network: tests use `FakeLLM`/`FakeEmbeddings` (`THRIVE_LLM=fake` is the test default via conftest).
- New settings read via `os.environ` in `config/settings.py` only, with safe defaults: `THRIVE_LLM` (default `"gemini"`), `THRIVE_BOT_CONFIG` (default `""` = use repo `config/bots.json`), `GEMINI_API_KEY` (no default).
- The spec's refusal rule is binding: the FAQ bot answers ONLY from retrieved context; thin retrieval → deterministic refusal copy pointing to advising, with no LLM call.

---

### Task 1: LLM service layer + bot config

**Files:**
- Create: `backend/rsm_thrive/services/llm.py`
- Create: `backend/config/bots.json`
- Create: `backend/rsm_thrive/services/bot_config.py`
- Modify: `backend/pyproject.toml` (add `google-genai>=1.0`, `pypdf>=5.0` to `dependencies`)
- Modify: `backend/config/settings.py` (add `THRIVE_LLM`, `THRIVE_BOT_CONFIG` reads)
- Modify: `backend/conftest.py` (force `THRIVE_LLM=fake` for the whole suite)
- Test: `backend/rsm_thrive/tests/test_llm.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `class LLM(ABC)` with `chat(self, system: str, messages: list[dict], json_mode: bool = False) -> str` — `messages` items are `{"role": "user"|"assistant", "content": str}`.
  - `class GeminiClient(LLM)` — `__init__(self, api_key=None, model=None, fallback_models=None, sleep=time.sleep)`.
  - `class FakeLLM(LLM)` — `__init__(self, replies: list[str])`, pops replies in order, records `self.calls` as `(system, messages, json_mode)` tuples; raises `RuntimeError("FakeLLM exhausted")` past the end.
  - `def get_llm() -> LLM` — reads `settings.THRIVE_LLM`: `"fake"` → `FakeLLM(replies=["{}"])` refreshed per call is useless, so `"fake"` raises `RuntimeError("THRIVE_LLM=fake requires tests to inject a FakeLLM explicitly")`. Views take an injectable seam instead (Task 7).
  - `def parse_llm_json(text: str) -> dict` — ported envelope parser.
  - `def load_bot_config() -> dict` and `def bot_config(bot: str) -> dict` in `bot_config.py`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_llm.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_llm.py -q`
Expected: FAIL with `ModuleNotFoundError: rsm_thrive.services.llm`

- [ ] **Step 3: Implement `services/llm.py`**

Port from the prior project (`/Users/shankar/Documents/Rady Recommender/Old/recommender/src/llm.py`) with these changes: `logging` instead of `print`; injectable `_sleep`; `json_mode` parameter (the old client forced `response_mime_type="application/json"` — FAQ/career answers are plain text); SDK calls isolated behind `self._generate` / `self._api_error` so retries are testable without the SDK.

```python
# backend/rsm_thrive/services/llm.py
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
```

Note the `sleep=time.sleep` init parameter stores to `self._sleep`; the retry tests build the object with `__new__` and set `_models`/`_sleep`/`_api_error`/`_generate` directly, so retries are tested without the SDK installed.

- [ ] **Step 4: Implement `config/bots.json` and `bot_config.py`**

```json
{
  "faq": {
    "model": null,
    "top_k": 6,
    "min_similarity": 0.35,
    "max_history_turns": 12,
    "system_prompt": "You are THRIVE, the assistant for UC San Diego Rady's MSBA program. Answer the student's question using ONLY the numbered context passages provided. Rules: (1) If the passages do not contain the answer, say you don't have that information and suggest contacting MSBA advising — never guess a policy. (2) Cite the passages you used by their bracketed number, like [1]. (3) Be concise and direct. (4) Never invent deadlines, fees, unit counts, or approval chains.",
    "refusal_reply": "I don't have program material that answers that, and I'd rather not guess about a policy. Please check with MSBA advising — you can book time with them from the Appointments tab."
  },
  "career": {
    "model": null,
    "top_k": 4,
    "min_similarity": 0.35,
    "max_history_turns": 12,
    "system_prompt": "You are THRIVE, a pragmatic career coach for UC San Diego Rady MSBA students heading into analytics roles. Give specific, actionable advice about applications, interviews, offers, and professional situations. If numbered context passages are provided, ground your answer in them and cite them like [1]; otherwise answer from general best practice and say so. For anything requiring program policy or personal circumstances you can't know, recommend booking time with career coaching from the Appointments tab. Be concise."
  },
  "electives": {
    "model": null,
    "top_k": 4,
    "min_similarity": 0.30,
    "max_history_turns": 12,
    "max_recommendations": 5,
    "extract_prompt": "You extract a career objective from a conversation with an MSBA student. Reply with JSON only: {\"reply\": \"<one short conversational sentence to the student>\", \"ready\": <true if a career goal is clear>, \"career_roles\": [<role ids from the allowed list, best match first>], \"interests\": [<free-text keywords the student mentioned>]}. Allowed role ids: {role_ids}. If no clear goal yet, set ready=false and make reply a single specific clarifying question.",
    "explain_prompt": "You are THRIVE, the electives advisor for the Rady MSBA. The ranked recommendations below come from a deterministic scoring engine — present them faithfully, do not reorder or invent courses. Write a short conversational answer: name each recommended course with its code, one line on why it fits (use the engine's reasons and the numbered syllabus passages, citing like [1] where used). End with one sentence inviting a follow-up. Never recommend a course not in the list."
  }
}
```

```python
# backend/rsm_thrive/services/bot_config.py
"""Versioned, deploy-free bot tuning.

Defaults live in the repo (`config/bots.json`, versioned). Setting
THRIVE_BOT_CONFIG to a file path overlays it key-by-key per bot, so prompts
and retrieval params are editable on the server without a deploy — the
spec's explicit tunability requirement.
"""

import json
from pathlib import Path

from django.conf import settings

_DEFAULTS_PATH = Path(settings.BASE_DIR) / "config" / "bots.json"


def load_bot_config() -> dict:
    config = json.loads(_DEFAULTS_PATH.read_text())
    override_path = getattr(settings, "THRIVE_BOT_CONFIG", "")
    if override_path:
        override = json.loads(Path(override_path).read_text())
        for bot, entry in override.items():
            config.setdefault(bot, {}).update(entry)
    return config


def bot_config(bot: str) -> dict:
    return load_bot_config()[bot]
```

- [ ] **Step 5: Settings, conftest, and dependencies**

In `config/settings.py`, next to the existing env reads:

```python
THRIVE_LLM = os.environ.get("THRIVE_LLM", "gemini")
THRIVE_BOT_CONFIG = os.environ.get("THRIVE_BOT_CONFIG", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
```

In `backend/conftest.py` add a top-level autouse guard:

```python
@pytest.fixture(autouse=True)
def _no_real_llm(settings):
    settings.THRIVE_LLM = "fake"
```

In `backend/pyproject.toml` dependencies add `"google-genai>=1.0"` and `"pypdf>=5.0"`, then run `uv sync`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_llm.py -q` then the full suite `uv run pytest -q`.
Expected: new tests PASS; full suite stays green.

- [ ] **Step 7: Commit**

```bash
git add backend && git commit -m "feat(c): LLM service layer (Gemini port + FakeLLM) and versioned bot config"
```

---

### Task 2: Knowledge models, embeddings, retrieval

**Files:**
- Create: `backend/rsm_thrive/models/knowledge.py`
- Modify: `backend/rsm_thrive/models/__init__.py` (export `Document`, `DocumentChunk`)
- Create: `backend/rsm_thrive/services/embeddings.py`
- Create: `backend/rsm_thrive/services/retrieval.py`
- Create: migration `backend/rsm_thrive/migrations/0013_document_documentchunk.py` (via `makemigrations`)
- Test: `backend/rsm_thrive/tests/test_retrieval.py`

**Interfaces:**
- Consumes: nothing from Task 1 (embeddings have their own fake).
- Produces:
  - `Document(source: str unique max 300, title: str max 300, kind: str choices syllabus|policy|catalog|scraped, destinations: JSONField list[str], fetched_at: DateTimeField default timezone.now)`
  - `DocumentChunk(document: FK related_name="chunks", seq: int, heading: str max 300 blank, text: TextField, embedding: JSONField list[float])`, `Meta.ordering = ["document_id", "seq"]`, unique `(document, seq)` named `uniq_document_chunk_seq`.
  - `class Embeddings(ABC)` with `embed(self, texts: list[str]) -> list[list[float]]`.
  - `class FakeEmbeddings(Embeddings)` — deterministic 32-dim bag-of-hashed-words unit vectors.
  - `class GeminiEmbeddings(Embeddings)` — `gemini-embedding-001`, lazy SDK import.
  - `def get_embeddings() -> Embeddings` — `settings.THRIVE_LLM == "fake"` → `FakeEmbeddings()` (embeddings piggyback the same switch; unlike chat, a deterministic fake IS meaningful here so no raise).
  - `def cosine(a: list[float], b: list[float]) -> float`
  - `def retrieve(query: str, destination: str, top_k: int, min_similarity: float, embeddings: Embeddings | None = None) -> list[tuple[DocumentChunk, float]]` — chunks of documents whose `destinations` include `destination`, scored by cosine, filtered by `min_similarity`, best first, at most `top_k`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_retrieval.py
import pytest

from rsm_thrive.models import Document, DocumentChunk
from rsm_thrive.services.embeddings import FakeEmbeddings, cosine, get_embeddings
from rsm_thrive.services.retrieval import retrieve

pytestmark = pytest.mark.django_db


def _doc(source, title, kind, destinations, chunks):
    emb = FakeEmbeddings()
    doc = Document.objects.create(source=source, title=title, kind=kind,
                                  destinations=destinations)
    vectors = emb.embed([text for _, text in chunks])
    for seq, ((heading, text), vector) in enumerate(zip(chunks, vectors)):
        DocumentChunk.objects.create(document=doc, seq=seq, heading=heading,
                                     text=text, embedding=vector)
    return doc


class TestFakeEmbeddings:
    def test_deterministic_and_normalized(self):
        emb = FakeEmbeddings()
        [a1] = emb.embed(["drop a course after week two"])
        [a2] = emb.embed(["drop a course after week two"])
        assert a1 == a2
        assert abs(sum(x * x for x in a1) - 1.0) < 1e-9

    def test_overlap_scores_higher_than_disjoint(self):
        emb = FakeEmbeddings()
        query, near, far = emb.embed([
            "dropping a course deadline",
            "the deadline for dropping a course is week two",
            "zoom meeting links for appointments",
        ])
        assert cosine(query, near) > cosine(query, far)

    def test_get_embeddings_is_fake_under_tests(self):
        assert isinstance(get_embeddings(), FakeEmbeddings)


class TestRetrieve:
    def test_ranks_filters_and_scopes_by_destination(self):
        _doc("handbook#drop", "MSBA Handbook", "policy", ["resources"], [
            ("Dropping a course", "Students may drop a course before the end of week two without a W."),
        ])
        _doc("syllabus#456", "MGTA 456 Syllabus", "syllabus", ["resources", "courses"], [
            ("Overview", "Supply chain analytics with optimization models."),
        ])
        _doc("career#resume", "Resume Guide", "scraped", ["career"], [
            ("Length", "Keep the resume to one page for analytics roles."),
        ])

        hits = retrieve("when can I drop a course", "resources",
                        top_k=5, min_similarity=0.0)
        assert hits and hits[0][0].document.title == "MSBA Handbook"
        titles = [chunk.document.title for chunk, _ in hits]
        assert "Resume Guide" not in titles  # career-only doc never leaks

    def test_min_similarity_filters_everything_thin(self):
        _doc("handbook#x", "MSBA Handbook", "policy", ["resources"], [
            ("Laptops", "Laptop loans are handled by the tech desk."),
        ])
        assert retrieve("quantum entanglement", "resources",
                        top_k=5, min_similarity=0.99) == []

    def test_top_k_caps(self):
        chunks = [(f"h{i}", f"course drop deadline detail number {i}") for i in range(4)]
        _doc("handbook#many", "MSBA Handbook", "policy", ["resources"], chunks)
        hits = retrieve("course drop deadline", "resources",
                        top_k=2, min_similarity=0.0)
        assert len(hits) == 2
        assert hits[0][1] >= hits[1][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_retrieval.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement models, embeddings, retrieval**

```python
# backend/rsm_thrive/models/knowledge.py
from django.db import models
from django.utils import timezone

KIND_CHOICES = [("syllabus", "syllabus"), ("policy", "policy"),
                ("catalog", "catalog"), ("scraped", "scraped")]


class Document(models.Model):
    """One ingested source (a PDF, a page, a catalog entry group)."""
    source = models.CharField(max_length=300, unique=True)  # stable ingest key
    title = models.CharField(max_length=300)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    destinations = models.JSONField(default=list)  # which bots may retrieve it
    fetched_at = models.DateTimeField(default=timezone.now)


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE,
                                 related_name="chunks")
    seq = models.IntegerField()
    heading = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    # A JSON list of floats, cosine-scanned in Python: the corpus is a few
    # thousand chunks at most. pgvector is a drop-in swap at F5 if it grows.
    embedding = models.JSONField(default=list)

    class Meta:
        ordering = ["document_id", "seq"]
        constraints = [models.UniqueConstraint(
            fields=["document", "seq"], name="uniq_document_chunk_seq")]
```

```python
# backend/rsm_thrive/services/embeddings.py
"""Embedding backends and the cosine they're compared with."""

import hashlib
import math
import re
from abc import ABC, abstractmethod

from django.conf import settings

EMBEDDING_MODEL = "gemini-embedding-001"
FAKE_DIM = 32


class Embeddings(ABC):
    @abstractmethod
    def embed(self, texts: list) -> list:
        """texts -> list of same-length float vectors."""


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-hashed-words unit vectors.

    Shared words land in shared dimensions, so overlapping texts score
    higher than disjoint ones — enough signal for every retrieval test.
    """

    def embed(self, texts: list) -> list:
        out = []
        for text in texts:
            vector = [0.0] * FAKE_DIM
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.md5(word.encode()).digest()
                vector[digest[0] % FAKE_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            out.append([x / norm for x in vector])
        return out


class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key=None):
        from google import genai  # lazy

        key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=key)

    def embed(self, texts: list) -> list:
        result = self._client.models.embed_content(
            model=EMBEDDING_MODEL, contents=texts)
        return [list(e.values) for e in result.embeddings]


def get_embeddings() -> Embeddings:
    if getattr(settings, "THRIVE_LLM", "gemini") == "fake":
        return FakeEmbeddings()
    return GeminiEmbeddings()


def cosine(a: list, b: list) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
```

```python
# backend/rsm_thrive/services/retrieval.py
"""Top-k chunk retrieval scoped to a destination."""

from rsm_thrive.models import DocumentChunk
from rsm_thrive.services.embeddings import cosine, get_embeddings


def retrieve(query, destination, top_k, min_similarity, embeddings=None):
    embeddings = embeddings or get_embeddings()
    [query_vector] = embeddings.embed([query])
    scored = []
    rows = (DocumentChunk.objects
            .filter(document__destinations__contains=destination)
            .select_related("document"))
    for chunk in rows:
        score = cosine(query_vector, chunk.embedding)
        if score >= min_similarity:
            scored.append((chunk, score))
    scored.sort(key=lambda pair: -pair[1])
    return scored[:top_k]
```

`destinations__contains` on a JSONField list works on both SQLite (as substring-of-JSON it does NOT — so implement the filter portably): replace the queryset filter with a Python-side check:

```python
    rows = DocumentChunk.objects.select_related("document")
    for chunk in rows:
        if destination not in (chunk.document.destinations or []):
            continue
```

Use the portable Python-side check (SQLite dev + Postgres prod must behave identically; the scan already walks every chunk).

Export both models from `models/__init__.py`, run `uv run python manage.py makemigrations rsm_thrive` (expect `0013`), migrate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_retrieval.py -q` then full suite.
Expected: PASS, suite green.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(c): knowledge models, embeddings (Gemini + fake), cosine retrieval"
```

---

### Task 3: Corpus ingestion command

**Files:**
- Create: `backend/rsm_thrive/services/ingest.py`
- Create: `backend/rsm_thrive/management/commands/ingest_corpus.py`
- Create: `backend/rsm_thrive/tests/fixtures/corpus/handbook-excerpt.md` (fixture)
- Test: `backend/rsm_thrive/tests/test_ingest.py`

**Interfaces:**
- Consumes: `Document`, `DocumentChunk`, `get_embeddings` (Task 2).
- Produces:
  - `def chunk_text(text: str, max_chars: int = 1400, overlap: int = 200) -> list[dict]` — heading-aware: split on markdown headings (`^#{1,6} ` lines) into sections; sections longer than `max_chars` split on paragraph boundaries with `overlap` characters carried over; returns `[{"heading": str, "text": str}, ...]`, empty sections dropped.
  - `def ingest_document(source, title, kind, destinations, text, embeddings) -> Document` — deletes any existing `Document` with that `source` (cascade drops old chunks), recreates it, chunks, embeds in one `embeddings.embed` batch, bulk-creates chunks. Re-run = clean upsert.
  - `def extract_pdf_text(path) -> str` — `pypdf.PdfReader`, pages joined with `\n\n`.
  - Command `ingest_corpus <dir>`: for each `*.pdf` in dir → `kind="syllabus"`, `destinations=["resources", "courses"]`, title = filename stem, source = `f"file:{name}"`; each `*.md`/`*.txt` → `kind="policy"`, `destinations=["resources"]`; plus `--catalog` flag ingesting `rsm_thrive/data/catalog/courses.json` (one document per course: title = `"<code> — <title>"`, source = `catalog:<code>`, `kind="catalog"`, `destinations=["resources", "courses"]`, text = description + offerings + notes). Prints one line per document: `ingested <source> (<n> chunks)`.

- [ ] **Step 1: Write the fixture and the failing tests**

`fixtures/corpus/handbook-excerpt.md`:

```markdown
# Dropping a course

Students may drop a course before the end of week two of the quarter without
a W appearing on the transcript. After week two, a drop requires approval
from the program office and the instructor.

# Laptop loans

Laptop loans for the quarter are handled by the Rady tech desk in room 2W108.
Requests are made through the student portal and approved within two business
days.
```

```python
# backend/rsm_thrive/tests/test_ingest.py
from pathlib import Path

import pytest

from rsm_thrive.models import Document, DocumentChunk
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.ingest import chunk_text, ingest_document

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"


class TestChunkText:
    def test_splits_on_headings(self):
        text = FIXTURES.joinpath("handbook-excerpt.md").read_text()
        chunks = chunk_text(text)
        assert [c["heading"] for c in chunks] == ["Dropping a course", "Laptop loans"]
        assert "week two" in chunks[0]["text"]

    def test_long_section_splits_with_overlap(self):
        paragraphs = "\n\n".join(f"Paragraph {i} " + "x" * 300 for i in range(10))
        chunks = chunk_text("# Big\n\n" + paragraphs, max_chars=800, overlap=100)
        assert len(chunks) > 1
        assert all(c["heading"] == "Big" for c in chunks)
        assert all(len(c["text"]) <= 800 for c in chunks)
        # the tail of one chunk reappears at the head of the next
        assert chunks[1]["text"][:50] in chunks[0]["text"]

    def test_preamble_before_first_heading_is_kept(self):
        chunks = chunk_text("intro line\n\n# H\n\nbody")
        assert chunks[0]["heading"] == "" and "intro" in chunks[0]["text"]


class TestIngestDocument:
    def test_creates_chunks_with_embeddings(self):
        text = FIXTURES.joinpath("handbook-excerpt.md").read_text()
        doc = ingest_document("test:handbook", "Handbook", "policy",
                              ["resources"], text, FakeEmbeddings())
        chunks = list(doc.chunks.all())
        assert len(chunks) == 2
        assert all(len(c.embedding) > 0 for c in chunks)
        assert chunks[0].seq == 0

    def test_rerun_replaces_not_duplicates(self):
        emb = FakeEmbeddings()
        ingest_document("test:h", "H", "policy", ["resources"], "# A\n\nfirst", emb)
        ingest_document("test:h", "H", "policy", ["resources"], "# B\n\nsecond", emb)
        assert Document.objects.filter(source="test:h").count() == 1
        assert DocumentChunk.objects.count() == 1
        assert DocumentChunk.objects.get().heading == "B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_ingest.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement `services/ingest.py`**

```python
# backend/rsm_thrive/services/ingest.py
"""Corpus ingestion: text -> heading-aware chunks -> embedded rows."""

import re

from django.db import transaction

from rsm_thrive.models import Document, DocumentChunk

_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def chunk_text(text, max_chars=1400, overlap=200):
    sections = []  # (heading, [lines])
    current = ("", [])
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append(current)
            current = (match.group(1).strip(), [])
        else:
            current[1].append(line)
    sections.append(current)

    chunks = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append({"heading": heading, "text": body})
            continue
        # split on paragraph boundaries, carrying `overlap` chars forward
        paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
        piece = ""
        for paragraph in paragraphs:
            if piece and len(piece) + 2 + len(paragraph) > max_chars:
                chunks.append({"heading": heading, "text": piece[:max_chars]})
                piece = piece[-overlap:]
            piece = (piece + "\n\n" + paragraph).strip() if piece else paragraph
        if piece:
            chunks.append({"heading": heading, "text": piece[:max_chars]})
    return chunks


def extract_pdf_text(path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


@transaction.atomic
def ingest_document(source, title, kind, destinations, text, embeddings):
    Document.objects.filter(source=source).delete()
    doc = Document.objects.create(source=source, title=title, kind=kind,
                                  destinations=destinations)
    chunks = chunk_text(text)
    if chunks:
        vectors = embeddings.embed([c["text"] for c in chunks])
        DocumentChunk.objects.bulk_create([
            DocumentChunk(document=doc, seq=seq, heading=c["heading"],
                          text=c["text"], embedding=vector)
            for seq, (c, vector) in enumerate(zip(chunks, vectors))
        ])
    return doc
```

- [ ] **Step 4: Implement the management command**

```python
# backend/rsm_thrive/management/commands/ingest_corpus.py
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from rsm_thrive.services.embeddings import get_embeddings
from rsm_thrive.services.ingest import extract_pdf_text, ingest_document

CATALOG = Path(__file__).resolve().parents[2] / "data" / "catalog" / "courses.json"


class Command(BaseCommand):
    help = "Ingest a corpus directory (PDF/md/txt) and optionally the course catalog."

    def add_arguments(self, parser):
        parser.add_argument("directory", nargs="?", default="")
        parser.add_argument("--catalog", action="store_true")

    def handle(self, *args, **options):
        embeddings = get_embeddings()
        directory = options["directory"]
        if not directory and not options["catalog"]:
            raise CommandError("Give a corpus directory, --catalog, or both.")

        if directory:
            root = Path(directory)
            if not root.is_dir():
                raise CommandError(f"{directory} is not a directory.")
            for path in sorted(root.iterdir()):
                if path.suffix.lower() == ".pdf":
                    text = extract_pdf_text(path)
                    kind, destinations = "syllabus", ["resources", "courses"]
                elif path.suffix.lower() in (".md", ".txt"):
                    text = path.read_text()
                    kind, destinations = "policy", ["resources"]
                else:
                    continue
                doc = ingest_document(f"file:{path.name}", path.stem, kind,
                                      destinations, text, embeddings)
                self.stdout.write(f"ingested file:{path.name} "
                                  f"({doc.chunks.count()} chunks)")

        if options["catalog"]:
            for course in json.loads(CATALOG.read_text()):
                parts = [course.get("description", "")]
                for offering in course.get("offerings", []):
                    parts.append(
                        f"Offered {offering.get('term', '')} "
                        f"with {offering.get('instructor', '')}. "
                        f"{offering.get('format_notes', '')}")
                if course.get("units_note"):
                    parts.append(course["units_note"])
                doc = ingest_document(
                    f"catalog:{course['code']}",
                    f"{course['code']} — {course['title']}",
                    "catalog", ["resources", "courses"],
                    "\n\n".join(p for p in parts if p), embeddings)
                self.stdout.write(f"ingested catalog:{course['code']} "
                                  f"({doc.chunks.count()} chunks)")
```

(The `data/catalog/courses.json` file itself lands in Task 4; until then `--catalog` simply isn't exercised by tests — the command imports the path lazily at call time.)

- [ ] **Step 5: Run tests, then the whole suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_ingest.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(c): heading-aware corpus ingestion command"
```

---

### Task 4: Electives engine port + catalog data

**Files:**
- Create: `backend/rsm_thrive/data/catalog/careers.json` (copy verbatim from `/Users/shankar/Documents/Rady Recommender/Old/recommender/catalog/careers.json`)
- Create: `backend/rsm_thrive/data/catalog/courses.json` (copy verbatim from `/Users/shankar/Documents/Rady Recommender/Old/recommender/catalog/courses.json`)
- Create: `backend/rsm_thrive/services/electives.py`
- Test: `backend/rsm_thrive/tests/test_electives.py`

**Interfaces:**
- Consumes: `Enrollment` (existing academic model), catalog JSONs.
- Produces:
  - `def load_catalog() -> list[dict]` and `def load_careers() -> dict` (module-level `@lru_cache`d readers).
  - `def rank_electives(catalog, profile, careers=None) -> list[dict]` — the deterministic scorer ported VERBATIM in behavior from `Old/recommender/src/matcher.py` (same weights: role weight `1.0/(1+0.5*pos)`, tag score `3.0/(1+pos)*tag_weight`, boost courses, tech/workload/interest adjustments — port the whole file, do not re-derive). Each result: `{"course": dict, "score": float, "reasons": [str]}` sorted descending, ties by course code.
  - `def recommend_for(user, career_roles, interests=None, limit=5) -> list[dict]` — builds the profile (`career_roles`, `interests`, defaults `technical_comfort=3`, `workload_preference="moderate"`), calls `rank_electives`, then drops courses whose `code` matches a `Course` the user has an `Enrollment` for (match on `Course.code` if the model has one, else on title prefix — check `models/academic.py` and match on the real field), and returns the top `limit`.

- [ ] **Step 1: Copy the catalog files**

```bash
mkdir -p backend/rsm_thrive/data/catalog
cp "/Users/shankar/Documents/Rady Recommender/Old/recommender/catalog/careers.json" backend/rsm_thrive/data/catalog/
cp "/Users/shankar/Documents/Rady Recommender/Old/recommender/catalog/courses.json" backend/rsm_thrive/data/catalog/
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_electives.py
import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import Enrollment
from rsm_thrive.services.electives import (
    load_careers, load_catalog, rank_electives, recommend_for)
from rsm_thrive.testing import make_course

pytestmark = pytest.mark.django_db


class TestCatalogData:
    def test_careers_and_catalog_load(self):
        careers = load_careers()
        assert "data-scientist" in careers
        catalog = load_catalog()
        assert any(c["code"] == "MGTA 453" for c in catalog)


class TestRankElectives:
    def test_deterministic(self):
        profile = {"career_roles": ["data-scientist"], "interests": ["ml"]}
        first = rank_electives(load_catalog(), profile, load_careers())
        second = rank_electives(load_catalog(), profile, load_careers())
        assert [r["course"]["code"] for r in first] == \
               [r["course"]["code"] for r in second]

    def test_core_courses_never_recommended(self):
        profile = {"career_roles": ["data-scientist"]}
        results = rank_electives(load_catalog(), profile, load_careers())
        assert all(not r["course"]["is_core"] for r in results)

    def test_role_changes_ranking(self):
        ds = rank_electives(load_catalog(),
                            {"career_roles": ["data-scientist"]}, load_careers())
        pm = rank_electives(load_catalog(),
                            {"career_roles": ["product-manager"]}, load_careers())
        assert [r["course"]["code"] for r in ds[:3]] != \
               [r["course"]["code"] for r in pm[:3]]

    def test_every_result_has_reasons(self):
        results = rank_electives(load_catalog(),
                                 {"career_roles": ["data-scientist"]},
                                 load_careers())
        assert all(r["reasons"] for r in results if r["score"] > 0)


class TestRecommendFor:
    def test_taken_courses_are_excluded_and_limit_applies(self):
        user = User.objects.create_user("stu")
        baseline = recommend_for(user, ["data-scientist"], limit=5)
        assert len(baseline) == 5
        top_code = baseline[0]["course"]["code"]

        course = make_course(code=top_code)
        Enrollment.objects.create(user=user, course=course)

        after = recommend_for(user, ["data-scientist"], limit=5)
        assert top_code not in [r["course"]["code"] for r in after]
```

Import `make_course` from `rsm_thrive.testing` (the existing factory: `make_course(id=None, **overrides)`; `Course.code` is a real CharField). `recommend_for` matches enrollments on `enrollment.course.code` — no `_code_of` indirection needed.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_electives.py -q`
Expected: FAIL with import errors.

- [ ] **Step 4: Implement `services/electives.py`**

Port `rank_electives` from `/Users/shankar/Documents/Rady Recommender/Old/recommender/src/matcher.py` — copy the function body, keep the scoring arithmetic identical, PEP8 it. Add:

```python
# backend/rsm_thrive/services/electives.py  (additions around the port)
import json
from functools import lru_cache
from pathlib import Path

from rsm_thrive.models import Enrollment

_DATA = Path(__file__).resolve().parent.parent / "data" / "catalog"


@lru_cache(maxsize=1)
def load_catalog():
    return json.loads((_DATA / "courses.json").read_text())


@lru_cache(maxsize=1)
def load_careers():
    return json.loads((_DATA / "careers.json").read_text())


def recommend_for(user, career_roles, interests=None, limit=5):
    profile = {
        "career_roles": career_roles,
        "career_tags": [],
        "technical_comfort": 3,
        "workload_preference": "moderate",
        "interests": interests or [],
    }
    ranked = rank_electives(load_catalog(), profile, load_careers())
    taken = _taken_codes(user)
    ranked = [r for r in ranked if r["course"]["code"] not in taken]
    return ranked[:limit]


def _taken_codes(user):
    return {
        enrollment.course.code
        for enrollment in Enrollment.objects.filter(user=user)
                                             .select_related("course")
    }
```

Sort ties in `rank_electives` by `(-score, course["code"])` so ordering is fully deterministic.

- [ ] **Step 5: Run tests, then the whole suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_electives.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(c): deterministic electives engine ported with catalog data"
```

---

### Task 5: FAQ and career bots

**Files:**
- Create: `backend/rsm_thrive/services/bots.py` (this task: shared helpers + `answer_faq` + `answer_career`)
- Test: `backend/rsm_thrive/tests/test_bots_faq.py`

**Interfaces:**
- Consumes: `retrieve` (Task 2), `bot_config` (Task 1), `LLM` instances passed in by the caller.
- Produces:
  - `@dataclass BotReply: body: str; chunk_ids: list[int]; model_note: str` (`model_note` is a short provenance string for the turn log: `"refusal"`, `"llm"`, `"clarify"`, `"engine+llm"`).
  - `def answer_faq(llm, question, history) -> BotReply` — `history` is `[{"role": "user"|"assistant", "content": str}, ...]` (already mapped from student/thrive, most recent last, WITHOUT the current question).
  - `def answer_career(llm, question, history) -> BotReply`
  - `def build_context(hits) -> str` — numbered passages: `"[1] <Document.title> — <heading>\n<text>"` joined by blank lines.
  - `def append_sources(body, hits) -> str` — appends `"\n\nSources: "` + unique document titles in first-retrieved order (skipped when `hits` is empty).

**Behavior (binding):**
- `answer_faq`: `retrieve(question, "resources", top_k, min_similarity)`. Empty → return `BotReply(config["refusal_reply"], [], "refusal")` with NO LLM call (deterministic, and a refusal that can't be sweet-talked). Non-empty → one `llm.chat(system_prompt + "\n\nContext passages:\n\n" + context, history + [question-as-user], json_mode=False)`, then `append_sources`.
- `answer_career`: `retrieve(question, "career", ...)`; empty retrieval is NOT a refusal — call the LLM with no context block (the prompt already says "answer from general best practice and say so"). Non-empty → same context flow as FAQ. Sources appended only when context was used.
- Both truncate `history` to the last `max_history_turns` entries.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_bots_faq.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_bots_faq.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement the two bots in `services/bots.py`**

```python
# backend/rsm_thrive/services/bots.py
"""The three destination bots. Pure functions over (llm, question, history)."""

from dataclasses import dataclass, field

from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.retrieval import retrieve


@dataclass
class BotReply:
    body: str
    chunk_ids: list = field(default_factory=list)
    model_note: str = "llm"


def build_context(hits):
    lines = []
    for n, (chunk, _score) in enumerate(hits, start=1):
        title = chunk.document.title
        head = f"[{n}] {title} — {chunk.heading}" if chunk.heading else f"[{n}] {title}"
        lines.append(f"{head}\n{chunk.text}")
    return "\n\n".join(lines)


def append_sources(body, hits):
    if not hits:
        return body
    titles = []
    for chunk, _score in hits:
        if chunk.document.title not in titles:
            titles.append(chunk.document.title)
    return f"{body}\n\nSources: {', '.join(titles)}"


def _trimmed(history, config):
    return history[-config["max_history_turns"]:]


def answer_faq(llm, question, history):
    config = bot_config("faq")
    hits = retrieve(question, "resources", config["top_k"], config["min_similarity"])
    if not hits:
        # Deterministic refusal: no context means no answer, and no LLM call
        # means the refusal cannot be argued with. Spec §5's binding rule.
        return BotReply(config["refusal_reply"], [], "refusal")
    system = f"{config['system_prompt']}\n\nContext passages:\n\n{build_context(hits)}"
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    body = llm.chat(system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "llm")


def answer_career(llm, question, history):
    config = bot_config("career")
    hits = retrieve(question, "career", config["top_k"], config["min_similarity"])
    system = config["system_prompt"]
    if hits:
        system = f"{system}\n\nContext passages:\n\n{build_context(hits)}"
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    body = llm.chat(system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "llm")
```

- [ ] **Step 4: Run tests, then the whole suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_bots_faq.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(c): FAQ bot (RAG + citations + deterministic refusal) and career bot"
```

---

### Task 6: Electives bot

**Files:**
- Modify: `backend/rsm_thrive/services/bots.py` (add `answer_electives`)
- Test: `backend/rsm_thrive/tests/test_bots_electives.py`

**Interfaces:**
- Consumes: `recommend_for`, `load_careers` (Task 4), `parse_llm_json` (Task 1), `retrieve`/`build_context`/`append_sources`/`BotReply`/`_trimmed` (Task 5).
- Produces: `def answer_electives(llm, user, question, history) -> BotReply` (note the extra `user` — the engine filters by their enrollments).

**Behavior (binding):**
1. **Extract**: one `llm.chat(extract_prompt-with-role-ids, history + question, json_mode=True)` → `parse_llm_json`. Role ids injected via `config["extract_prompt"].replace("{role_ids}", ", ".join(sorted(load_careers())))`. Career roles are sanitized: any id not in `load_careers()` is dropped.
2. **Clarify**: if `ready` is falsy or no valid role survives → `BotReply(envelope["reply"] or <fallback clarify copy>, [], "clarify")`. Fallback copy (when the envelope's reply is empty): `"What role are you aiming for after the program? Say something like 'data scientist' or 'product manager' and I can be specific."`
3. **Recommend**: `recommend_for(user, career_roles, interests, limit=config["max_recommendations"])`. Empty result (everything taken) → `BotReply` with body `"Based on your enrollments you've already covered the electives that fit that goal best — come chat with academic advising about what's next."`, note `"engine"`.
4. **Explain**: retrieve syllabus context for the top course codes — one `retrieve(" ".join(top codes + question), "courses", config["top_k"], config["min_similarity"])`. Build the engine block:
   `"Ranked recommendations (deterministic engine):\n1. <code> <title> — score <score:.1f> — reasons: <r1>; <r2>"` per course. Second `llm.chat(explain_prompt + "\n\n" + engine block + ("\n\nContext passages:\n\n" + context if hits else ""), history + question)` → `append_sources` → `BotReply(body, chunk_ids, "engine+llm")`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_bots_electives.py
import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.services.bots import answer_electives
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_bots_electives.py -q`
Expected: FAIL with `ImportError: answer_electives`.

- [ ] **Step 3: Implement `answer_electives`**

```python
# appended to backend/rsm_thrive/services/bots.py
from rsm_thrive.services.electives import load_careers, recommend_for
from rsm_thrive.services.llm import parse_llm_json

CLARIFY_FALLBACK = ("What role are you aiming for after the program? Say "
                    "something like 'data scientist' or 'product manager' "
                    "and I can be specific.")
ALL_COVERED = ("Based on your enrollments you've already covered the "
               "electives that fit that goal best — come chat with academic "
               "advising about what's next.")


def answer_electives(llm, user, question, history):
    config = bot_config("electives")
    careers = load_careers()

    extract_system = config["extract_prompt"].replace(
        "{role_ids}", ", ".join(sorted(careers)))
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    envelope = parse_llm_json(llm.chat(extract_system, messages, json_mode=True))

    roles = [r for r in (envelope.get("career_roles") or []) if r in careers]
    if not envelope.get("ready") or not roles:
        return BotReply(envelope.get("reply") or CLARIFY_FALLBACK, [], "clarify")

    interests = [i for i in (envelope.get("interests") or []) if isinstance(i, str)]
    ranked = recommend_for(user, roles, interests,
                           limit=config["max_recommendations"])
    if not ranked:
        return BotReply(ALL_COVERED, [], "engine")

    lines = []
    for n, entry in enumerate(ranked, start=1):
        course = entry["course"]
        reasons = "; ".join(entry["reasons"]) or "general fit"
        lines.append(f"{n}. {course['code']} {course['title']} — "
                     f"score {entry['score']:.1f} — reasons: {reasons}")
    engine_block = "Ranked recommendations (deterministic engine):\n" + "\n".join(lines)

    hits = retrieve(" ".join([e["course"]["code"] for e in ranked] + [question]),
                    "courses", config["top_k"], config["min_similarity"])
    explain_system = f"{config['explain_prompt']}\n\n{engine_block}"
    if hits:
        explain_system += f"\n\nContext passages:\n\n{build_context(hits)}"
    body = llm.chat(explain_system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "engine+llm")
```

- [ ] **Step 4: Run tests, then the whole suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_bots_electives.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(c): electives bot — LLM goal extraction, deterministic engine, grounded explanation"
```

---

### Task 7: Chat write endpoints + turn logging

**Files:**
- Modify: `backend/rsm_thrive/models/chat.py` (add `ChatTurnLog`)
- Modify: `backend/rsm_thrive/models/__init__.py` (export it)
- Create: migration `0014_chatturnlog.py` (via `makemigrations`)
- Modify: `backend/rsm_thrive/views/chat.py` (write endpoints + bot dispatch)
- Modify: `backend/rsm_thrive/urls.py` (route POSTs; existing GET routes stay)
- Test: `backend/rsm_thrive/tests/test_chat_write.py`
- Modify: `backend/rsm_thrive/tests/contract/` — add contract cases asserting POST responses validate against the existing CONVERSATION schema.

**Interfaces:**
- Consumes: `answer_faq`, `answer_career`, `answer_electives`, `BotReply` (Tasks 5–6), `get_llm` (Task 1), `conversation_payload` (existing).
- Produces:
  - `POST /api/thrive/conversations` body `{"destination": "...", "body": "..."}` → 201, full conversation payload (2 messages).
  - `POST /api/thrive/conversations/<id>/messages` body `{"body": "..."}` → 200, full conversation payload.
  - `ChatTurnLog(message: OneToOneField ChatMessage, bot: Char 16, model_note: Char 32, chunk_ids: JSONField list, duration_ms: Integer)`.
  - Module hook `views.chat.llm_factory = get_llm` — tests monkeypatch this to return a `FakeLLM`; the view calls `llm_factory()` per request.

**Behavior (binding):**
- Validation before any write: `destination` must be in the closed union (400 `bad_request`), `body` must be a non-empty string ≤ 4000 chars after strip (400 `bad_request`). Unknown/foreign conversation → 404 `unknown_conversation` (reuse `_own_conversation`).
- URL dispatch: the existing `conversations` view handles GET; make it dispatch on method (GET → list, POST → create). Same for `conversation` detail vs `.../messages` — add `path("conversations/<str:conversation_id>/messages", chat.conversation_messages)`. Non-allowed methods → 405 (use `require_http_methods(["GET", "POST"])` on the merged views).
- Title of a new conversation: first message body, stripped, hard-cut to 60 chars (append nothing — the mock titles are plain).
- Turn flow (both endpoints), inside one `transaction.atomic`: persist student `ChatMessage` → run the destination's bot → persist thrive `ChatMessage` → `ChatTurnLog` on the thrive message → bump `conversation.updated_at = timezone.now()` and save. History passed to bots: all prior messages mapped `student→user`, `thrive→assistant`, EXCLUDING the just-persisted student turn (it is passed as `question`).
- **Rescue the turn** (spec: fallback chains rescue, never 500): the bot call is wrapped; ANY exception → log at ERROR with the conversation id, and persist a thrive turn with body `DEGRADED_REPLY = "I'm having trouble reaching my knowledge sources right now. Your message is saved — try asking again in a minute."`, `model_note="degraded"`, empty chunk ids. The student turn stays. Response is still 201/200.
- Dispatch table: `{"resources": answer_faq, "career": answer_career}` take `(llm, question, history)`; `"courses"` → `answer_electives(llm, request.user, question, history)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_chat_write.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_chat_write.py -q`
Expected: FAIL (no ChatTurnLog, POST routes 405).

- [ ] **Step 3: Model + migration**

```python
# appended to backend/rsm_thrive/models/chat.py
class ChatTurnLog(models.Model):
    """Provenance for one assistant turn: which bot, which chunks, how long.

    The spec's diagnosability requirement: a wrong answer is traceable to the
    exact retrieved chunks in one look.
    """
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE,
                                   related_name="turn_log")
    bot = models.CharField(max_length=16)
    model_note = models.CharField(max_length=32)
    chunk_ids = models.JSONField(default=list)
    duration_ms = models.IntegerField(default=0)
```

Export from `models/__init__.py`; `uv run python manage.py makemigrations rsm_thrive` (expect `0014`).

- [ ] **Step 4: Views + urls**

```python
# backend/rsm_thrive/views/chat.py — rewritten module skeleton (keep the
# existing list/detail logic verbatim inside the new dispatchers)
import json
import logging
import time

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import (BadRequest, api_login_required, json_error,
                             json_ok, parse_body)
from rsm_thrive.models import ChatMessage, ChatTurnLog, Conversation
from rsm_thrive.serializers.chat import conversation_payload
from rsm_thrive.services.bots import BotReply, answer_career, answer_electives, answer_faq
from rsm_thrive.services.llm import get_llm

logger = logging.getLogger("rsm_thrive.chat")

VALID_DESTINATIONS = {"resources", "courses", "career"}
MAX_BODY = 4000
DEGRADED_REPLY = ("I'm having trouble reaching my knowledge sources right "
                  "now. Your message is saved — try asking again in a minute.")

# Module-level seam: tests monkeypatch this with a FakeLLM factory.
llm_factory = get_llm


def _validated_body(body):
    text = body.get("body")
    if not isinstance(text, str) or not text.strip():
        raise BadRequest("body must be a non-empty string.")
    text = text.strip()
    if len(text) > MAX_BODY:
        raise BadRequest(f"body must be at most {MAX_BODY} characters.")
    return text


def _history_of(conversation):
    return [
        {"role": "user" if m.role == "student" else "assistant", "content": m.body}
        for m in conversation.messages.all()
    ]


def _run_bot(user, destination, question, history):
    started = time.monotonic()
    try:
        llm = llm_factory()
        if destination == "courses":
            reply = answer_electives(llm, user, question, history)
        elif destination == "career":
            reply = answer_career(llm, question, history)
        else:
            reply = answer_faq(llm, question, history)
    except Exception:
        logger.exception("bot turn failed (destination=%s)", destination)
        reply = BotReply(DEGRADED_REPLY, [], "degraded")
    duration_ms = int((time.monotonic() - started) * 1000)
    return reply, duration_ms


def _append_turn(conversation, destination, question):
    """Student turn -> bot -> thrive turn -> log -> bump. One transaction."""
    history = _history_of(conversation)
    with transaction.atomic():
        ChatMessage.objects.create(conversation=conversation, role="student",
                                   body=question)
        reply, duration_ms = _run_bot(conversation.user, destination,
                                      question, history)
        assistant = ChatMessage.objects.create(conversation=conversation,
                                               role="thrive", body=reply.body)
        ChatTurnLog.objects.create(message=assistant, bot=destination,
                                   model_note=reply.model_note,
                                   chunk_ids=reply.chunk_ids,
                                   duration_ms=duration_ms)
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["updated_at"])


@api_login_required
@require_http_methods(["GET", "POST"])
def conversations(request):
    if request.method == "GET":
        # ... existing list body unchanged ...
        ...
    try:
        body = parse_body(request)
        destination = body.get("destination")
        if destination not in VALID_DESTINATIONS:
            raise BadRequest(
                f"destination must be one of {sorted(VALID_DESTINATIONS)}.")
        question = _validated_body(body)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    conversation_row = Conversation.objects.create(
        user=request.user, destination=destination, title=question[:60])
    _append_turn(conversation_row, destination, question)
    conversation_row = (Conversation.objects.filter(pk=conversation_row.pk)
                        .prefetch_related("messages").first())
    return json_ok(conversation_payload(conversation_row), status=201)


@api_login_required
@require_http_methods(["POST"])
def conversation_messages(request, conversation_id):
    row = _own_conversation(request.user, conversation_id)
    if row is None:
        return json_error("unknown_conversation",
                          f"No conversation {conversation_id}.", 404)
    try:
        question = _validated_body(parse_body(request))
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    _append_turn(row, row.destination, question)
    row = (Conversation.objects.filter(pk=row.pk)
           .prefetch_related("messages").first())
    return json_ok(conversation_payload(row))
```

One transaction note (binding): `_run_bot` performs network work; holding a DB transaction open across an LLM call is wrong. Restructure `_append_turn` as: persist the student turn in its own small transaction FIRST (the student's message must survive a bot crash), then run the bot with no transaction open, then persist assistant turn + log + bump in a second transaction. The docstring above is the naive shape — implement the two-transaction shape and test `test_llm_failure_rescues_the_turn` proves the student turn survives (extend it: assert the student message exists even when the bot degrades).

urls.py additions (keep `conversations` and `conversation` names):

```python
path("conversations/<str:conversation_id>/messages",
     chat.conversation_messages, name="conversation_messages"),
```

Route order: this literal-suffix path must be declared BEFORE `conversations/<str:conversation_id>`? No — `<str:...>` does not match across `/`, so order is safe either way; still, place `/messages` first to match the repo's `tasks/order` convention.

- [ ] **Step 5: Contract test additions**

In the existing contract suite add two cases: POST create response validates against the CONVERSATION schema; POST message response validates too (reuse the schema — the payload shape is unchanged). Follow the suite's existing pattern for authenticated contract cases, installing a FakeLLM via the same monkeypatch seam.

- [ ] **Step 6: Run tests, then the whole suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend && git commit -m "feat(c): chat write endpoints with bot dispatch, turn rescue, and turn logging"
```

---

### Task 8: Frontend write path

**Files:**
- Modify: `frontend/src/lib/data/api/providers.ts` (add `createConversation`, `sendConversationMessage`)
- Modify: `frontend/src/lib/data/api/providers.spec.ts` (cover both)
- Create: `frontend/src/routes/ask-sync/+server.ts` (same-origin proxy)
- Create: `frontend/src/routes/ask-sync/server.spec.ts`
- Modify: `frontend/src/routes/ask/[destination]/+page.server.ts` (pass `live`)
- Modify: `frontend/src/lib/components/ask/ChatWindow.svelte` (live send path)
- Modify: `frontend/src/lib/messages.ts` (live copy: pending label, error reply, live intro)
- Modify: `frontend/src/routes/ask/+layout.svelte` or wherever `intro` renders — switch copy on `live` (locate with grep `ask.intro`).

**Interfaces:**
- Consumes: `apiFetch`, `apiEnabled`, `ApiError` (existing api client); `Conversation` type.
- Produces:
  - `api.createConversation(destination: AskDestination, body: string): Promise<Conversation>` → `apiFetch("/conversations", { method: "POST", body: { destination, body } })`.
  - `api.sendConversationMessage(conversationId: string, body: string): Promise<Conversation>` → `apiFetch(`/conversations/${encodeURIComponent(conversationId)}/messages`, { method: "POST", body: { body } })`.
  - `POST /ask-sync` accepting `{"action": "create", "destination", "body"}` or `{"action": "message", "conversationId", "body"}` → `{ conversation }` JSON, ApiError envelopes passed through with status (the overlay-sync pattern, closed action list, unknown action 400, `apiEnabled()` false → 404).
  - NOT added to `data/providers.ts`'s delegator list: these are write providers with no mock counterpart — mock mode's ChatWindow behavior is deliberately unchanged, so the delegator seam does not apply. Import them in `/ask-sync` from `$lib/data/api/providers` directly (matching how `overlay-sync` imports `apiFetch` directly rather than going through delegators).

**ChatWindow behavior (binding):**
- New prop `live: boolean` (from page data; `+page.server.ts` returns `live: apiEnabled()` — import `apiEnabled` from `$lib/data/api/client`; the ask layout load passes it through if the intro renders in the layout).
- `live === false`: the current behavior byte-for-byte (placeholder reply, session-local `sent`).
- `live === true` submit flow:
  1. Push the student bubble optimistically into `sent`, clear the draft, set `pending = true` (composer disabled, a "THRIVE is thinking…" status line with `aria-live` handled by the existing log's `role="log"` — render it as a thrive-side bubble with the pending copy).
  2. `fetch("/ask-sync", { method: "POST", ... })` with `action: conversation ? "message" : "create"`.
  3. On ok: `await goto(\`/ask/${destination}?c=${payload.conversation.id}\`, { invalidateAll: true })` — the server reload renders both persisted turns and the rail's history updates; then clear `sent` and `pending` (the `{#key}` remount clears them anyway for a new conversation; clear explicitly for the same-conversation case where the id doesn't change).
  4. On failure (non-ok or thrown): keep the student bubble, `pending = false`, append a thrive bubble with `messages.ask.chat.errorReply` copy. Never lose the draft's content (it's in the bubble).
- Copy additions to `messages.ts` under `ask.chat`: `pendingReply: 'Thinking…'`, `errorReply: 'Something went wrong sending that. Your message is shown above — try again in a moment.'`; under `ask`: `introLive: 'Three places to ask, depending on what you need. Answers come from the program's own material — conversations are saved to your account.'`. The intro site renders `live ? copy.introLive : copy.intro`.

- [ ] **Step 1: Write the failing provider + proxy specs**

Add to `providers.spec.ts` (follow the existing write-provider test pattern in that file):

```typescript
it("createConversation POSTs destination and body", async () => {
  const impl = stubFetch(201, { id: "conv-9", destination: "career",
    title: "q", messages: [], updatedAt: "2026-08-23T09:00:00-07:00" });
  const result = await runWithAuth(AUTH, () =>
    api.createConversation("career", "resume length?"));
  const [url, init] = impl.mock.calls[0];
  expect(url).toBe("http://api.test/api/thrive/conversations");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual(
    { destination: "career", body: "resume length?" });
  expect(result.id).toBe("conv-9");
});

it("sendConversationMessage POSTs to the conversation", async () => {
  const impl = stubFetch(200, { id: "conv-9", destination: "career",
    title: "q", messages: [], updatedAt: "2026-08-23T09:00:00-07:00" });
  await runWithAuth(AUTH, () => api.sendConversationMessage("conv-9", "more"));
  const [url, init] = impl.mock.calls[0];
  expect(url).toBe("http://api.test/api/thrive/conversations/conv-9/messages");
  expect(JSON.parse(init.body as string)).toEqual({ body: "more" });
});
```

`ask-sync/server.spec.ts` mirrors `overlay-sync/server.spec.ts` structure:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { POST } from "./+server";

function stubFetch(status = 201, payload: unknown = {}) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300, status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function call(body: unknown) {
  const request = new Request("http://localhost/ask-sync", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return runWithAuth({ cookie: "sessionid=s; csrftoken=t", student: null },
    () => POST({ request } as Parameters<typeof POST>[0]));
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("POST /ask-sync", () => {
  it("create forwards to POST /conversations and wraps the payload", async () => {
    const impl = stubFetch(201, { id: "conv-3" });
    const response = await call({ action: "create", destination: "career",
                                  body: "hi" });
    expect(response.status).toBe(200);
    expect((await response.json()).conversation.id).toBe("conv-3");
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/conversations");
    expect(init.method).toBe("POST");
    expect(init.headers["x-csrftoken"]).toBe("t");
  });

  it("message forwards to the conversation's messages", async () => {
    const impl = stubFetch(200, { id: "conv-3" });
    await call({ action: "message", conversationId: "conv-3", body: "more" });
    expect(impl.mock.calls[0][0])
      .toBe("http://api.test/api/thrive/conversations/conv-3/messages");
  });

  it("unknown action 400s; ApiError envelopes pass through", async () => {
    stubFetch();
    expect((await call({ action: "nope" })).status).toBe(400);
    stubFetch(404, { error: { code: "unknown_conversation", message: "x" } });
    const missing = await call({ action: "message", conversationId: "conv-99",
                                 body: "q" });
    expect(missing.status).toBe(404);
    expect((await missing.json()).error.code).toBe("unknown_conversation");
  });

  it("404s when api mode is off", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    expect((await call({ action: "create", destination: "career", body: "q" }))
      .status).toBe(404);
  });
});
```

- [ ] **Step 2: Run specs to verify they fail**

Run: `cd frontend && npx vitest run src/routes/ask-sync src/lib/data/api/providers.spec.ts`
Expected: FAIL.

- [ ] **Step 3: Implement providers and proxy**

`api/providers.ts` additions (match the file's existing style and section comments):

```typescript
export function createConversation(
	destination: AskDestination,
	body: string,
): Promise<Conversation> {
	return apiFetch<Conversation>("/conversations", {
		method: "POST",
		body: { destination, body },
	});
}

export function sendConversationMessage(
	conversationId: string,
	body: string,
): Promise<Conversation> {
	return apiFetch<Conversation>(
		`/conversations/${encodeURIComponent(conversationId)}/messages`,
		{ method: "POST", body: { body } },
	);
}
```

(Check `apiFetch`'s options signature in `api/client.ts` first — if it takes a pre-serialized body or different option names, follow the real signature; `overlay-sync/+server.ts`'s call is the working example.)

`ask-sync/+server.ts`:

```typescript
/**
 * Same-origin proxy for the chat composer.
 *
 * Same shape and reasons as /overlay-sync: a client component cannot reach
 * Django cross-origin with credentials, so this route turns a small closed
 * set of actions into authenticated apiFetch calls. Unlike overlay-sync the
 * response body matters — the caller needs the persisted conversation back.
 */
import { json } from "@sveltejs/kit";

import { ApiError, apiEnabled } from "$lib/data/api/client";
import { createConversation, sendConversationMessage } from "$lib/data/api/providers";
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ request }) => {
	if (!apiEnabled()) {
		return json({ error: { code: "api_disabled", message: "API mode is off." } },
			{ status: 404 });
	}
	const payload = (await request.json()) as Record<string, unknown>;
	try {
		if (payload.action === "create") {
			const conversation = await createConversation(
				payload.destination as never, String(payload.body ?? ""));
			return json({ conversation });
		}
		if (payload.action === "message") {
			const conversation = await sendConversationMessage(
				String(payload.conversationId ?? ""), String(payload.body ?? ""));
			return json({ conversation });
		}
	} catch (error) {
		if (error instanceof ApiError) {
			return json({ error: { code: error.code, message: error.message } },
				{ status: error.status });
		}
		throw error;
	}
	return json({ error: { code: "unknown_action",
		message: `Unknown action: ${String(payload.action)}` } }, { status: 400 });
};
```

- [ ] **Step 4: Wire ChatWindow's live path and copy**

Follow the binding behavior above. Read the whole component first; keep the mock path untouched; add `live` prop threading from `+page.server.ts` (`live: apiEnabled()`) through `+page.svelte`. Find where `messages.ask.intro` renders (grep) and switch on `live` there, passing `live` through that surface's load if it's the layout. Add the three copy entries. `goto` comes from `$app/navigation`.

- [ ] **Step 5: Run all frontend gates**

Run: `cd frontend && npm test && npm run check && npm run build`
Expected: all green, check 0 errors 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add frontend && git commit -m "feat(c): live chat composer — ask-sync proxy, write providers, pending/error states"
```

---

### Task 9: Eval harness, gates, e2e smoke

**Files:**
- Create: `backend/rsm_thrive/data/evals/faq_golden.json`
- Create: `backend/rsm_thrive/management/commands/eval_bots.py`
- Test: `backend/rsm_thrive/tests/test_eval_command.py`
- Modify: `backend/README.md` (corpus ingestion + eval run + THRIVE_LLM/GEMINI_API_KEY docs — a short section, follow the README's existing tone)

**Interfaces:**
- Consumes: `answer_faq` (Task 5), `FakeLLM`/`get_llm` (Task 1).
- Produces: `uv run python manage.py eval_bots [--llm fake|real]` — runs every golden case through `answer_faq` with real retrieval; prints per-case `PASS`/`FAIL` with the retrieved chunk ids; exits non-zero on any failure.

**Golden set** (`faq_golden.json` — grows over time; these six seed it):

```json
[
  {"id": "drop-deadline", "question": "When can I drop a course without a W?",
   "must_contain": ["week two"], "must_refuse": false},
  {"id": "drop-approval", "question": "Who approves a drop after week two?",
   "must_contain": ["program office"], "must_refuse": false},
  {"id": "laptop", "question": "Where do I request a laptop loan?",
   "must_contain": ["tech desk"], "must_refuse": false},
  {"id": "off-topic-refusal", "question": "What's the best pizza in La Jolla?",
   "must_contain": [], "must_refuse": true},
  {"id": "policy-refusal", "question": "Can I get a tuition refund in week 9?",
   "must_contain": [], "must_refuse": true},
  {"id": "visa-refusal", "question": "How do I extend my visa after graduating?",
   "must_contain": [], "must_refuse": true}
]
```

**Command behavior (binding):**
- `--llm fake` (default): `FakeLLM` scripted to echo the context — build the fake reply per case as the concatenated retrieved chunk texts (so `must_contain` checks retrieval quality deterministically); refusal cases pass when the bot returns the refusal reply (`model_note == "refusal"`).
- `--llm real`: `get_llm()` (needs `GEMINI_API_KEY` and `THRIVE_LLM` unset/gemini); `must_contain` checked case-insensitively against the LLM's body.
- A `must_refuse: false` case whose retrieval comes back empty is a FAIL (labeled `no-retrieval`), because the corpus is missing material — the diagnosable failure mode the spec calls out.
- Output per case: `PASS drop-deadline (chunks: 12, 14)` / `FAIL off-topic-refusal: answered instead of refusing (chunks: 3)`. Summary line + `sys.exit(1)` on failures (use `CommandError` or `self.stderr` + raise).
- The eval requires an ingested corpus; with an empty knowledge table it prints a clear one-line hint (`run ingest_corpus first`) and exits 1.

- [ ] **Step 1: Write the failing test**

```python
# backend/rsm_thrive/tests/test_eval_command.py
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.ingest import ingest_document

pytestmark = pytest.mark.django_db

HANDBOOK = """# Dropping a course

Students may drop a course before the end of week two without a W. After
week two, a drop requires approval from the program office.

# Laptop loans

Laptop loans are handled by the Rady tech desk in room 2W108.
"""


def test_eval_passes_on_seeded_corpus(capsys):
    ingest_document("test:handbook", "MSBA Handbook", "policy", ["resources"],
                    HANDBOOK, FakeEmbeddings())
    call_command("eval_bots", "--llm", "fake")
    out = capsys.readouterr().out
    assert "PASS drop-deadline" in out
    assert "PASS off-topic-refusal" in out
    assert "FAIL" not in out


def test_eval_fails_loudly_on_empty_corpus():
    with pytest.raises(CommandError):
        call_command("eval_bots", "--llm", "fake")
```

(If a golden case turns out not to pass against the fixture corpus with fake embeddings — e.g. the refusal threshold catches a legit question — tune `min_similarity` in `config/bots.json` or the golden set until the seeded eval is green and refusals still refuse. That tuning loop is the harness working, not a test hack; record what moved in the commit message.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_eval_command.py -q`
Expected: FAIL (unknown command).

- [ ] **Step 3: Implement `eval_bots.py`**

```python
# backend/rsm_thrive/management/commands/eval_bots.py
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from rsm_thrive.models import DocumentChunk
from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.bots import answer_faq
from rsm_thrive.services.llm import FakeLLM, get_llm
from rsm_thrive.services.retrieval import retrieve

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "evals" / "faq_golden.json"


class Command(BaseCommand):
    help = "Run the golden FAQ set through the bot; fails on any regression."

    def add_arguments(self, parser):
        parser.add_argument("--llm", choices=["fake", "real"], default="fake")

    def handle(self, *args, **options):
        if not DocumentChunk.objects.exists():
            raise CommandError("The knowledge table is empty — run ingest_corpus first.")
        cases = json.loads(GOLDEN.read_text())
        config = bot_config("faq")
        failures = 0
        for case in cases:
            if options["llm"] == "fake":
                hits = retrieve(case["question"], "resources",
                                config["top_k"], config["min_similarity"])
                llm = FakeLLM(replies=[" ".join(c.text for c, _ in hits) or "?"])
            else:
                llm = get_llm()
            reply = answer_faq(llm, case["question"], [])
            chunks = ", ".join(str(i) for i in reply.chunk_ids) or "none"
            refused = reply.model_note == "refusal"
            if case["must_refuse"]:
                ok, why = refused, "answered instead of refusing"
            elif refused:
                ok, why = False, "refused instead of answering (no-retrieval?)"
            elif not reply.chunk_ids:
                ok, why = False, "no-retrieval"
            else:
                missing = [kw for kw in case["must_contain"]
                           if kw.lower() not in reply.body.lower()]
                ok, why = not missing, f"missing {missing}"
            if ok:
                self.stdout.write(f"PASS {case['id']} (chunks: {chunks})")
            else:
                failures += 1
                self.stdout.write(f"FAIL {case['id']}: {why} (chunks: {chunks})")
        self.stdout.write(f"{len(cases) - failures}/{len(cases)} passed")
        if failures:
            raise CommandError(f"{failures} eval case(s) failed.")
```

- [ ] **Step 4: Run the test, tune until green**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_eval_command.py -q`
Expected: PASS (tune `min_similarity`/golden keywords if not — see Step 1's note).

- [ ] **Step 5: Full gates**

Run: `cd backend && uv run pytest -q` and `cd frontend && npm test && npm run check && npm run build`.
Expected: everything green, 0 warnings.

- [ ] **Step 6: e2e smoke (deterministic, no API key)**

From the repo root, using the SAME hostname (localhost) for both servers:

```bash
cd backend
uv run python manage.py migrate
uv run python manage.py seed_demo
THRIVE_LLM=fake uv run python manage.py ingest_corpus rsm_thrive/tests/fixtures/corpus --catalog
# THRIVE_LLM=fake makes get_llm() raise, proving the degraded path end-to-end:
THRIVE_LLM=fake THRIVE_DEV_LOGIN_ENABLED=1 uv run python manage.py runserver &
cd ../frontend && THRIVE_API_ORIGIN=http://localhost:8000 npm run dev &
```

Smoke steps (curl with a cookie jar, dev-login as demo/demo):
1. `POST /api/thrive/conversations` `{"destination":"resources","body":"When can I drop a course?"}` → 201 with two messages; with `THRIVE_LLM=fake` the assistant body is the DEGRADED reply — proving turn rescue.
2. Restart Django WITHOUT `THRIVE_LLM` but with a real `GEMINI_API_KEY` if available (`ls ~/.gemini 2>/dev/null; echo $GEMINI_API_KEY` to check; the old project used one) → repeat step 1 → a real grounded answer with `Sources:`. If no key is available, skip and note it in the report — the fake-path smoke plus unit coverage stands.
3. GET `/api/thrive/conversations` → the new conversation is first with `updatedAt` fresh.
4. Browser check via the frontend: `/ask/resources`, send a message, watch it navigate to `?c=conv-N` with both turns rendered and the rail updated.
5. Kill both servers (captured PIDs, `kill` not `pkill`).

- [ ] **Step 7: README + commit**

```bash
git add backend frontend && git commit -m "feat(c): golden-set eval harness, docs, and e2e smoke"
```

---

## Deferred / carried

- **ai_service adapter**: F5, once Vincent grants access (VINCENT-ASKS #4) — slot `AiServiceLLM(LLM)` into `services/llm.py`, switch `THRIVE_LLM=ai_service`.
- **pgvector**: F5 if the corpus outgrows the Python scan (swap `retrieval.py` internals; interface unchanged). Needs `CREATE EXTENSION` (VINCENT-ASKS #3).
- **Scraped Rady/UCSD pages + scheduled refresh**: needs Celery on the server (F5); `ingest_corpus` re-runs are already idempotent, so the cron is just a scheduled invocation.
- **Real syllabus PDF ingestion**: the 25 MGTA PDFs live outside the repo at `/Users/shankar/Documents/Rady Recommender/Old/MGTA/` — run `ingest_corpus` against that directory locally and on the server; the repo carries only the small test fixture. Document in README.
- **Program handbook PDF**: not currently on disk — ask the user for it; `program_rules.json` and the catalog cover part of the gap meanwhile.
- **Canvas-taken-courses**: `recommend_for` filters by `Enrollment`, which F3 will populate from Canvas; today it holds seed data (fine for the demo).
- **F5 note carried from spec**: LLM summaries make the resume `summaryChanged` flag nearly-always-true (recorded in the F2b review; Phase C does not touch resume summaries — the note transfers to whichever phase wires them).
- **Quarter-offered filter** (spec §5): v1 ranks all electives regardless of term — "which quarter" needs a current-term source the app doesn't have yet (F3/Canvas). The catalog chunks carry offerings text, so the explanation LLM can already speak to timing; the hard filter lands with F3.
- **Streaming (SSE)**: the URL design admits it later without moving endpoints; v1 is synchronous like the UI.
