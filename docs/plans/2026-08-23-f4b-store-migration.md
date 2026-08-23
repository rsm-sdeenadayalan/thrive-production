# F4b — localStorage → Server Store Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In API mode, a student's personal edits (task ticks/renames/priorities/dues/order, self-added tasks, notes, event ignores/joins, calendar labels/urgent flags, custom events, quick list, calendar prefs) persist on the server and follow them across devices — while the mock path, the client reactive layer, and every store's public API stay byte-identical.

**Architecture:** The server becomes a drop-in replacement for `localStorage` behind the existing one-seam factory (`overrideStore.svelte.ts` — "when the Django backend lands, this module is the seam that changes"). `GET /overlay` gains a `stores` map keyed by the EXACT localStorage key names; the root layout primes it and `hydrate()` consumes the seed instead of localStorage when present. Writes stay optimistic: each `set()` additionally calls a central `syncOverlay(storageKey, id, value)` dispatcher (fire-and-forget, keep-on-failure — the same contract as a localStorage quota throw) which POSTs to a single same-origin SvelteKit proxy route (`/overlay-sync`) that forwards to Django via the server-only `apiFetch` (cookie + CSRF ride the existing hooks context). Client-generated ids become the server keys (`StudentTask.client_key`; the four new models key on `(user, key)` verbatim — including the double-prefixed `custom-custom-…` ids), so no write ever needs an id round-trip. Forget-on-match stays client-side, computed against SOURCE tasks: the API `getTasks` switches to `GET /tasks?view=source` (assignment-derived + shared, no overrides, no StudentTask — added tasks arrive via the seed, exactly like the mock).

**Tech Stack:** Django ≥5.2 (uv), SvelteKit 2 / TS strict / Vitest (npm). No new dependencies.

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §3.2/§7-semantics; store semantics authority: `frontend/src/lib/overrideStore.svelte.ts`, `userEdits.svelte.ts`, `calendarItems.ts`, `ignoredEvents.ts`, `quickList.ts`, `calendarPrefs.ts`, `taskNotes.svelte.ts`, and `docs/upstream/BACKEND.md` §7 ("absent = use the source value"; a bare done-set cannot express un-ticking a shipped-done task). Out of scope: undo redesign (stays client-local), `thrive:quicklist-panel` / `floatingPanel` / `thrive:assistant` (stay browser-local by design), base path (F5).

## Global Constraints

- **Mock path byte-identical**: with `THRIVE_API_ORIGIN` unset (and the seed unprimed), every store reads/writes localStorage exactly as today — all 672 frontend tests, six gates, and the timezone sweep stay green untouched.
- **Sparse-override semantics preserved**: forget-on-match is computed client-side against source values; a cleared facet syncs as explicit `null`; the seed only ever contains genuine divergence. In API mode localStorage is NOT written (no per-browser ghost state).
- **Key spaces verbatim**: task id / calendar item id / raw `Event.id` — server columns store the client's strings untouched (calendar-item keys can be `custom-custom-<epoch36>…`: column length 120). No fourth key space invented; quick-list `q-…` and custom-event `custom-…` ids are client-authored row KEYS, not new cross-references.
- **Wall-clock strings stay strings**: `CustomEvent.dayKey` ("YYYY-MM-DD") and `time` ("HH:mm") are LOCAL wall-clock CharFields, never DateTimeFields (a `DateTimeField` would shift evening events for anyone behind UTC). `QuickItem.dueDate` is an opaque client string.
- **Hydration contract unchanged**: empty on the server and first client render; stores fill in the root layout's `$effect` after mount — seed is primed there, before `hydrateStores()`.
- **`.svelte.ts` runes rules**: copy-on-write reassignment (never mutate `values`), `read()` never hydrates, `set()` hydrates first. The sync dispatcher lives in a plain `.ts` module (no runes).
- **Failure contract**: sync is fire-and-forget; on failure the in-memory (and screen) value KEEPS the edit and a `console.warn` records it — mirroring the documented localStorage-quota behavior. No rollback, no toast.
- Error envelope / 401 / guard idioms as established. Backend from `backend/` via `uv run`; frontend from `frontend/` via npm. Commit per task on `main`. Suites at start: backend 127, frontend 672, check 0/0.

---

### Task 1: Django — client keys for added tasks + source task view

**Files:**
- Modify: `backend/rsm_thrive/models/overlay.py` (StudentTask), `backend/rsm_thrive/services/tasks.py`, `backend/rsm_thrive/views/tasks.py`
- Test: `backend/rsm_thrive/tests/test_client_key_tasks.py`

**Interfaces:**
- `StudentTask` gains `client_key = models.CharField(max_length=64, null=True, blank=True)` with `UniqueConstraint(fields=["user", "client_key"], condition=Q(client_key__isnull=False), name="uniq_student_task_client_key")`.
- `services/tasks.py`: StudentTask rows serialize with `"id": t.client_key or f"stu:{t.pk}"`; new `assemble_source_tasks(user) -> list[dict]` — assignment-derived + SharedTask ONLY (no StudentTask, no overrides), sorted `(done, due, id)` on source values.
- `views/tasks.py`: `POST /tasks` accepts optional `clientKey` (string ≤64; must not start with `asg:`/`shared:`/`stu:`; else 400) and becomes an UPSERT on `(user, client_key)` when provided (update title/dueDate/priority/source; the mock's `setTaskDue` mutates a stored added task and re-sends the whole object, so re-POSTing an existing key must update, not duplicate); `DELETE /tasks/<task_id>` also matches `client_key` rows (and still cascades that key's `TaskOverride`s); `GET /tasks?view=source` returns `assemble_source_tasks`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_client_key_tasks.py`:

```python
import json

import pytest
from django.utils import timezone

from rsm_thrive.models import StudentTask, TaskOverride
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _post(client, body):
    return client.post("/api/thrive/tasks", data=json.dumps(body),
                       content_type="application/json")


def test_client_key_create_upsert_and_delete(client):
    me = make_student()
    client.force_login(me.user)
    body = {"title": "Print resume", "dueDate": "2026-09-01T12:00:00-07:00",
            "clientKey": "task-add-abc"}
    created = _post(client, body).json()
    assert created["id"] == "task-add-abc"

    # re-POST with the same key updates in place (setTaskDue re-sends the object)
    body["title"] = "Print resume tonight"
    updated = _post(client, body)
    assert updated.status_code == 201
    assert StudentTask.objects.count() == 1
    assert StudentTask.objects.get().title == "Print resume tonight"

    # overrides key on the client key; delete cascades them
    client.patch("/api/thrive/tasks/task-add-abc/override",
                 data=json.dumps({"done": True}), content_type="application/json")
    assert TaskOverride.objects.filter(task_key="task-add-abc").exists()
    assert client.delete("/api/thrive/tasks/task-add-abc").status_code == 204
    assert StudentTask.objects.count() == 0
    assert not TaskOverride.objects.filter(task_key="task-add-abc").exists()


def test_client_key_rejects_reserved_prefixes(client):
    me = make_student()
    client.force_login(me.user)
    for bad in ("asg:x", "shared:9", "stu:9"):
        resp = _post(client, {"title": "x", "dueDate": "2026-09-01T12:00:00-07:00",
                              "clientKey": bad})
        assert resp.status_code == 400


def test_source_view_excludes_student_tasks_and_overrides(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    _post(client if client.force_login(me.user) is None else client,
          {"title": "Mine", "dueDate": "2026-09-01T12:00:00-07:00",
           "clientKey": "task-add-1"})
    client.patch("/api/thrive/tasks/asg:a1/override",
                 data=json.dumps({"title": "Renamed"}),
                 content_type="application/json")

    merged = client.get("/api/thrive/tasks").json()
    source = client.get("/api/thrive/tasks?view=source").json()
    assert any(t["id"] == "task-add-1" for t in merged)
    assert [t["id"] for t in source] == ["asg:a1"]
    assert source[0]["title"] == "Homework 1"  # no override applied
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest rsm_thrive/tests/test_client_key_tasks.py -v`, FAILs.

- [ ] **Step 3: Implement**

Model: add the field + constraint to `StudentTask` (import `Q` is already in overlay.py via appointments? overlay.py has no Q — add `from django.db.models import Q` or use `models.Q`). `uv run python manage.py makemigrations rsm_thrive`.

`services/tasks.py`: in `_base_tasks`, the StudentTask loop's `"id"` becomes `t.client_key or f"stu:{t.pk}"`. Add:

```python
def assemble_source_tasks(user) -> list[dict]:
    """Assignment-derived + shared tasks only, no overrides — the mock-parity
    source view the API frontend merges client overrides onto."""
    tasks = [t for t in _base_tasks(user) if not t["id"].startswith("stu:")
             and t["id"] not in _student_task_ids(user)]
    tasks.sort(key=lambda t: (t["done"], t["_due"], t["id"]))
    for task in tasks:
        task.pop("_due", None)
        task.pop("_order", None)
    return tasks
```

Implementation note: simpler than filtering after the fact — refactor `_base_tasks(user, include_student=True)` with the StudentTask loop guarded by the flag, and `assemble_source_tasks` calls `_base_tasks(user, include_student=False)` then sorts/strips as above (no override pass). Keep `assemble_tasks` behavior identical.

`views/tasks.py`:
- `tasks` view: `if request.GET.get("view") == "source": return json_ok(assemble_source_tasks(request.user))`.
- `create_task`: after existing validation add:

```python
    client_key = body.get("clientKey")
    if client_key is not None:
        if (not isinstance(client_key, str) or not client_key.strip()
                or len(client_key) > 64
                or client_key.startswith(("asg:", "shared:", "stu:"))):
            return json_error("bad_request", "clientKey is invalid.", 400)
        row, _created = StudentTask.objects.update_or_create(
            user=request.user, client_key=client_key,
            defaults={"title": title.strip(), "due_date": due,
                      "priority": body.get("priority", "medium"),
                      "source": body.get("source", "admin")},
        )
    else:
        row = StudentTask.objects.create(...)  # existing path unchanged
```

(then the existing `merged[...]` lookup keys on `client_key or f"stu:{row.pk}"`). Note: the existing priority/source enum validation from the F1 fix wave must still run BEFORE the upsert.
- `delete_task`: accept ids that are either `stu:<pk>` (existing path) or a client key: `StudentTask.objects.filter(user=request.user).filter(Q(client_key=task_id) | Q(pk=pk_if_stu_prefix))` — keep the 400 `not_deletable` ONLY for `asg:`/`shared:` prefixes; unknown other keys → 404. TaskOverride cascade uses `task_key=task_id` as today.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS (contract suite unchanged: no clientKey in its flows).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): client-keyed student tasks and source task view"
```

---

### Task 2: Django — personal-store models + endpoints + bulk order

**Files:**
- Create: `backend/rsm_thrive/models/personal.py`, `backend/rsm_thrive/views/personal.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/urls.py`, `backend/rsm_thrive/views/tasks.py` (bulk order), `backend/rsm_thrive/testing.py`
- Test: `backend/rsm_thrive/tests/test_personal_stores.py`

**Interfaces:**
- Models (all keyed on the client's string verbatim, unique per user):
  - `CalendarItemLabel(user FK, item_key Char(120), label Text)` — `uniq_item_label`
  - `CalendarItemUrgent(user FK, item_key Char(120))` — `uniq_item_urgent` (presence = urgent)
  - `CustomCalendarEvent(user FK, key Char(120), title Char(200), day_key Char(10), time Char(5) blank default "", label Text blank default "", urgent Bool default False, created_at_ms BigInt)` — `uniq_custom_event`
  - `QuickListItem(user FK, key Char(64), title Char(200), done Bool default False, created_at_ms BigInt, copied_from Char(120) blank default "", due_date Char(64) blank default "", note Text blank default "")` — `uniq_quick_item`
- Endpoints (all `@api_login_required`, 204 on success, idempotent upserts/deletes):
  - `PUT /calendar-items/<item_key>/label` body `{"label": str}` — trimmed; empty → delete row
  - `PUT | DELETE /calendar-items/<item_key>/urgent`
  - `PUT /custom-events/<key>` body `{"title" non-empty str, "dayKey" matches ^\d{4}-\d{2}-\d{2}$, "time"? matches ^\d{2}:\d{2}$, "label"? str, "urgent"? bool, "createdAt" int}` (400 `bad_request` otherwise); `DELETE /custom-events/<key>` — also deletes CalendarItemLabel/Urgent rows with `item_key == f"custom-{key}"` (mirror of the client cascade; client also fires them — double delete is idempotent)
  - `PUT /quick-items/<key>` body `{"title" non-empty str, "done" bool, "createdAt" int, "copiedFrom"? str, "dueDate"? str, "note"? str}`; `DELETE /quick-items/<key>`
  - `PATCH /tasks/order` body `{"orders": {taskKey: int|null}}` — bulk: for each key in the caller's assembled task set, upsert/clear `TaskOverride.sort_order` (int, bools rejected); keys NOT in the assembled set are silently skipped (bulk must not 404 midway); 400 on non-dict orders or non-int/non-null values.
- Factories: `make_quick_item(profile, key, **overrides)`, `make_custom_event(profile, key, **overrides)` (defaults per model), used by Task 3's overlay tests.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_personal_stores.py`:

```python
import json

import pytest
from django.utils import timezone

from rsm_thrive.models import (
    CalendarItemLabel, CalendarItemUrgent, CustomCalendarEvent, QuickListItem,
    TaskOverride,
)
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _put(client, path, body=None):
    return client.put(path, data=json.dumps(body if body is not None else {}),
                      content_type="application/json")


def test_label_and_urgent_roundtrip(client):
    me = make_student()
    client.force_login(me.user)
    key = "custom-custom-1712345678901-ab3"   # double-prefixed ids fit verbatim
    assert _put(client, f"/api/thrive/calendar-items/{key}/label",
                {"label": "  Study group  "}).status_code == 204
    assert CalendarItemLabel.objects.get(item_key=key).label == "Study group"
    assert _put(client, f"/api/thrive/calendar-items/{key}/label",
                {"label": "  "}).status_code == 204        # empty = delete
    assert not CalendarItemLabel.objects.exists()

    assert _put(client, f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert _put(client, f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert CalendarItemUrgent.objects.count() == 1          # idempotent
    assert client.delete(f"/api/thrive/calendar-items/{key}/urgent").status_code == 204
    assert not CalendarItemUrgent.objects.exists()


def test_custom_event_upsert_validation_and_cascade(client):
    me = make_student()
    client.force_login(me.user)
    good = {"title": "Study jam", "dayKey": "2026-09-01", "time": "18:30",
            "urgent": True, "createdAt": 1712345678901}
    assert _put(client, "/api/thrive/custom-events/custom-x1", good).status_code == 204
    good["title"] = "Study jam 2"
    assert _put(client, "/api/thrive/custom-events/custom-x1", good).status_code == 204
    row = CustomCalendarEvent.objects.get()
    assert row.title == "Study jam 2" and row.day_key == "2026-09-01"

    for bad in ({**good, "dayKey": "2026-9-1"}, {**good, "time": "6pm"},
                {**good, "title": " "}, {**good, "createdAt": "now"}):
        assert _put(client, "/api/thrive/custom-events/custom-x2", bad).status_code == 400

    # delete cascades the item-key-space annotations
    _put(client, "/api/thrive/calendar-items/custom-custom-x1/label", {"label": "L"})
    _put(client, "/api/thrive/calendar-items/custom-custom-x1/urgent")
    assert client.delete("/api/thrive/custom-events/custom-x1").status_code == 204
    assert not CustomCalendarEvent.objects.exists()
    assert not CalendarItemLabel.objects.exists()
    assert not CalendarItemUrgent.objects.exists()


def test_quick_item_upsert_and_delete(client):
    me = make_student()
    client.force_login(me.user)
    item = {"title": "Buy poster board", "done": False, "createdAt": 1712345678901,
            "copiedFrom": "asg:a1"}
    assert _put(client, "/api/thrive/quick-items/q-abc", item).status_code == 204
    item["done"] = True
    assert _put(client, "/api/thrive/quick-items/q-abc", item).status_code == 204
    assert QuickListItem.objects.get().done is True
    assert client.delete("/api/thrive/quick-items/q-abc").status_code == 204
    assert not QuickListItem.objects.exists()
    assert _put(client, "/api/thrive/quick-items/q-bad", {"title": "", "done": False,
                "createdAt": 1}).status_code == 400


def test_bulk_order(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    make_assignment(course, id="a2", due=timezone.now() + timezone.timedelta(days=2))
    client.force_login(me.user)

    resp = client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": 2, "asg:a2": 1,
                                                    "asg:ghost": 3}}),
                        content_type="application/json")
    assert resp.status_code == 204
    stored = {o.task_key: o.sort_order for o in TaskOverride.objects.all()}
    assert stored == {"asg:a1": 2, "asg:a2": 1}   # unknown key silently skipped

    resp = client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": None}}),
                        content_type="application/json")
    assert resp.status_code == 204
    assert "asg:a1" not in {o.task_key for o in TaskOverride.objects.all()}

    assert client.patch("/api/thrive/tasks/order",
                        data=json.dumps({"orders": {"asg:a1": True}}),
                        content_type="application/json").status_code == 400
```

- [ ] **Step 2: Run to verify failure** — FAILs (imports/404s).

- [ ] **Step 3: Implement**

`models/personal.py` per the Interfaces block (all four models; `from django.db import models`; constraints named exactly). Re-export in `models/__init__.py`; `makemigrations`.

`views/personal.py` — pattern per endpoint (label shown; urgent mirrors ignore/join's `_flag_views`; custom/quick validate then `update_or_create(user=..., key=..., defaults={...})`):

```python
import re

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, parse_body
from rsm_thrive.models import (
    CalendarItemLabel, CalendarItemUrgent, CustomCalendarEvent, QuickListItem,
)

DAY_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


@api_login_required
@require_http_methods(["PUT"])
def item_label(request, item_key):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    label = body.get("label")
    if not isinstance(label, str):
        return json_error("bad_request", "label must be a string.", 400)
    trimmed = label.strip()
    if trimmed:
        CalendarItemLabel.objects.update_or_create(
            user=request.user, item_key=item_key, defaults={"label": trimmed})
    else:
        CalendarItemLabel.objects.filter(user=request.user, item_key=item_key).delete()
    return HttpResponse(status=204)
```

Custom-event PUT validates: title non-empty str; dayKey `DAY_KEY_RE`; `time` absent/None or `TIME_RE`; urgent bool (default False); label str (default ""); createdAt int not bool. DELETE cascades:

```python
    CustomCalendarEvent.objects.filter(user=request.user, key=key).delete()
    derived = f"custom-{key}"
    CalendarItemLabel.objects.filter(user=request.user, item_key=derived).delete()
    CalendarItemUrgent.objects.filter(user=request.user, item_key=derived).delete()
```

Quick-item PUT validates title non-empty str, done bool, createdAt int not bool; optional copiedFrom/dueDate/note strings (default "").

Bulk order in `views/tasks.py`:

```python
@api_login_required
@require_http_methods(["PATCH"])
def bulk_order(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    orders = body.get("orders")
    if not isinstance(orders, dict):
        return json_error("bad_request", "orders must be an object.", 400)
    for value in orders.values():
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            return json_error("bad_request", "order values must be integers or null.", 400)
    known = {t["id"] for t in assemble_tasks(request.user)}
    for key, value in orders.items():
        if key not in known:
            continue
        if value is None:
            row = TaskOverride.objects.filter(user=request.user, task_key=key).first()
            if row:
                row.sort_order = None
                if all(getattr(row, f) is None for f in OVERRIDE_FACETS.values()):
                    row.delete()
                else:
                    row.save(update_fields=["sort_order"])
        else:
            row, _ = TaskOverride.objects.get_or_create(user=request.user, task_key=key)
            row.sort_order = value
            row.save(update_fields=["sort_order"])
    from django.http import HttpResponse
    return HttpResponse(status=204)
```

Routes (urls.py, alphabetical; `tasks/order` BEFORE `tasks/<str:task_id>` so "order" isn't swallowed as a task id):
`path("calendar-items/<str:item_key>/label", personal.item_label)`, `path("calendar-items/<str:item_key>/urgent", personal.item_urgent)`, `path("custom-events/<str:key>", personal.custom_event)`, `path("quick-items/<str:key>", personal.quick_item)`, `path("tasks/order", tasks.bulk_order)`.

Factories:

```python
from rsm_thrive.models import CustomCalendarEvent, QuickListItem


def make_quick_item(profile, key, **overrides) -> QuickListItem:
    fields = {"title": "Scratch item", "done": False, "created_at_ms": 1712000000000}
    fields.update(overrides)
    return QuickListItem.objects.create(user=profile.user, key=key, **fields)


def make_custom_event(profile, key, **overrides) -> CustomCalendarEvent:
    fields = {"title": "Custom thing", "day_key": "2026-09-01", "time": "18:00",
              "created_at_ms": 1712000000000}
    fields.update(overrides)
    return CustomCalendarEvent.objects.create(user=profile.user, key=key, **fields)
```

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): personal store models, endpoints, and bulk order"
```

---

### Task 3: Django — the overlay `stores` seed map

**Files:**
- Modify: `backend/rsm_thrive/views/overlay.py`, `backend/rsm_thrive/tests/contract/schemas.py`
- Test: `backend/rsm_thrive/tests/test_overlay_stores.py`

**Interfaces:**
- `GET /overlay` keeps its four existing keys and gains `"stores"`: an object whose keys are the EXACT localStorage key names, each holding that store's `Record` exactly as the frontend persists it:
  - `"thrive:task-done"` `{taskKey: bool}`, `"thrive:task-titles"` `{taskKey: str}`, `"thrive:task-priority"`, `"thrive:task-due"` (ISO instant strings via `iso_instant`), `"thrive:task-order"` `{taskKey: int}` — each built from the non-null facet of the user's `TaskOverride` rows.
  - `"thrive:task-added"` `{clientKeyOrStuId: Task-payload}` — from StudentTask rows: `{"id": key, "title", "dueDate": iso_instant, "source", "priority", "done": false, "subtasks": t.subtasks}`.
  - `"thrive:event-joins"` / `"thrive:ignored-events"`: `{eventId: true}`.
  - `"thrive:item-labels"` `{itemKey: str}`; `"thrive:item-urgent"` `{itemKey: true}`.
  - `"thrive:custom-events"` `{key: {"id": key, "title", "dayKey", "time"?, "label"?, "urgent"?, "createdAt"}}` — `time`/`label` omitted when blank; `urgent` omitted when false (matches the client's optional-field shape).
  - `"thrive:quicklist"` `{key: {"id": key, "title", "done", "createdAt", "copiedFrom"?, "dueDate"?, "note"?}}` — optionals omitted when blank.
  - `"thrive:task-notes"` `{taskKey: str}`.
  - `"thrive:calendar-prefs"` `{"value": <the stored prefs object>}` (the store persists under the literal sub-key `"value"` — reproduce it) or `{}` when unset.
- Contract `OVERLAY` schema: add `"stores"` to `required` with `{"type": "object"}` (open — it is a mirror of client-shaped records, pinned by the dedicated test below, not by the schema).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_overlay_stores.py`:

```python
import json

import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_custom_event, make_quick_item,
    make_student, set_override,
)

pytestmark = pytest.mark.django_db


def test_overlay_stores_mirror_localstorage_shapes(client):
    me = make_student()
    course = make_course(id="c1")
    enroll(me, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    set_override(me, "asg:a1", done=False, title="Renamed", order=3)
    client.force_login(me.user)

    # server-side personal rows
    client.post("/api/thrive/tasks",
                data=json.dumps({"title": "Mine", "dueDate": "2026-09-01T12:00:00-07:00",
                                 "clientKey": "task-add-1"}),
                content_type="application/json")
    client.put("/api/thrive/events/evt-1/ignore")
    client.put("/api/thrive/events/evt-2/join")
    client.put("/api/thrive/calendar-items/apt-3/label",
               data=json.dumps({"label": "Coffee chat"}),
               content_type="application/json")
    client.put("/api/thrive/calendar-items/apt-3/urgent")
    make_custom_event(me, "custom-x1", urgent=True)
    make_quick_item(me, "q-abc", note="call mom")
    client.put("/api/thrive/tasks/asg:a1/note",
               data=json.dumps({"note": "ask prof"}), content_type="application/json")
    client.put("/api/thrive/calendar-prefs",
               data=json.dumps({"view": "week"}), content_type="application/json")

    stores = client.get("/api/thrive/overlay").json()["stores"]
    assert stores["thrive:task-done"] == {"asg:a1": False}
    assert stores["thrive:task-titles"] == {"asg:a1": "Renamed"}
    assert stores["thrive:task-order"] == {"asg:a1": 3}
    assert stores["thrive:task-priority"] == {} and stores["thrive:task-due"] == {}
    added = stores["thrive:task-added"]["task-add-1"]
    assert added["id"] == "task-add-1" and added["done"] is False
    assert added["subtasks"] == [] and added["source"] == "admin"
    assert stores["thrive:ignored-events"] == {"evt-1": True}
    assert stores["thrive:event-joins"] == {"evt-2": True}
    assert stores["thrive:item-labels"] == {"apt-3": "Coffee chat"}
    assert stores["thrive:item-urgent"] == {"apt-3": True}
    custom = stores["thrive:custom-events"]["custom-x1"]
    assert custom == {"id": "custom-x1", "title": "Custom thing",
                      "dayKey": "2026-09-01", "time": "18:00",
                      "urgent": True, "createdAt": 1712000000000}
    quick = stores["thrive:quicklist"]["q-abc"]
    assert quick == {"id": "q-abc", "title": "Scratch item", "done": False,
                     "createdAt": 1712000000000, "note": "call mom"}
    assert stores["thrive:task-notes"] == {"asg:a1": "ask prof"}
    assert stores["thrive:calendar-prefs"] == {"value": {"view": "week"}}


def test_overlay_stores_empty_world(client):
    me = make_student()
    client.force_login(me.user)
    stores = client.get("/api/thrive/overlay").json()["stores"]
    assert stores["thrive:task-done"] == {}
    assert stores["thrive:calendar-prefs"] == {}
    assert stores["thrive:custom-events"] == {}
```

- [ ] **Step 2: Run to verify failure** — KeyError "stores".

- [ ] **Step 3: Implement**

In `views/overlay.py`, build the map inside the existing `overlay` view (new helper `_stores_payload(user)` below it) using: `TaskOverride` facet splits (skip null facets; `iso_instant` for due), `StudentTask` (id = `client_key or f"stu:{pk}"`), `IgnoredEvent`/`EventJoin`, `CalendarItemLabel`/`CalendarItemUrgent`, `CustomCalendarEvent` (omit `time`/`label` when blank, omit `urgent` when False; key `createdAt` from `created_at_ms`), `QuickListItem` (omit blank optionals), `TaskNote`, and the existing `CalendarPrefs` row wrapped as `{"value": prefs.prefs}` when present else `{}`. Add `"stores": _stores_payload(request.user)` to the response. Update the contract `OVERLAY` schema: add `"stores": {"type": "object"}` to properties and `"stores"` to required.

- [ ] **Step 4: Run tests** — all PASS (contract suite included).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): overlay stores seed map mirroring localStorage shapes"
```

---

### Task 4: Frontend — overlaySync module + /overlay-sync proxy route

**Files:**
- Create: `frontend/src/lib/overlaySync.ts`, `frontend/src/routes/overlay-sync/+server.ts`
- Test: `frontend/src/lib/overlaySync.spec.ts`, `frontend/src/routes/overlay-sync/server.spec.ts`

**Interfaces:**
- `overlaySync.ts` (plain `.ts` — no runes) exports:
  - `interface OverlaySeed { stores: Record<string, Record<string, unknown>> }`
  - `primeOverlay(data: OverlaySeed | null): void`; `overlayEnabled(): boolean`; `seedFor(key: string): Record<string, unknown> | null`
  - `syncOverlay(storageKey: string, id: string, value: unknown): void` — no-op unless primed AND the key has a handler; dispatches per the table below. `undefined`/`null` value = clear/delete.
  - Special behaviors: `thrive:task-order` writes COALESCE — pending `{id: value}` entries flush via one `queueMicrotask` into a single `task-order-bulk` op (a drag reorder's N set() calls in one tick become one request); `thrive:calendar-prefs` writes DEBOUNCE 400 ms trailing (rapid filter-chip clicks collapse; always sends the latest `value` sub-key object).
  - Keys with NO handler (`thrive:quicklist-panel`, `thrive:assistant`, panel keys) stay purely local.
- Handler → op table (op names are the proxy's contract):
  | storageKey | op | payload |
  |---|---|---|
  | thrive:task-done | task-override | `{taskKey: id, facets: {done: value ?? null}}` |
  | thrive:task-titles | task-override | `{taskKey, facets: {title: value ?? null}}` |
  | thrive:task-priority | task-override | `{taskKey, facets: {priority: value ?? null}}` |
  | thrive:task-due | task-override | `{taskKey, facets: {dueDate: value ?? null}}` |
  | thrive:task-order | task-order-bulk (coalesced) | `{orders: {taskKey: int|null, ...}}` |
  | thrive:task-added | task-add / task-remove | add: `{task: {...value, clientKey: id}}`; remove when cleared: `{taskKey: id}` |
  | thrive:event-joins | event-join | `{eventId: id, on: value === true}` |
  | thrive:ignored-events | event-ignore | `{eventId: id, on: value === true}` |
  | thrive:item-labels | item-label | `{itemKey: id, label: value ?? ""}` |
  | thrive:item-urgent | item-urgent | `{itemKey: id, on: value === true}` |
  | thrive:custom-events | custom-event-put / custom-event-delete | put: `{key: id, event: value}`; delete when cleared |
  | thrive:quicklist | quick-put / quick-delete | put: `{key: id, item: value}`; delete when cleared |
  | thrive:task-notes | task-note | `{taskKey: id, note: value ?? ""}` |
  | thrive:calendar-prefs | calendar-prefs (debounced) | `{prefs: value}` (the `"value"` sub-key's object) |
- Transport: `send(op, payload)` → `fetch("/overlay-sync", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({op, ...payload})})`, fire-and-forget: `.then` warns on `!r.ok`, `.catch` warns; the whole call wrapped so no throw ever escapes into a store.
- `+server.ts`: `POST /overlay-sync` — 404 envelope when `!apiEnabled()`; parses `{op, ...payload}`; allowlist maps op → `{path, method, body}` for `apiFetch` (running inside the hooks' request context, so cookie+CSRF forward): `task-override → PATCH /tasks/{taskKey}/override body facets`; `task-add → POST /tasks body {title,dueDate,priority,source,clientKey}` (project ONLY those five fields out of the client Task object); `task-remove → DELETE /tasks/{taskKey}`; `task-order-bulk → PATCH /tasks/order body {orders}`; `event-ignore/event-join → PUT|DELETE /events/{eventId}/ignore|join` by `on`; `calendar-prefs → PUT /calendar-prefs body prefs`; `task-note → PUT /tasks/{taskKey}/note body {note}`; `item-label → PUT /calendar-items/{itemKey}/label body {label}`; `item-urgent → PUT|DELETE /calendar-items/{itemKey}/urgent`; `custom-event-put → PUT /custom-events/{key}` body `{title,dayKey,time,label,urgent,createdAt}` projected from the event object; `custom-event-delete → DELETE`; `quick-put → PUT /quick-items/{key}` body projected `{title,done,createdAt,copiedFrom,dueDate,note}`; `quick-delete → DELETE`. Unknown op → 400 `unknown_op`. ApiError → its status+envelope passthrough; success → `json({ok: true})`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/overlaySync.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { overlayEnabled, primeOverlay, seedFor, syncOverlay } from "./overlaySync";

function stubFetch() {
  const impl = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function sentOps(impl: ReturnType<typeof vi.fn>) {
  return impl.mock.calls.map(([, init]) => JSON.parse(init.body as string));
}

beforeEach(() => {
  vi.useFakeTimers();
  primeOverlay({ stores: { "thrive:task-done": { "asg:a1": true } } });
});
afterEach(() => {
  primeOverlay(null);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("overlaySync", () => {
  it("seed access and enablement", () => {
    expect(overlayEnabled()).toBe(true);
    expect(seedFor("thrive:task-done")).toEqual({ "asg:a1": true });
    expect(seedFor("thrive:task-titles")).toBeNull();
    primeOverlay(null);
    expect(overlayEnabled()).toBe(false);
  });

  it("does nothing when unprimed or for unhandled keys", () => {
    const impl = stubFetch();
    syncOverlay("thrive:quicklist-panel", "panel", { open: true });
    primeOverlay(null);
    syncOverlay("thrive:task-done", "asg:a1", true);
    expect(impl).not.toHaveBeenCalled();
  });

  it("dispatches override facets with null for cleared values", () => {
    const impl = stubFetch();
    syncOverlay("thrive:task-done", "asg:a1", true);
    syncOverlay("thrive:task-titles", "asg:a1", undefined);
    expect(sentOps(impl)).toEqual([
      { op: "task-override", taskKey: "asg:a1", facets: { done: true } },
      { op: "task-override", taskKey: "asg:a1", facets: { title: null } },
    ]);
  });

  it("adds clientKey to added tasks and removes on clear", () => {
    const impl = stubFetch();
    const task = { id: "task-add-1", title: "T", dueDate: "2026-09-01T12:00:00-07:00",
                   source: "admin", priority: "medium", done: false, subtasks: [] };
    syncOverlay("thrive:task-added", "task-add-1", task);
    syncOverlay("thrive:task-added", "task-add-1", undefined);
    const ops = sentOps(impl);
    expect(ops[0].op).toBe("task-add");
    expect(ops[0].task.clientKey).toBe("task-add-1");
    expect(ops[1]).toEqual({ op: "task-remove", taskKey: "task-add-1" });
  });

  it("coalesces order writes in one tick into one bulk op", async () => {
    const impl = stubFetch();
    syncOverlay("thrive:task-order", "asg:a1", 1);
    syncOverlay("thrive:task-order", "asg:a2", 2);
    syncOverlay("thrive:task-order", "asg:a3", undefined);
    expect(impl).not.toHaveBeenCalled();     // waits for the microtask
    await Promise.resolve();
    expect(sentOps(impl)).toEqual([
      { op: "task-order-bulk", orders: { "asg:a1": 1, "asg:a2": 2, "asg:a3": null } },
    ]);
  });

  it("debounces calendar prefs and sends the latest", () => {
    const impl = stubFetch();
    syncOverlay("thrive:calendar-prefs", "value", { view: "week" });
    syncOverlay("thrive:calendar-prefs", "value", { view: "agenda" });
    vi.advanceTimersByTime(399);
    expect(impl).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(sentOps(impl)).toEqual([{ op: "calendar-prefs", prefs: { view: "agenda" } }]);
  });

  it("join/ignore map presence to on", () => {
    const impl = stubFetch();
    syncOverlay("thrive:event-joins", "evt-2", true);
    syncOverlay("thrive:ignored-events", "evt-1", undefined);
    expect(sentOps(impl)).toEqual([
      { op: "event-join", eventId: "evt-2", on: true },
      { op: "event-ignore", eventId: "evt-1", on: false },
    ]);
  });

  it("never throws when fetch rejects", async () => {
    const impl = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", impl);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(() => syncOverlay("thrive:task-done", "asg:a1", true)).not.toThrow();
    await Promise.resolve();
    await Promise.resolve();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
```

`frontend/src/routes/overlay-sync/server.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runWithAuth } from "$lib/server/requestContext";
import { POST } from "./+server";

function stubFetch(status = 204, payload: unknown = null) {
  const impl = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  vi.stubGlobal("fetch", impl);
  return impl;
}

function call(body: unknown) {
  const request = new Request("http://localhost/overlay-sync", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return runWithAuth({ cookie: "sessionid=s; csrftoken=t", student: null }, () =>
    POST({ request } as Parameters<typeof POST>[0]),
  );
}

beforeEach(() => vi.stubEnv("THRIVE_API_ORIGIN", "http://api.test"));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("POST /overlay-sync", () => {
  it("forwards task-override to the Django PATCH", async () => {
    const impl = stubFetch(200, {});
    const response = await call({ op: "task-override", taskKey: "asg:a1",
                                  facets: { done: true } });
    expect(response.status).toBe(200);
    const [url, init] = impl.mock.calls[0];
    expect(url).toBe("http://api.test/api/thrive/tasks/asg%3Aa1/override");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ done: true }));
    expect(init.headers["x-csrftoken"]).toBe("t");
  });

  it("projects only the five task-add fields", async () => {
    const impl = stubFetch(201, {});
    await call({ op: "task-add", task: { id: "x", title: "T", done: false,
      dueDate: "2026-09-01T12:00:00-07:00", source: "admin", priority: "low",
      subtasks: [], clientKey: "task-add-1", courseId: "c1" } });
    const sent = JSON.parse(impl.mock.calls[0][1].body as string);
    expect(sent).toEqual({ title: "T", dueDate: "2026-09-01T12:00:00-07:00",
      priority: "low", source: "admin", clientKey: "task-add-1" });
  });

  it("routes on/off ops to PUT vs DELETE", async () => {
    const impl = stubFetch();
    await call({ op: "event-ignore", eventId: "evt-1", on: true });
    await call({ op: "event-ignore", eventId: "evt-1", on: false });
    expect(impl.mock.calls[0][1].method).toBe("PUT");
    expect(impl.mock.calls[1][1].method).toBe("DELETE");
  });

  it("400s unknown ops and passes ApiError envelopes through", async () => {
    stubFetch();
    const bad = await call({ op: "nonsense" });
    expect(bad.status).toBe(400);
    stubFetch(404, { error: { code: "unknown_task", message: "x" } });
    const notFound = await call({ op: "task-override", taskKey: "asg:x",
                                  facets: { done: true } });
    expect(notFound.status).toBe(404);
    expect((await notFound.json()).error.code).toBe("unknown_task");
  });

  it("404s when api mode is off", async () => {
    vi.stubEnv("THRIVE_API_ORIGIN", "");
    const response = await call({ op: "task-override", taskKey: "x",
                                  facets: { done: true } });
    expect(response.status).toBe(404);
  });
});
```

- [ ] **Step 2: Run to verify failure** — modules missing.

- [ ] **Step 3: Implement** both modules per the Interfaces block (the op allowlist in `+server.ts` and the handler table in `overlaySync.ts` are the complete specification; every op/payload pair is pinned by the tests above). TypeScript strict: type op payloads via small interfaces or `Record<string, unknown>` + narrow casts; svelte-check must stay 0/0.

- [ ] **Step 4: Run tests** — both specs PASS, `npm test` green, `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/overlaySync.ts frontend/src/lib/overlaySync.spec.ts frontend/src/routes/overlay-sync
git commit -m "feat(frontend): overlay sync dispatcher and same-origin proxy route"
```

---

### Task 5: Frontend — seed hydration + sync wiring in the store layer

**Files:**
- Modify: `frontend/src/lib/overrideStore.svelte.ts`, `frontend/src/lib/taskNotes.svelte.ts`, `frontend/src/routes/+layout.server.ts`, `frontend/src/routes/+layout.svelte`
- Test: `frontend/src/lib/overrideStore.seed.spec.ts`

**Interfaces:**
- `overrideStore.svelte.ts` — two surgical changes, everything else byte-identical:
  1. `hydrate()` seed-first:
  ```typescript
  	function hydrate(): void {
  		if (hydrated) return;

  		const seeded = seedFor(key);
  		if (seeded) {
  			hydrated = true;
  			values = seeded as Values;
  			return;
  		}

  		const store = storage();
  		if (!store) return;

  		hydrated = true;
  		values = parse(store.getItem(key));
  	}
  ```
  2. `set()` — after `values = next;` add `syncOverlay(key, id, value);` and guard the localStorage write with `if (overlayEnabled()) return;` (server mode never writes localStorage). Import: `import { overlayEnabled, seedFor, syncOverlay } from "./overlaySync";`
- `taskNotes.svelte.ts` — mirrored: `hydrateTaskNotes()` seed-first from `seedFor("thrive:task-notes")` (cast to `NoteMap`); `setNote` adds `syncOverlay(KEY, taskId, trimmed || undefined);` after `notes = next;` and skips the localStorage write when `overlayEnabled()`.
- `+layout.server.ts`: in API mode also fetch the overlay seed:
  ```typescript
  import { getStudent } from '$lib/data';
  import { apiEnabled, apiFetch } from '$lib/data/api/client';
  import type { LayoutServerLoad } from './$types';

  export const load: LayoutServerLoad = async () => {
  	const student = await getStudent();
  	if (!apiEnabled()) return { student };
  	const overlay = await apiFetch<{ stores: Record<string, Record<string, unknown>> }>(
  		'/overlay',
  	);
  	return { student, overlay: { stores: overlay.stores } };
  };
  ```
  (keep the existing doc comment block above the load).
- `+layout.svelte`: the `$effect` becomes (prime BEFORE hydrate; `data.overlay` is `undefined` in mock mode → `primeOverlay(null)` keeps localStorage behavior):
  ```svelte
  	$effect(() => {
  		primeOverlay(data.overlay ?? null);
  		hydrateStores();
  		hydrateTaskNotes();
  	});
  ```
  with `import { primeOverlay } from '$lib/overlaySync';` added.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/overrideStore.seed.spec.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { primeOverlay } from "./overlaySync";

afterEach(() => {
  primeOverlay(null);
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("seed-backed stores", () => {
  it("hydrates from the seed and syncs writes without touching localStorage", async () => {
    const impl = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", impl);
    const setItem = vi.fn();
    vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem });

    primeOverlay({ stores: { "thrive:seed-test": { a: 1 } } });
    const { createOverrideStore } = await import("./overrideStore.svelte");
    const store = createOverrideStore<number>("thrive:seed-test");
    store.hydrate();
    expect(store.read()).toEqual({ a: 1 });

    store.set("b", 2);
    expect(store.read()).toEqual({ a: 1, b: 2 });   // optimistic local state
    expect(setItem).not.toHaveBeenCalled();           // no localStorage in API mode
    // no handler for thrive:seed-test → no network either
    expect(impl).not.toHaveBeenCalled();
  });

  it("falls back to localStorage when unprimed", async () => {
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => JSON.stringify({ x: true })),
      setItem: vi.fn(),
    });
    const { createOverrideStore } = await import("./overrideStore.svelte");
    const store = createOverrideStore<boolean>("thrive:seed-test-2");
    store.hydrate();
    expect(store.read()).toEqual({ x: true });
  });

  it("task notes hydrate from the seed and sync via task-note op", async () => {
    const impl = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", impl);
    vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem: vi.fn() });
    primeOverlay({ stores: { "thrive:task-notes": { "asg:a1": "hi" } } });

    const notes = await import("./taskNotes.svelte");
    notes.hydrateTaskNotes();
    expect(notes.taskNotes()).toEqual({ "asg:a1": "hi" });

    notes.setNote("asg:a2", "  new note ");
    expect(notes.taskNotes()["asg:a2"]).toBe("new note");
    const sent = JSON.parse(impl.mock.calls[0][1].body as string);
    expect(sent).toEqual({ op: "task-note", taskKey: "asg:a2", note: "new note" });
  });
});
```

- [ ] **Step 2: Run to verify failure** — seed cases FAIL (stores read localStorage only).

- [ ] **Step 3: Implement** the four files exactly per the Interfaces block. Do not alter any other line of `overrideStore.svelte.ts`/`taskNotes.svelte.ts` — the doc comments describing localStorage stay (they describe the fallback path; add one sentence to each file's header noting the seed-first branch, e.g. "In API mode the same contract is served by the server seed primed from the root layout.").

- [ ] **Step 4: Run tests** — new spec PASS; **full `npm test` (all suites — the 672 existing tests pin the mock path)**; `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): stores hydrate from the server seed and sync writes"
```

---

### Task 6: Frontend — source-view tasks + end-to-end store wiring tests

**Files:**
- Modify: `frontend/src/lib/data/api/providers.ts` (getTasks only)
- Test: `frontend/src/lib/storeWiring.spec.ts`; update the one assertion in `frontend/src/lib/data/api/providers.spec.ts` for getTasks' path

**Interfaces:**
- `api/providers.ts`: `getTasks` becomes `apiFetch<Task[]>("/tasks?view=source")` — in API mode the client owns the merge (stores seeded from the server), so the provider must deliver SOURCE tasks exactly like the mock does; the merged `/tasks` remains for the contract suite. Update the existing endpoint-table test accordingly.
- `storeWiring.spec.ts` — integration tests driving the REAL store functions (userEdits etc.) with a primed seed and stubbed fetch, pinning the exact wire payloads that the per-module specs cannot see:
  - `setTaskDone(sourceTask, true)` on a source-done=false task → `task-override {done: true}`; `setTaskDone(sourceTask, false)` (match) → `{done: null}` (forget-on-match ships a clear).
  - `addTask(task)` → `task-add` with `clientKey === task.id`; `removeAddedTask(id)` → `task-remove` among the ops (the five sibling override clears may also fire — assert the remove op is present, not the exact op count).
  - `reorderWithin([a, b])` → exactly ONE `task-order-bulk` after a microtask flush.
  - `setEventIgnored("evt-1", true)` → `event-ignore on:true`.
  - `setCalendarPrefs({view: "week"})` → after 400 ms fake-timer advance, ONE `calendar-prefs` op whose `prefs.view === "week"` (the store writes the whole normalized object — assert the field, not deep equality).
  - `setItemLabel("apt-3", "Chat")` → `item-label`; `addQuickItem("milk")` → `quick-put` with `item.title === "milk"`.

- [ ] **Step 1: Write the failing tests** (storeWiring.spec.ts imports the real modules: `$lib/userEdits.svelte`, `$lib/ignoredEvents`, `$lib/calendarPrefs`, `$lib/calendarItems`, `$lib/quickList`; prime the seed with EMPTY store records for each key it touches so hydration is seed-backed; stub fetch + localStorage; use `vi.useFakeTimers()` for the prefs case and `await Promise.resolve()` for the order flush. Write each case to assert the payloads named in the Interfaces block.)

- [ ] **Step 2: Run to verify failure** — getTasks path test fails (still `/tasks`); wiring cases fail until Tasks 4–5 behaviors compose (if Tasks 4–5 landed correctly most wiring cases pass immediately — that is fine; the failing getTasks assertion is the TDD anchor).

- [ ] **Step 3: Implement** the one-line getTasks change; fix anything the wiring tests surface.

- [ ] **Step 4: Run tests** — `npm test` green (all suites), `npm run check` 0/0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): source-view tasks and store wiring coverage"
```

---

### Task 7: Gates + extended end-to-end smoke

**Files:** none expected; fix fallout if gates surface any (report what/why).

- [ ] **Step 1: Frontend gates** (from `frontend/`): `npm test`, `npm run check` (0/0), `npm run build`, `python3 ../scripts/check-contrast.py`, `npm run check:layout`, `npm run check:interaction`, plus the timezone sweep per `../docs/upstream/setup_info.md`.

- [ ] **Step 2: Backend suite** — `cd ../backend && uv run pytest -q` (0 warnings).

- [ ] **Step 3: End-to-end smoke** — same skeleton as F4a's Task 8 script (same-hostname NOTE applies: use `localhost` for BOTH servers everywhere), extended after the login steps:

```bash
# 4. Overlay round-trip through the proxy: ignore an event as the browser would
curl -s -b $JAR -c $JAR -o /dev/null -w "%{http_code}\n" \
  -H "content-type: application/json" \
  -d '{"op":"event-ignore","eventId":"evt-demo-1","on":true}' \
  http://localhost:3123/overlay-sync
# expect: 200

# 5. The seed reflects it (through Django directly)
curl -s -b $JAR http://localhost:8123/api/thrive/overlay | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d['stores']['thrive:ignored-events'])"
# expect: {'evt-demo-1': True}

# 6. And the dashboard still renders
curl -s -b $JAR http://localhost:3123/ | grep -o "Demo Student" | head -1
# expect: Demo Student
```

Record every command's actual output in the report. Debug and fix if anything fails — this is the phase's definition of done.

- [ ] **Step 4: Commit any fixes** (`test(f4b): gates green and overlay smoke passing`), or state "no fixes needed".

---

## Plan Self-Review (completed at authoring)

- **Spec coverage:** all 14 persisted localStorage keys have a server path (10 via existing F1 endpoints + 4 new model groups); the three deliberately-local keys are named in scope; BACKEND.md §7's forget-on-match rule survives because the client computes it against SOURCE tasks (Task 1's `view=source` + Task 6's getTasks change) and clears sync as explicit nulls; the hydration contract ("empty on server, real after mount") is preserved by priming inside the same `$effect`.
- **Placeholder scan:** Task 4's Step 3 refers to its Interfaces table + tests as the complete op-by-op specification (each op's path/method/body is enumerated there and pinned by test assertions); Task 6's Step 1 enumerates every assertion in prose with exact payloads. No TBDs.
- **Type consistency:** `primeOverlay/overlayEnabled/seedFor/syncOverlay` signatures identical across Tasks 4–6; op names and payload keys match between the handler table, the proxy allowlist, and both spec files; `clientKey` semantics match Task 1's backend (upsert, reserved-prefix rejection); the seed's store shapes (Task 3) mirror the exact `Record` layouts the frontend persists (verified against overrideStore/userEdits/calendarItems/quickList/calendarPrefs/taskNotes line references from recon).
