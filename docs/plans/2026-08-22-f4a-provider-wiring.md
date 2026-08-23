# F4a — Provider-to-API Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the SvelteKit frontend run on the real Django API behind an authenticated session — every one of the 27 provider functions gains an HTTP implementation selected by one environment variable, with the mock path remaining the default so the repo's gates and 640 unit tests keep their meaning.

**Architecture:** Django first grows the three things wiring needs: a `profile_required` guard (closes the known 500 for authenticated-but-profile-less users across ALL `thrive_profile` call sites), a DEBUG-style dev login (LDAP arrives only on the server), and the missing conversations read endpoints. Then the frontend gets a server-only API client (cookie + CSRF forwarding via `AsyncLocalStorage` per-request context), an `api/providers.ts` twin of every provider with the contract's error translations, a one-line-per-provider delegation switch in `providers.ts` (`THRIVE_API_ORIGIN` set → API, unset → mock), and a `hooks.server.ts` auth gate. Finished with the full gate suite plus a scripted end-to-end smoke (login → dashboard with real data).

**Tech Stack:** Django ≥5.2 (backend, uv), SvelteKit 2 / TypeScript strict / Vitest (frontend, npm, Node ≥20 — local Node is v24).

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §2 (identity & request flow). Semantics: `frontend/src/lib/data/providers.ts` (all bodies), `types.ts`. Out of scope: localStorage-store migration (F4b), base-path + production CSRF origin (F5), chat writes/LLM (Phase C).

## Global Constraints

- **The provider surface does not move**: `frontend/src/lib/data/index.ts` is untouched; all 27 exported signatures stay byte-identical; components/loads/actions are not edited except the two named integration points (hooks, appointments action auth check).
- **Mock is the default**: with `THRIVE_API_ORIGIN` unset, every provider runs its existing mock body — `npm test` (640 tests), all six gates, and the timezone sweep must stay green with no env vars set.
- Error translations are contract text: booking 409 (and code `slot_unknown` 404) → `throw SlotUnavailableError(server message verbatim)`; 404 → `null` for `cancelAppointment`, `submitRequest`, `setCurrentVersion`, `getConversation`, `getCurrentResume` (code `no_resume`); TSS payloads unwrap `{"connected": bool}` to the bare boolean the contract expects; `generateNewVersion` passes `{version, diff}` through.
- API code is server-only: the client lives under `src/lib/data/api/` and reads the incoming request's cookie from `src/lib/server/requestContext.ts` (AsyncLocalStorage); nothing under `api/` or `server/` may be imported by a `.svelte` component.
- CSRF for unsafe methods: Django's `/me` gains `@ensure_csrf_cookie`; the client echoes the `csrftoken` cookie value as an `x-csrftoken` header on non-GET.
- Backend: error envelope everywhere; authenticated-but-profile-less → **403 code `no_profile`** (never 500) on every endpoint that touches `thrive_profile`. Conversations: id spaces `conv-<pk>` / `msg-<pk>`; destination enum verbatim `resources|courses|career`; list sorted `updatedAt` desc (NOT filtered by destination — providers.ts:547).
- All backend commands from `backend/` via `uv run`; all frontend commands from `frontend/` via npm (run `npm ci` once first — node_modules is not checked out). Commit per task on `main`.

---

### Task 1: Django — `profile_required` guard across all thrive_profile call sites

**Files:**
- Modify: `backend/rsm_thrive/http.py`, `backend/rsm_thrive/views/students.py`, `backend/rsm_thrive/views/events.py`, `backend/rsm_thrive/views/degree.py`, `backend/rsm_thrive/views/requests.py`, `backend/rsm_thrive/views/resume.py`
- Test: `backend/rsm_thrive/tests/test_no_profile.py`

**Interfaces:**
- Produces in `http.py`: `profile_required(view)` — decorator for use UNDER `api_login_required`; resolves `request.user.thrive_profile`, on `StudentProfile.DoesNotExist` returns `json_error("no_profile", "No student profile for this account.", 403)`, else sets `request.thrive_profile` and calls the view.
- Every view that previously read `request.user.thrive_profile` now carries `@profile_required` and reads `request.thrive_profile`: `students.me`, `events.events`, `degree.timeline`, `degree.progress`, `requests.prefill`, `requests.create_request`, `requests.tss`, `requests.tss_connect`, `resume.generate_version_view`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_no_profile.py`:

```python
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

PROFILE_ENDPOINTS = [
    ("get", "/api/thrive/me"),
    ("get", "/api/thrive/events"),
    ("get", "/api/thrive/degree/timeline"),
    ("get", "/api/thrive/degree/progress"),
    ("get", "/api/thrive/requests/prefill"),
    ("get", "/api/thrive/tss"),
    ("post", "/api/thrive/tss/connect"),
    ("post", "/api/thrive/resume/versions"),
]


@pytest.mark.parametrize("method,path", PROFILE_ENDPOINTS)
def test_profileless_user_gets_403_not_500(client, method, path):
    bare = get_user_model().objects.create_user(username="staffonly")
    client.force_login(bare)
    resp = getattr(client, method)(path)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "no_profile"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_no_profile.py -v`
Expected: FAILs with 500s (RelatedObjectDoesNotExist).

- [ ] **Step 3: Implement**

Append to `backend/rsm_thrive/http.py`:

```python
def profile_required(view):
    """Use under api_login_required: guarantees request.thrive_profile."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        from rsm_thrive.models import StudentProfile
        try:
            request.thrive_profile = request.user.thrive_profile
        except StudentProfile.DoesNotExist:
            return json_error("no_profile", "No student profile for this account.", 403)
        return view(request, *args, **kwargs)
    return wrapper
```

In each listed view: add `@profile_required` directly below `@api_login_required` (and below any `@require_http_methods`), import it, and replace every `request.user.thrive_profile` with `request.thrive_profile`. Example (`views/students.py`):

```python
from rsm_thrive.http import api_login_required, json_ok, profile_required
from rsm_thrive.serializers.students import student_payload


@api_login_required
@profile_required
def me(request):
    return json_ok(student_payload(request.thrive_profile))
```

Note: `requests.create_request` is dispatched via `requests_dispatch` — decorate `create_request`, `my_requests` untouched (it queries by `request.user`, no profile). Do NOT decorate views that never touch the profile.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS (111 existing + 8 new).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "fix(backend): 403 no_profile instead of 500 across profile endpoints"
```

---

### Task 2: Django — dev login + CSRF cookie on /me

**Files:**
- Create: `backend/rsm_thrive/views/auth.py`
- Modify: `backend/config/settings.py`, `backend/rsm_thrive/views/students.py`, `backend/rsm_thrive/urls.py`, `backend/rsm_thrive/management/commands/seed_demo.py`
- Test: `backend/rsm_thrive/tests/test_dev_login.py`

**Interfaces:**
- Produces: `GET|POST /api/thrive/dev-login` — minimal HTML login form (DEBUG-substitute for LDAP; gated by `settings.THRIVE_DEV_LOGIN_ENABLED`, env `THRIVE_DEV_LOGIN` default `"1"`). POST authenticates and redirects to a SAFE `next` (relative paths always; absolute only when prefixed by an origin in `settings.THRIVE_FRONTEND_ORIGINS`, env `THRIVE_FRONTEND_ORIGINS` comma-separated, default `"http://localhost:5173,http://localhost:3000,http://localhost:3123"`); anything else falls back to `/`. Disabled → 404 envelope.
- `/me` gains `@ensure_csrf_cookie` (outermost) so API clients receive the `csrftoken` cookie.
- `seed_demo` gives the demo user a password: `demo`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_dev_login.py`:

```python
import pytest
from django.test import override_settings

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db
LOGIN = "/api/thrive/dev-login"


def _student_with_password(username="ada", password="pw"):
    profile = make_student(username=username)
    profile.user.set_password(password)
    profile.user.save()
    return profile


def test_login_roundtrip_relative_next(client):
    _student_with_password()
    page = client.get(f"{LOGIN}?next=/after")
    assert page.status_code == 200 and b"<form" in page.content

    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": "/after"})
    assert resp.status_code == 302 and resp["Location"] == "/after"
    assert client.get("/api/thrive/me").status_code == 200  # session established


def test_login_allows_frontend_origin_and_blocks_others(client):
    _student_with_password()
    good = "http://localhost:5173/calendar"
    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": good})
    assert resp["Location"] == good

    client.logout()
    evil = "https://evil.example/phish"
    resp = client.post(LOGIN, {"username": "ada", "password": "pw", "next": evil})
    assert resp["Location"] == "/"


def test_bad_credentials_reshow_form(client):
    _student_with_password()
    resp = client.post(LOGIN, {"username": "ada", "password": "nope", "next": "/"})
    assert resp.status_code == 200 and b"Wrong username or password" in resp.content


@override_settings(THRIVE_DEV_LOGIN_ENABLED=False)
def test_disabled_login_404s(client):
    assert client.get(LOGIN).status_code == 404


def test_me_sets_csrf_cookie(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/me")
    assert "csrftoken" in resp.cookies
```

- [ ] **Step 2: Run to verify failure** — Expected: 404s.

- [ ] **Step 3: Implement**

`backend/config/settings.py` (near the bottom):

```python
THRIVE_DEV_LOGIN_ENABLED = os.environ.get("THRIVE_DEV_LOGIN", "1") == "1"
THRIVE_FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "THRIVE_FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:3123",
    ).split(",")
    if origin.strip()
]
```

`backend/rsm_thrive/views/auth.py`:

```python
"""Dev-only session login. On the server, UCSD LDAP replaces this (F5)."""
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.html import escape

from rsm_thrive.http import json_error


def _safe_next(next_url: str) -> str:
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    for origin in settings.THRIVE_FRONTEND_ORIGINS:
        if next_url == origin or next_url.startswith(origin + "/"):
            return next_url
    return "/"


def dev_login(request):
    if not settings.THRIVE_DEV_LOGIN_ENABLED:
        return json_error("not_found", "No such page.", 404)
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    error = ""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", ""),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(_safe_next(next_url))
        error = "<p>Wrong username or password.</p>"
    token = get_token(request)
    html = (
        "<!doctype html><meta charset='utf-8'><title>THRIVE dev login</title>"
        "<h1>THRIVE dev login</h1>" + error +
        "<form method='post'>"
        f"<input type='hidden' name='csrfmiddlewaretoken' value='{token}'>"
        f"<input type='hidden' name='next' value='{escape(next_url)}'>"
        "<p><label>Username <input name='username' autofocus></label></p>"
        "<p><label>Password <input type='password' name='password'></label></p>"
        "<p><button>Sign in</button></p></form>"
    )
    return HttpResponse(html)
```

`views/students.py`: add `from django.views.decorators.csrf import ensure_csrf_cookie` and stack `@ensure_csrf_cookie` ABOVE `@api_login_required` on `me`.

`urls.py`: import `auth` (alphabetical) and add `path("dev-login", auth.dev_login, name="dev-login")` (alphabetically among the paths).

`seed_demo.py`: after creating the demo profile, add:

```python
        profile.user.set_password("demo")
        profile.user.save(update_fields=["password"])
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat(backend): dev login and csrf cookie on /me"
```

---

### Task 3: Django — conversations read endpoints

**Files:**
- Create: `backend/rsm_thrive/models/chat.py`, `backend/rsm_thrive/serializers/chat.py`, `backend/rsm_thrive/views/chat.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`, `backend/rsm_thrive/urls.py`, `backend/rsm_thrive/tests/contract/schemas.py`, `backend/rsm_thrive/tests/contract/test_contract.py`, `backend/rsm_thrive/management/commands/seed_demo.py`
- Test: `backend/rsm_thrive/tests/test_conversations.py`

**Interfaces:**
- Models: `Conversation(user FK, destination: Char16 choices resources|courses|career, title: Char200, updated_at: DateTime default timezone.now)`; `ChatMessage(conversation FK related_name="messages", role: Char16 choices student|thrive, body: Text, sent_at: DateTime default timezone.now)` with `Meta.ordering = ["sent_at", "pk"]`.
- Serializer `conversation_payload(conversation) -> dict`: `{id "conv-<pk>", destination, title, messages: [{id "msg-<pk>", role, body, sentAt}], updatedAt}`.
- Routes: `GET /api/thrive/conversations` (own, order `-updated_at, -pk`, NOT filtered by destination, messages included); `GET /api/thrive/conversations/conv-<pk>` (own; unknown/malformed → 404 `unknown_conversation`; same `isascii()+isdigit()` guard pattern).
- Factories: `make_conversation(profile, **overrides)` (defaults destination "resources", title "Conversation <n>", updated_at now); `make_message(conversation, **overrides)` (defaults role "student", body "hello", sent_at now).
- Contract: schemas `CHAT_MESSAGE` (all 4 required; role enum `["student","thrive"]`; sentAt ISO_INSTANT) and `CONVERSATION` (all 5 required; destination enum `["resources","courses","career"]`; messages array of CHAT_MESSAGE; updatedAt ISO_INSTANT); CASES gains `("/api/thrive/conversations", schemas.CONVERSATION, True)`; world fixture creates one conversation with two messages. seed_demo: one conversation with a student question + thrive reply.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_conversations.py`:

```python
import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_conversation, make_message, make_student

pytestmark = pytest.mark.django_db


def test_conversations_newest_first_with_messages(client):
    me = make_student()
    other = make_student(username="other")
    now = timezone.now()
    old = make_conversation(me, title="Old", updated_at=now - dt.timedelta(days=2))
    new = make_conversation(me, title="New", destination="courses", updated_at=now)
    make_message(old, role="student", body="hi", sent_at=now - dt.timedelta(days=2))
    make_message(old, role="thrive", body="hello", sent_at=now - dt.timedelta(days=2, hours=-1))
    make_conversation(other, title="Theirs")

    client.force_login(me.user)
    body = client.get("/api/thrive/conversations").json()
    assert [c["title"] for c in body] == ["New", "Old"]
    assert body[1]["destination"] == "resources"
    msgs = body[1]["messages"]
    assert [m["body"] for m in msgs] == ["hi", "hello"]  # sent_at asc
    assert msgs[0]["role"] == "student" and msgs[0]["id"].startswith("msg-")
    assert body[0]["messages"] == []


def test_single_conversation_and_404s(client):
    me = make_student()
    other = make_student(username="other")
    mine = make_conversation(me)
    theirs = make_conversation(other)
    client.force_login(me.user)

    ok = client.get(f"/api/thrive/conversations/conv-{mine.pk}").json()
    assert ok["id"] == f"conv-{mine.pk}"
    for bad in (f"conv-{theirs.pk}", "conv-99999", "banana", "conv-²"):
        resp = client.get(f"/api/thrive/conversations/{bad}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "unknown_conversation"
```

- [ ] **Step 2: Run to verify failure** — Expected: import errors / 404 routes.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/chat.py`:

```python
from django.conf import settings
from django.db import models
from django.utils import timezone

DESTINATION_CHOICES = [
    ("resources", "resources"), ("courses", "courses"), ("career", "career"),
]
ROLE_CHOICES = [("student", "student"), ("thrive", "thrive")]


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    destination = models.CharField(max_length=16, choices=DESTINATION_CHOICES)
    title = models.CharField(max_length=200)
    updated_at = models.DateTimeField(default=timezone.now)  # when the last message landed


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    body = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sent_at", "pk"]
```

`backend/rsm_thrive/serializers/chat.py`:

```python
from rsm_thrive.serialize import iso_instant


def conversation_payload(conversation) -> dict:
    return {
        "id": f"conv-{conversation.pk}",
        "destination": conversation.destination,
        "title": conversation.title,
        "messages": [
            {
                "id": f"msg-{message.pk}",
                "role": message.role,
                "body": message.body,
                "sentAt": iso_instant(message.sent_at),
            }
            for message in conversation.messages.all()
        ],
        "updatedAt": iso_instant(conversation.updated_at),
    }
```

`backend/rsm_thrive/views/chat.py`:

```python
from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Conversation
from rsm_thrive.serializers.chat import conversation_payload


@api_login_required
def conversations(request):
    rows = (Conversation.objects.filter(user=request.user)
            .prefetch_related("messages").order_by("-updated_at", "-pk"))
    return json_ok([conversation_payload(c) for c in rows])


def _own_conversation(user, conversation_id):
    if not conversation_id.startswith("conv-"):
        return None
    pk = conversation_id.removeprefix("conv-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return (Conversation.objects.filter(pk=pk, user=user)
            .prefetch_related("messages").first())


@api_login_required
def conversation(request, conversation_id):
    row = _own_conversation(request.user, conversation_id)
    if row is None:
        return json_error("unknown_conversation",
                          f"No conversation {conversation_id}.", 404)
    return json_ok(conversation_payload(row))
```

Factories (append to `testing.py`, merging imports):

```python
from rsm_thrive.models import ChatMessage, Conversation


def make_conversation(profile, **overrides) -> Conversation:
    n = next(_counter)
    fields = {"destination": "resources", "title": f"Conversation {n}",
              "updated_at": timezone.now()}
    fields.update(overrides)
    return Conversation.objects.create(user=profile.user, **fields)


def make_message(conversation, **overrides) -> ChatMessage:
    fields = {"role": "student", "body": "hello", "sent_at": timezone.now()}
    fields.update(overrides)
    return ChatMessage.objects.create(conversation=conversation, **fields)
```

Routes: `path("conversations", chat.conversations, name="conversations")`, `path("conversations/<str:conversation_id>", chat.conversation, name="conversation")` (alphabetical; static before parameterized). Re-export models; `makemigrations`.

Contract: add the two schemas per the Interfaces block (`additionalProperties: false` throughout); CASES `+ ("/api/thrive/conversations", schemas.CONVERSATION, True)`; world fixture adds `conv = make_conversation(profile); make_message(conv); make_message(conv, role="thrive", body="answer")`. seed_demo (inside atomic): one conversation "What are the core courses?" with a student question and a thrive reply.

- [ ] **Step 4: Migrate + run tests** — `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`, all PASS (contract now 20 cases).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): conversation read endpoints for the ask surface"
```

---

### Task 4: Frontend — errors module, request context, API client

**Files:**
- Create: `frontend/src/lib/data/errors.ts`, `frontend/src/lib/server/requestContext.ts`, `frontend/src/lib/data/api/client.ts`
- Modify: `frontend/src/lib/data/providers.ts` (only the `SlotUnavailableError` block), `frontend/package.json` (only if `@types/node` is missing from devDependencies — check first; `npm i -D @types/node` if absent)
- Test: `frontend/src/lib/data/api/client.spec.ts`

**Interfaces:**
- `errors.ts` exports `SlotUnavailableError` (class moved VERBATIM from providers.ts:198-203); `providers.ts` deletes the class and adds `export { SlotUnavailableError } from "./errors";` — the public surface via `index.ts` is unchanged.
- `requestContext.ts`: `interface RequestAuth { cookie: string; student: Student | null }`; `runWithAuth<T>(auth: RequestAuth, fn: () => T | Promise<T>)`; `currentAuth(): RequestAuth | null`. Backed by `AsyncLocalStorage` from `node:async_hooks`.
- `client.ts`: `class ApiError extends Error { status: number; code: string }`; `apiOrigin(): string | null` (reads `process.env.THRIVE_API_ORIGIN`); `apiEnabled(): boolean`; `apiFetch<T>(path, init?: { method?: string; body?: unknown }): Promise<T>` — prefixes `${origin}/api/thrive`, forwards the context cookie, echoes `csrftoken` as `x-csrftoken` on non-GET, JSON-encodes body, throws `ApiError(status, error.code, error.message)` on non-2xx, returns `undefined` for 204.

- [ ] **Step 1: Run `npm ci` in `frontend/` (once), then write the failing test**

`frontend/src/lib/data/api/client.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { ApiError, apiEnabled, apiFetch } from "./client";

const AUTH = { cookie: "sessionid=abc; csrftoken=tok123", student: null };

function stubFetch(status: number, payload: unknown) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("is disabled without the env var", () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    expect(apiEnabled()).toBe(false);
  });

  it("forwards the request cookie and prefixes the path", async () => {
    const impl = stubFetch(200, { ok: true });
    const result = await runWithAuth(AUTH, () => apiFetch<{ ok: boolean }>("/me"));
    expect(result).toEqual({ ok: true });
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/me");
    expect(init.headers.cookie).toBe(AUTH.cookie);
    expect(init.headers["x-csrftoken"]).toBeUndefined();
  });

  it("sends csrf header and json body on POST", async () => {
    const impl = stubFetch(201, { id: "appt-1" });
    await runWithAuth(AUTH, () =>
      apiFetch("/appointments", { method: "POST", body: { slotId: "s1" } }),
    );
    const [, init] = impl.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["x-csrftoken"]).toBe("tok123");
    expect(init.headers["content-type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ slotId: "s1" }));
  });

  it("throws ApiError with the envelope's code and message", async () => {
    stubFetch(409, { error: { code: "slot_unavailable", message: "That time was just taken. Pick another." } });
    const attempt = runWithAuth(AUTH, () => apiFetch("/appointments", { method: "POST", body: {} }));
    await expect(attempt).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      code: "slot_unavailable",
      message: "That time was just taken. Pick another.",
    });
    expect(new ApiError(404, "x", "y")).toBeInstanceOf(Error);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/data/api/client.spec.ts`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement**

`frontend/src/lib/data/errors.ts`: move the `SlotUnavailableError` class here verbatim (including its docstring-free shape), and in `providers.ts` replace the class definition with `export { SlotUnavailableError } from "./errors";` plus `import { SlotUnavailableError } from "./errors";` for the internal `bookAppointment` throw sites.

`frontend/src/lib/server/requestContext.ts`:

```typescript
import { AsyncLocalStorage } from "node:async_hooks";

import type { Student } from "$lib/data/types";

export interface RequestAuth {
	cookie: string;
	student: Student | null;
}

const storage = new AsyncLocalStorage<RequestAuth>();

export function runWithAuth<T>(auth: RequestAuth, fn: () => T | Promise<T>) {
	return storage.run(auth, fn);
}

export function currentAuth(): RequestAuth | null {
	return storage.getStore() ?? null;
}
```

`frontend/src/lib/data/api/client.ts`:

```typescript
/**
 * Server-only HTTP client for the Django API. Reads the incoming request's
 * cookie from the per-request AsyncLocalStorage context, so provider
 * signatures never carry credentials. Never import from a component.
 */
import { currentAuth } from "$lib/server/requestContext";

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
	) {
		super(message);
		this.name = "ApiError";
	}
}

export function apiOrigin(): string | null {
	return process.env.THRIVE_API_ORIGIN || null;
}

export function apiEnabled(): boolean {
	return apiOrigin() !== null;
}

function csrfToken(cookie: string): string | null {
	const match = cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
	return match ? match[1] : null;
}

interface Envelope {
	error?: { code?: string; message?: string };
}

export async function apiFetch<T>(
	path: string,
	init: { method?: string; body?: unknown } = {},
): Promise<T> {
	const origin = apiOrigin();
	if (!origin) throw new Error("THRIVE_API_ORIGIN is not set");
	const auth = currentAuth();
	const method = init.method ?? "GET";
	const headers: Record<string, string> = { accept: "application/json" };
	if (auth?.cookie) headers.cookie = auth.cookie;
	if (method !== "GET" && auth?.cookie) {
		const token = csrfToken(auth.cookie);
		if (token) headers["x-csrftoken"] = token;
		headers.referer = origin;
	}
	if (init.body !== undefined) headers["content-type"] = "application/json";
	const response = await fetch(`${origin}/api/thrive${path}`, {
		method,
		headers,
		body: init.body === undefined ? undefined : JSON.stringify(init.body),
	});
	if (response.status === 204) return undefined as T;
	const payload = (await response.json().catch(() => null)) as (Envelope & T) | null;
	if (!response.ok) {
		throw new ApiError(
			response.status,
			payload?.error?.code ?? "unknown",
			payload?.error?.message ?? `API error ${response.status}`,
		);
	}
	return payload as T;
}
```

If `npm run check` complains about `process` or `node:async_hooks` types, add `@types/node` as a devDependency and include the package.json/package-lock changes in this commit.

- [ ] **Step 4: Run tests** — `npx vitest run src/lib/data/api/client.spec.ts` PASS, then `npm test` (whole suite green), `npm run check` (0 errors, 0 warnings).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): server api client with request-scoped auth context"
```

---

### Task 5: Frontend — API read providers

**Files:**
- Create: `frontend/src/lib/data/api/providers.ts`
- Test: `frontend/src/lib/data/api/providers.spec.ts`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError` (Task 4); `currentAuth` (student cache); domain types.
- Produces (this task, reads): `getStudent` (returns the context-cached student copy when hooks already fetched it, else `/me`), `getCourses`, `getSyllabi`, `getAssignments`, `getTasks`, `getEvents`, `getDegreeProgress` (`/degree/progress`), `getProgramTimeline` (`/degree/timeline`), `getResources`, `getAdvisors`, `getSlots(advisorId)`, `getMyAppointments`, `getConversations`, `getConversation(id)` (404 → null). All same signatures as the mock providers.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/data/api/providers.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Student } from "$lib/data/types";
import { runWithAuth } from "$lib/server/requestContext";
import * as api from "./providers";

const AUTH = { cookie: "sessionid=abc", student: null as Student | null };

function stubFetch(status: number, payload: unknown) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("read providers", () => {
  it.each([
    ["getCourses", () => api.getCourses(), "/api/thrive/courses"],
    ["getSyllabi", () => api.getSyllabi(), "/api/thrive/syllabi"],
    ["getAssignments", () => api.getAssignments(), "/api/thrive/assignments"],
    ["getTasks", () => api.getTasks(), "/api/thrive/tasks"],
    ["getEvents", () => api.getEvents(), "/api/thrive/events"],
    ["getDegreeProgress", () => api.getDegreeProgress(), "/api/thrive/degree/progress"],
    ["getProgramTimeline", () => api.getProgramTimeline(), "/api/thrive/degree/timeline"],
    ["getResources", () => api.getResources(), "/api/thrive/resources"],
    ["getAdvisors", () => api.getAdvisors(), "/api/thrive/advisors"],
    ["getMyAppointments", () => api.getMyAppointments(), "/api/thrive/appointments"],
    ["getConversations", () => api.getConversations(), "/api/thrive/conversations"],
  ] as const)("%s hits its endpoint", async (_name, call, expectedPath) => {
    const impl = stubFetch(200, []);
    await runWithAuth(AUTH, call);
    expect(impl.mock.calls[0][0]).toBe(`http://api.test${expectedPath}`);
  });

  it("getSlots encodes the advisor id", async () => {
    const impl = stubFetch(200, []);
    await runWithAuth(AUTH, () => api.getSlots("adv 1"));
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/advisors/adv%201/slots");
  });

  it("getStudent uses the context cache when hooks populated it", async () => {
    const impl = stubFetch(200, { id: "never" });
    const student = { id: "ada" } as Student;
    const result = await runWithAuth({ cookie: "", student }, () => api.getStudent());
    expect(result.id).toBe("ada");
    expect(result).not.toBe(student); // copy, never the stored object
    expect(impl).not.toHaveBeenCalled();
  });

  it("getStudent falls back to /me", async () => {
    const impl = stubFetch(200, { id: "ada" });
    const result = await runWithAuth(AUTH, () => api.getStudent());
    expect(result.id).toBe("ada");
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/me");
  });

  it("getConversation maps 404 to null and rethrows others", async () => {
    stubFetch(404, { error: { code: "unknown_conversation", message: "x" } });
    const missing = await runWithAuth(AUTH, () => api.getConversation("conv-9"));
    expect(missing).toBeNull();

    stubFetch(500, { error: { code: "boom", message: "x" } });
    await expect(runWithAuth(AUTH, () => api.getConversation("conv-9"))).rejects.toMatchObject({
      status: 500,
    });
  });
});
```

- [ ] **Step 2: Run to verify failure** — `npx vitest run src/lib/data/api/providers.spec.ts` FAILs (module missing).

- [ ] **Step 3: Implement**

`frontend/src/lib/data/api/providers.ts` (this task writes the header + reads; Task 6 appends the writes):

```typescript
/**
 * HTTP implementations of the provider contract. Bodies only — the public
 * surface stays `$lib/data`; `providers.ts` delegates here when
 * THRIVE_API_ORIGIN is set. Server-only.
 */
import { currentAuth } from "$lib/server/requestContext";

import type {
	Advisor,
	Appointment,
	AppointmentSlot,
	Assignment,
	Conversation,
	Course,
	CourseRequest,
	CourseRequestInput,
	CourseRequestPrefill,
	DegreeProgress,
	Event,
	ProgramTimeline,
	ResourceLink,
	ResumeDiff,
	ResumeVersion,
	Skill,
	Student,
	Syllabus,
	Task,
} from "../types";
import { ApiError, apiFetch } from "./client";

export async function getStudent(): Promise<Student> {
	const cached = currentAuth()?.student;
	if (cached) return { ...cached };
	return apiFetch<Student>("/me");
}

export function getCourses(): Promise<Course[]> {
	return apiFetch<Course[]>("/courses");
}

export function getSyllabi(): Promise<Syllabus[]> {
	return apiFetch<Syllabus[]>("/syllabi");
}

export function getAssignments(): Promise<Assignment[]> {
	return apiFetch<Assignment[]>("/assignments");
}

export function getTasks(): Promise<Task[]> {
	return apiFetch<Task[]>("/tasks");
}

export function getEvents(): Promise<Event[]> {
	return apiFetch<Event[]>("/events");
}

export function getDegreeProgress(): Promise<DegreeProgress> {
	return apiFetch<DegreeProgress>("/degree/progress");
}

export function getProgramTimeline(): Promise<ProgramTimeline> {
	return apiFetch<ProgramTimeline>("/degree/timeline");
}

export function getResources(): Promise<ResourceLink[]> {
	return apiFetch<ResourceLink[]>("/resources");
}

export function getAdvisors(): Promise<Advisor[]> {
	return apiFetch<Advisor[]>("/advisors");
}

export function getSlots(advisorId: string): Promise<AppointmentSlot[]> {
	return apiFetch<AppointmentSlot[]>(
		`/advisors/${encodeURIComponent(advisorId)}/slots`,
	);
}

export function getMyAppointments(): Promise<Appointment[]> {
	return apiFetch<Appointment[]>("/appointments");
}

export function getConversations(): Promise<Conversation[]> {
	return apiFetch<Conversation[]>("/conversations");
}

export async function getConversation(
	conversationId: string,
): Promise<Conversation | null> {
	try {
		return await apiFetch<Conversation>(
			`/conversations/${encodeURIComponent(conversationId)}`,
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}
```

(The unused type imports for Task 6's writes are fine to include now if `npm run check` accepts them; otherwise import them in Task 6.)

- [ ] **Step 4: Run tests** — focused spec PASS, `npm test` green, `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/data/api
git commit -m "feat(frontend): api implementations for the read providers"
```

---

### Task 6: Frontend — API write providers with contract error translation

**Files:**
- Modify: `frontend/src/lib/data/api/providers.ts` (append)
- Test: `frontend/src/lib/data/api/writes.spec.ts`

**Interfaces:**
- Produces: `bookAppointment(slotId, reason)` (409 or `slot_unknown` → `SlotUnavailableError(server message)`), `cancelAppointment(id)` (404 → null), `getRequestPrefill`, `createRequest(input)`, `submitRequest(id)` (404 → null), `getMyRequests`, `getTssConnection()` / `connectTss()` (unwrap `{connected}` → boolean), `getSkills`, `getResumeVersions`, `getCurrentResume` (404 → null), `generateNewVersion()` (→ `{version, diff}`), `setCurrentVersion(id)` (404 → null). Same signatures as the mocks.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/data/api/writes.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SlotUnavailableError } from "$lib/data/errors";
import { runWithAuth } from "$lib/server/requestContext";
import * as api from "./providers";

const AUTH = { cookie: "sessionid=abc; csrftoken=t", student: null };

function stubFetch(status: number, payload: unknown) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("write providers", () => {
  it("bookAppointment posts and returns the appointment", async () => {
    const impl = stubFetch(201, { id: "appt-1", status: "confirmed" });
    const result = await runWithAuth(AUTH, () => api.bookAppointment("s1", "why"));
    expect(result.id).toBe("appt-1");
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/appointments");
    expect(init.body).toBe(JSON.stringify({ slotId: "s1", reason: "why" }));
  });

  it("bookAppointment translates 409 and slot_unknown into SlotUnavailableError", async () => {
    stubFetch(409, { error: { code: "slot_unavailable", message: "That time was just taken. Pick another." } });
    await expect(runWithAuth(AUTH, () => api.bookAppointment("s1", "r")))
      .rejects.toThrow(SlotUnavailableError);

    stubFetch(404, { error: { code: "slot_unknown", message: "That time is no longer listed." } });
    const attempt = runWithAuth(AUTH, () => api.bookAppointment("s1", "r"));
    await expect(attempt).rejects.toThrow("That time is no longer listed.");
  });

  it("cancelAppointment maps 404 to null", async () => {
    stubFetch(404, { error: { code: "unknown_appointment", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.cancelAppointment("appt-9"))).toBeNull();
  });

  it("submitRequest and setCurrentVersion map 404 to null", async () => {
    stubFetch(404, { error: { code: "unknown_request", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.submitRequest("req-9"))).toBeNull();
    stubFetch(404, { error: { code: "unknown_version", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.setCurrentVersion("rv-9"))).toBeNull();
  });

  it("tss providers unwrap the connected flag", async () => {
    stubFetch(200, { connected: false });
    expect(await runWithAuth(AUTH, () => api.getTssConnection())).toBe(false);
    const impl = stubFetch(200, { connected: true });
    expect(await runWithAuth(AUTH, () => api.connectTss())).toBe(true);
    expect(impl.mock.calls[0][1].method).toBe("POST");
  });

  it("getCurrentResume maps no_resume 404 to null; generate returns version+diff", async () => {
    stubFetch(404, { error: { code: "no_resume", message: "x" } });
    expect(await runWithAuth(AUTH, () => api.getCurrentResume())).toBeNull();

    stubFetch(201, { version: { id: "rv-1" }, diff: { addedSkills: [], addedCourses: [], summaryChanged: true } });
    const generated = await runWithAuth(AUTH, () => api.generateNewVersion());
    expect(generated.version.id).toBe("rv-1");
    expect(generated.diff.summaryChanged).toBe(true);
  });

  it("createRequest posts the input", async () => {
    const impl = stubFetch(201, { id: "req-1", status: "draft" });
    await runWithAuth(AUTH, () =>
      api.createRequest({ type: "drop", course: "MGTA 453", reason: "conflict" }),
    );
    expect(impl.mock.calls[0][1].body).toBe(
      JSON.stringify({ type: "drop", course: "MGTA 453", reason: "conflict" }),
    );
  });
});
```

- [ ] **Step 2: Run to verify failure** — FAILs (functions missing).

- [ ] **Step 3: Implement**

Append to `frontend/src/lib/data/api/providers.ts`:

```typescript
import { SlotUnavailableError } from "../errors";

export async function bookAppointment(
	slotId: string,
	reason: string,
): Promise<Appointment> {
	try {
		return await apiFetch<Appointment>("/appointments", {
			method: "POST",
			body: { slotId, reason },
		});
	} catch (error) {
		if (
			error instanceof ApiError &&
			(error.status === 409 || error.code === "slot_unknown")
		) {
			throw new SlotUnavailableError(error.message);
		}
		throw error;
	}
}

export async function cancelAppointment(
	appointmentId: string,
): Promise<Appointment | null> {
	try {
		return await apiFetch<Appointment>(
			`/appointments/${encodeURIComponent(appointmentId)}/cancel`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function getRequestPrefill(): Promise<CourseRequestPrefill> {
	return apiFetch<CourseRequestPrefill>("/requests/prefill");
}

export function createRequest(input: CourseRequestInput): Promise<CourseRequest> {
	return apiFetch<CourseRequest>("/requests", { method: "POST", body: input });
}

export async function submitRequest(
	requestId: string,
): Promise<CourseRequest | null> {
	try {
		return await apiFetch<CourseRequest>(
			`/requests/${encodeURIComponent(requestId)}/submit`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function getMyRequests(): Promise<CourseRequest[]> {
	return apiFetch<CourseRequest[]>("/requests");
}

export async function getTssConnection(): Promise<boolean> {
	return (await apiFetch<{ connected: boolean }>("/tss")).connected;
}

export async function connectTss(): Promise<boolean> {
	return (
		await apiFetch<{ connected: boolean }>("/tss/connect", { method: "POST" })
	).connected;
}

export function getSkills(): Promise<Skill[]> {
	return apiFetch<Skill[]>("/resume/skills");
}

export function getResumeVersions(): Promise<ResumeVersion[]> {
	return apiFetch<ResumeVersion[]>("/resume/versions");
}

export async function getCurrentResume(): Promise<ResumeVersion | null> {
	try {
		return await apiFetch<ResumeVersion>("/resume/current");
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}

export function generateNewVersion(): Promise<{
	version: ResumeVersion;
	diff: ResumeDiff;
}> {
	return apiFetch<{ version: ResumeVersion; diff: ResumeDiff }>(
		"/resume/versions",
		{ method: "POST" },
	);
}

export async function setCurrentVersion(
	versionId: string,
): Promise<ResumeVersion | null> {
	try {
		return await apiFetch<ResumeVersion>(
			`/resume/versions/${encodeURIComponent(versionId)}/current`,
			{ method: "POST" },
		);
	} catch (error) {
		if (error instanceof ApiError && error.status === 404) return null;
		throw error;
	}
}
```

- [ ] **Step 4: Run tests** — focused spec PASS, `npm test` green, `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/data/api
git commit -m "feat(frontend): api write providers with contract error translation"
```

---

### Task 7: Frontend — delegation switch, auth hooks, action guard

**Files:**
- Modify: `frontend/src/lib/data/providers.ts`, `frontend/src/app.d.ts`, `frontend/src/routes/appointments/+page.server.ts`, `frontend/src/lib/messages.ts`
- Create: `frontend/src/hooks.server.ts`
- Test: `frontend/src/lib/data/delegation.spec.ts`

**Interfaces:**
- `providers.ts`: every existing exported provider body is renamed to a module-local `mockX` function (bodies UNCHANGED); each public export becomes a one-line delegator, e.g. `export function getStudent(): Promise<Student> { return apiEnabled() ? api.getStudent() : mockGetStudent(); }`. All 27: getStudent, getCourses, getSyllabi, getAssignments, getTasks, getEvents, getDegreeProgress, getProgramTimeline, getResources, getAdvisors, getSlots, getMyAppointments, bookAppointment, cancelAppointment, getRequestPrefill, createRequest, submitRequest, getMyRequests, getTssConnection, connectTss, getSkills, getResumeVersions, getCurrentResume, generateNewVersion, setCurrentVersion, getConversations, getConversation. Imports: `import * as api from "./api/providers"; import { apiEnabled } from "./api/client";`.
- `hooks.server.ts`: no-op passthrough when `apiEnabled()` is false. When true: wrap `resolve(event)` in `runWithAuth({ cookie, student: null }, ...)`; fetch `/me`; on `ApiError` 401/403 redirect 303 to `process.env.THRIVE_LOGIN_URL ?? \`${process.env.THRIVE_API_ORIGIN}/api/thrive/dev-login\`` with `?next=<event.url.href>`; on success set `auth.student` and `event.locals.student`.
- `app.d.ts`: `App.Locals` gains `student?: Student`.
- Appointments actions: first line of both `book` and `cancel` becomes `if (!locals.student && apiEnabled()) return fail(401, { error: messages.appointments.errors.signedOut });` (destructure `locals` in the action signature). New copy key `signedOut: "Your session has ended. Refresh to sign in again."` added to `messages.appointments.errors`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/data/delegation.spec.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("provider delegation", () => {
  it("uses the mock path when THRIVE_API_ORIGIN is unset", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    const { getStudent } = await import("./providers");
    const student = await getStudent();
    expect(student.id).toBeTruthy(); // mock student
    expect(spy).not.toHaveBeenCalled();
  });

  it("uses the api path when THRIVE_API_ORIGIN is set", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test");
    const impl = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "ada" }),
    });
    vi.stubGlobal("fetch", impl);
    const { getStudent } = await import("./providers");
    const student = await runWithAuth({ cookie: "", student: null }, () => getStudent());
    expect(student.id).toBe("ada");
    expect(impl.mock.calls[0][0]).toBe("http://api.test/api/thrive/me");
  });
});
```

- [ ] **Step 2: Run to verify failure** — the second case FAILs (no delegation yet).

- [ ] **Step 3: Implement**

In `providers.ts`: add the two imports; rename each existing exported function `getX` to `mockGetX` (keep bodies and docstrings — move the doc comments WITH the mock functions), then add the 27 delegators at the end of the file under a `// Delegation: THRIVE_API_ORIGIN selects the Django implementations.` banner. Signature examples (repeat the pattern for all 27, preserving exact parameter and return types):

```typescript
export function getStudent(): Promise<Student> {
	return apiEnabled() ? api.getStudent() : mockGetStudent();
}
export function getSlots(advisorId: string): Promise<AppointmentSlot[]> {
	return apiEnabled() ? api.getSlots(advisorId) : mockGetSlots(advisorId);
}
export function bookAppointment(slotId: string, reason: string): Promise<Appointment> {
	return apiEnabled() ? api.bookAppointment(slotId, reason) : mockBookAppointment(slotId, reason);
}
export function getConversation(conversationId: string): Promise<Conversation | null> {
	return apiEnabled() ? api.getConversation(conversationId) : mockGetConversation(conversationId);
}
```

`frontend/src/hooks.server.ts`:

```typescript
import { redirect, type Handle } from "@sveltejs/kit";

import { ApiError, apiEnabled, apiFetch } from "$lib/data/api/client";
import type { Student } from "$lib/data/types";
import { runWithAuth, type RequestAuth } from "$lib/server/requestContext";

export const handle: Handle = async ({ event, resolve }) => {
	if (!apiEnabled()) return resolve(event);

	const auth: RequestAuth = {
		cookie: event.request.headers.get("cookie") ?? "",
		student: null,
	};

	return runWithAuth(auth, async () => {
		try {
			auth.student = await apiFetch<Student>("/me");
		} catch (error) {
			if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
				const login =
					process.env.THRIVE_LOGIN_URL ??
					`${process.env.THRIVE_API_ORIGIN}/api/thrive/dev-login`;
				redirect(303, `${login}?next=${encodeURIComponent(event.url.href)}`);
			}
			throw error;
		}
		event.locals.student = auth.student;
		return resolve(event);
	});
};
```

`app.d.ts`: inside the existing `App` namespace add:

```typescript
		interface Locals {
			student?: import("$lib/data/types").Student;
		}
```

`appointments/+page.server.ts`: change both action signatures to `async ({ request, locals })` and insert as the FIRST statement of each:

```typescript
		if (apiEnabled() && !locals.student) {
			return fail(401, { error: messages.appointments.errors.signedOut });
		}
```

with `import { apiEnabled } from "$lib/data/api/client";` added to the imports. `messages.ts`: add `signedOut: "Your session has ended. Refresh to sign in again.",` alongside the other `appointments.errors` entries.

- [ ] **Step 4: Run tests** — focused spec PASS, `npm test` green, `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): provider delegation switch, auth hooks, action guard"
```

---

### Task 8: Gates + end-to-end smoke

**Files:**
- No new source files expected; fix any fallout the gates surface (report what and why).

- [ ] **Step 1: Frontend gates** (from `frontend/`)

```bash
npm test                              # full unit suite
npm run check                         # 0 errors AND 0 warnings
npm run build                         # compiles (netlify adapter)
python3 ../scripts/check-contrast.py  # palette
npx playwright install chromium       # best effort; gates skip loudly without it
npm run check:layout
npm run check:interaction
```

Also run the timezone sweep: open `../docs/upstream/setup_info.md`, find the timezone sweep command, and run it as written there.

- [ ] **Step 2: Backend suite** — `cd ../backend && uv run pytest -q` (expect 120+ passed, 0 warnings).

- [ ] **Step 3: End-to-end smoke (scripted, run once)**

```bash
cd ../backend
rm -f db.sqlite3
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8123 > /tmp/f4a-django.log 2>&1 &
DJANGO_PID=$!

cd ../frontend
ADAPTER=node npm run build:node
THRIVE_API_ORIGIN=http://127.0.0.1:8123 ORIGIN=http://localhost:3123 PORT=3123 \
  node build-node/index.js > /tmp/f4a-node.log 2>&1 &
NODE_PID=$!
sleep 3

# NOTE: address Django and the Node server by the SAME hostname (e.g. both localhost) — session cookies are host-scoped and a 127.0.0.1/localhost mix splits the cookie jar.

# 1. Unauthenticated → redirect to dev login
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:3123/
# expect: 303 http://127.0.0.1:8123/api/thrive/dev-login?next=...

# 2. Log in as demo (grab csrf, post credentials, keep the session cookie)
JAR=/tmp/f4a-cookies.txt
curl -s -c $JAR http://localhost:8123/api/thrive/dev-login > /dev/null
CSRF=$(grep csrftoken $JAR | awk '{print $7}')
curl -s -b $JAR -c $JAR -o /dev/null -w "%{http_code}\n" \
  -d "username=demo&password=demo&next=/&csrfmiddlewaretoken=$CSRF" \
  http://localhost:8123/api/thrive/dev-login
# expect: 302

# 3. Authenticated dashboard renders real data
curl -s -b $JAR http://localhost:3123/ | grep -o "Demo Student" | head -1
# expect: Demo Student

kill $DJANGO_PID $NODE_PID
```

Record each command's actual output in the report. If the smoke fails, debug and fix before committing — this step is the phase's definition of done.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A backend frontend
git commit -m "test(f4a): gates green and end-to-end smoke passing"
```

(If nothing needed fixing, commit only if there are changes; otherwise state "no fixes needed" in the report.)

---

## Plan Self-Review (completed at authoring)

- **Spec coverage:** spec §2 login flow (T2 dev substitute + T7 hooks), identity threading via ALS with unchanged signatures (T4/T7), server-to-server cookie+CSRF (T2/T4), auth enforced on every call by Django (unchanged from F1-F2) plus the in-action guard closing MIGRATION §9 defect 2 (T7), the carried F1 ruling "no_profile across ALL call sites via one shared helper" (T1), the conversations gap (T3). Base path + production CSRF origin deliberately deferred to F5; localStorage stores to F4b.
- **Placeholder scan:** T7's delegation shows 4 of 27 wrappers with the exact pattern and the complete name list — the remaining wrappers are the same one-liner with types already defined in this plan and in `providers.ts` itself; T8's timezone-sweep command is deliberately read from `setup_info.md` (the authority) rather than transcribed. No TBDs.
- **Type consistency:** `RequestAuth`, `runWithAuth`, `currentAuth`, `ApiError(status, code, message)`, `apiEnabled`, `apiFetch<T>(path, {method, body})` used identically across T4–T7; provider names match `providers.ts` exports 1:1; Django additions reuse `json_error`/`api_login_required` conventions.
