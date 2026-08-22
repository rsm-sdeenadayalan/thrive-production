# F2b — Course Requests + Living Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the remaining 11 contract providers as API endpoints: course action requests (TSS/EASy-style drafts → submit, with a prefill snapshot) and the living resume (skills, versioned resumes with deterministic generation + diff, current-version switching).

**Architecture:** Extends the F1/F2a `rsm_thrive` app with the established pattern: models (+ one partial unique constraint for "exactly one current resume version"), thin views, contract-exact serializers, sorts server-side, contract-test schemas. Resume versions store their skills/courses/experience as frozen contract-shaped JSON snapshots (a version is a historical record — it must not change when live data does). Generation is deterministic template logic ported verbatim from the frontend mock (`composeSummary`); an LLM-written summary is a Phase C enhancement behind the same endpoint.

**Tech Stack:** Python ≥3.12, Django ≥5.2, uv, pytest + pytest-django (no new dependencies).

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §4 (course-request + resume provider rows). Semantics source of truth: `frontend/src/lib/data/providers.ts:300-517` and `types.ts` (CourseRequest*, Skill, Resume*). Out of scope: resume upload/parsing (Phase J), LLM summaries (Phase C).

## Global Constraints

- camelCase keys matching `types.ts` exactly. Closed unions verbatim, including literals with spaces: CourseRequestType `"enroll" | "drop" | "reduced load" | "out of major"`; CourseRequestStatus `draft|submitted|approved|denied`; SkillSource `course|manual`.
- `CourseRequest` JSON: `{id, type, course, reason, status, submittedAt, prefill}` — ALL keys required; `submittedAt` is `null` while draft, ISO instant after. `prefill` is the snapshot **taken at creation**, never recomputed (`types.ts`: "a submitted request should show what was actually sent").
- `CourseRequestPrefill`: `{studentName, program, track, term, currentCourses, currentUnits, unitsCompleted, unitsRequired}`; `currentCourses` entries are `f"{code} · {title}"` — **middle dot U+00B7, byte-exact** (providers.ts:314).
- Requests list sort (providers.ts:367-381): drafts first (in creation order), then submitted by `submittedAt` desc.
- `submitRequest` is idempotent (providers.ts:342-365): non-draft comes back unchanged (200), never re-stamped; unknown/not-owned → 404 (frontend maps to `null`).
- TSS: `GET /tss` → `{"connected": bool}`; `POST /tss/connect` → `{"connected": true}` (providers return plain booleans; F4 unwraps).
- ResumeVersion JSON: `{id, label, createdAt, summary, skills, courses, experience, isCurrent}` all required; versions list newest-first (createdAt desc, pk desc); **exactly one current version per user**, enforced by a partial unique constraint; `getCurrentResume` with no versions → 404 (frontend maps to null); `setCurrentVersion` unknown id → 404 and must NOT clear the existing current.
- `generateNewVersion` → 201 `{"version": {...}, "diff": {addedSkills, addedCourses, summaryChanged}}`; summary template byte-exact from providers.ts:430-437: `f"{program} candidate at UC San Diego working toward a {goal} role. Coursework and projects across {headline}"` + (`f", and {n-4} more."` when >4 skills else `"."`) where headline = first 4 skill names comma-joined; diff `addedCourses` entries use the `"CODE · TITLE"` format; experience carries forward from the previous current version (student-authored).
- Instants via `iso_instant`; unauthenticated → 401 envelope; error envelope everywhere; unseeded degree data in prefill → 503 `not_configured` (reuses the F1 `NotConfigured` pattern).
- All commands from `backend/` via `uv run`; commit per task on `main`.

---

### Task 1: Models + factories

**Files:**
- Create: `backend/rsm_thrive/models/requests.py`, `backend/rsm_thrive/models/resume.py`
- Modify: `backend/rsm_thrive/models/students.py` (add one field), `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`
- Test: `backend/rsm_thrive/tests/test_f2b_models.py`

**Interfaces:**
- Produces models:
  - `CourseRequest(user FK, type: Char16 choices enroll|drop|"reduced load"|"out of major", course: Char200, reason: Text, status: Char16 choices draft|submitted|approved|denied default "draft", submitted_at: DateTime null blank, prefill: JSONField default dict, created_at auto_now_add)`
  - `StudentProfile.tss_connected = models.BooleanField(default=False)` (new field on the existing model)
  - `Skill(user FK, name: Char120, source: Char16 choices course|manual default "manual", course FK "rsm_thrive.Course" null blank on_delete=SET_NULL)`
  - `ResumeCourseHighlight(code: Char32 unique, title: Char200, highlight: Char240)` — catalog of "what this course lets you claim", matched against enrolled course codes at generation time.
  - `ResumeVersion(user FK, label: Char120, created_at auto_now_add, summary: Text, skills: JSON list, courses: JSON list, experience: JSON list, is_current: Bool default False)` with `UniqueConstraint(fields=["user"], condition=Q(is_current=True), name="uniq_current_resume")`.
- Factories: `make_skill(profile, **overrides)` (defaults name "Skill <n>", source "manual"); `make_highlight(code, **overrides)` (defaults title "Course <code>", highlight "Can analyze data"); `make_course_request(profile, **overrides)` (defaults type "enroll", course "MGTA 999 · Test Course", reason "why", prefill {}).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_f2b_models.py`:

```python
import pytest
from django.db import IntegrityError, transaction

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_course_request, make_skill, make_student

pytestmark = pytest.mark.django_db


def test_only_one_current_resume_version_per_user():
    profile = make_student()
    ResumeVersion.objects.create(user=profile.user, label="v1", summary="s",
                                 is_current=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ResumeVersion.objects.create(user=profile.user, label="v2",
                                         summary="s", is_current=True)
    # a different user's current is unaffected
    other = make_student(username="other")
    ResumeVersion.objects.create(user=other.user, label="v1", summary="s",
                                 is_current=True)


def test_request_and_skill_factories():
    profile = make_student()
    req = make_course_request(profile)
    assert req.status == "draft" and req.submitted_at is None
    skill = make_skill(profile, name="SQL")
    assert skill.source == "manual" and skill.course_id is None
    assert profile.tss_connected is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_f2b_models.py -v` — Expected: FAIL (imports).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/requests.py`:

```python
from django.conf import settings
from django.db import models

REQUEST_TYPE_CHOICES = [
    ("enroll", "enroll"), ("drop", "drop"),
    ("reduced load", "reduced load"), ("out of major", "out of major"),
]
REQUEST_STATUS_CHOICES = [
    ("draft", "draft"), ("submitted", "submitted"),
    ("approved", "approved"), ("denied", "denied"),
]


class CourseRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=16, choices=REQUEST_TYPE_CHOICES)
    course = models.CharField(max_length=200)
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=REQUEST_STATUS_CHOICES,
                              default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    prefill = models.JSONField(default=dict)  # snapshot at creation, never recomputed
    created_at = models.DateTimeField(auto_now_add=True)
```

`backend/rsm_thrive/models/resume.py`:

```python
from django.conf import settings
from django.db import models
from django.db.models import Q

SKILL_SOURCE_CHOICES = [("course", "course"), ("manual", "manual")]


class Skill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    source = models.CharField(max_length=16, choices=SKILL_SOURCE_CHOICES,
                              default="manual")
    course = models.ForeignKey("rsm_thrive.Course", null=True, blank=True,
                               on_delete=models.SET_NULL)


class ResumeCourseHighlight(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
    highlight = models.CharField(max_length=240)


class ResumeVersion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.TextField()
    skills = models.JSONField(default=list)      # frozen contract-shaped snapshots
    courses = models.JSONField(default=list)
    experience = models.JSONField(default=list)
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=Q(is_current=True),
                                    name="uniq_current_resume"),
        ]
```

`models/students.py`: add `tss_connected = models.BooleanField(default=False)` to `StudentProfile` (after the consent fields). Re-export the three new models in `models/__init__.py` (alphabetical by module). Factories appended to `testing.py` (merge imports):

```python
from rsm_thrive.models import CourseRequest, ResumeCourseHighlight, Skill


def make_skill(profile, **overrides) -> Skill:
    n = next(_counter)
    fields = {"name": f"Skill {n}", "source": "manual"}
    fields.update(overrides)
    return Skill.objects.create(user=profile.user, **fields)


def make_highlight(code, **overrides) -> ResumeCourseHighlight:
    fields = {"title": f"Course {code}", "highlight": "Can analyze data"}
    fields.update(overrides)
    return ResumeCourseHighlight.objects.create(code=code, **fields)


def make_course_request(profile, **overrides) -> CourseRequest:
    fields = {"type": "enroll", "course": "MGTA 999 · Test Course",
              "reason": "why", "prefill": {}}
    fields.update(overrides)
    return CourseRequest.objects.create(user=profile.user, **fields)
```

- [ ] **Step 4: Migrate + run tests** — `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): course request and resume models"
```

---

### Task 2: Prefill service + GET /requests/prefill

**Files:**
- Create: `backend/rsm_thrive/services/requests.py`, `backend/rsm_thrive/serializers/requests.py`, `backend/rsm_thrive/views/requests.py`
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_prefill.py`

**Interfaces:**
- Consumes: `Enrollment`, `degree_progress`/`NotConfigured` (services/degree.py), `iso_instant`, http helpers.
- Produces: `services.requests.build_prefill(profile) -> dict` (raises `NotConfigured` when degree data unseeded); `serializers.requests.request_payload(req) -> dict`; route `GET /api/thrive/requests/prefill`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_prefill.py`:

```python
import pytest

from rsm_thrive.testing import enroll, make_course, make_requirement, make_student

pytestmark = pytest.mark.django_db


def test_prefill_shape_and_course_format(client):
    profile = make_student(display_name="Ada Lovelace", goal="Data Scientist")
    make_requirement("11 month", units_required=50)
    c1 = make_course(id="c1", code="MGTA 453", title="Business Analytics", units=4)
    c2 = make_course(id="c2", code="MGTA 495", title="Special Topics", units=2)
    done = make_course(id="c3", code="MGTA 400", title="Done Course", units=4)
    enroll(profile, c1)
    enroll(profile, c2)
    enroll(profile, done, completed=True)

    client.force_login(profile.user)
    body = client.get("/api/thrive/requests/prefill").json()
    assert body == {
        "studentName": "Ada Lovelace",
        "program": "MSBA",
        "track": "11 month",
        "term": "Fall 2026",
        "currentCourses": ["MGTA 400 · Done Course", "MGTA 453 · Business Analytics",
                           "MGTA 495 · Special Topics"],
        "currentUnits": 10,
        "unitsCompleted": 4,
        "unitsRequired": 50,
    }


def test_prefill_unseeded_degree_503(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/requests/prefill")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "not_configured"
```

- [ ] **Step 2: Run to verify failure** — Expected: 404.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/services/requests.py`:

```python
"""Course-request prefill: the student record snapshot frozen onto each request."""
from rsm_thrive.models import Enrollment
from rsm_thrive.services.degree import degree_progress


def build_prefill(profile) -> dict:
    enrollments = (Enrollment.objects.filter(user=profile.user)
                   .select_related("course").order_by("course__code"))
    degree = degree_progress(profile)  # raises NotConfigured when unseeded
    return {
        "studentName": profile.display_name,
        "program": profile.program,
        "track": profile.track,
        "term": profile.current_term,
        "currentCourses": [f"{e.course.code} · {e.course.title}" for e in enrollments],
        "currentUnits": sum(e.course.units for e in enrollments),
        "unitsCompleted": degree["unitsCompleted"],
        "unitsRequired": degree["unitsRequired"],
    }
```

`backend/rsm_thrive/serializers/requests.py`:

```python
from rsm_thrive.serialize import iso_instant


def request_payload(req) -> dict:
    return {
        "id": f"req-{req.pk}",
        "type": req.type,
        "course": req.course,
        "reason": req.reason,
        "status": req.status,
        "submittedAt": iso_instant(req.submitted_at) if req.submitted_at else None,
        "prefill": req.prefill,
    }
```

`backend/rsm_thrive/views/requests.py`:

```python
from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.services.degree import NotConfigured
from rsm_thrive.services.requests import build_prefill


@api_login_required
def prefill(request):
    try:
        return json_ok(build_prefill(request.user.thrive_profile))
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)
```

Route (place BEFORE any parameterized `requests/...` path): `path("requests/prefill", requests.prefill, name="request-prefill")` — add `requests` to the alphabetical views import (as `requests` collides with nothing in urls.py).

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): course request prefill endpoint"
```

---

### Task 3: POST /requests + GET /requests

**Files:**
- Modify: `backend/rsm_thrive/views/requests.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_requests.py`

**Interfaces:**
- Produces: `GET /api/thrive/requests` (drafts first in creation order, then submitted by submitted_at desc); `POST /api/thrive/requests` body `{"type", "course", "reason"}` → 201 `request_payload` with the prefill snapshot frozen in. Validation: type ∈ the four literals; course/reason non-empty strings (trimmed); errors → 400 `bad_request`; unseeded degree during prefill → 503 `not_configured`. Route uses a GET/POST dispatcher (405 envelope otherwise).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_requests.py`:

```python
import datetime as dt
import json

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_course_request, make_requirement, make_student

pytestmark = pytest.mark.django_db


def _post(client, body):
    return client.post("/api/thrive/requests", data=json.dumps(body),
                       content_type="application/json")


def test_create_request_freezes_prefill(client):
    profile = make_student()
    make_requirement("11 month")
    client.force_login(profile.user)
    resp = _post(client, {"type": "reduced load", "course": "  Term-wide  ",
                          "reason": " health "})
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "reduced load"
    assert body["course"] == "Term-wide" and body["reason"] == "health"
    assert body["status"] == "draft" and body["submittedAt"] is None
    assert body["prefill"]["track"] == "11 month"
    assert body["prefill"]["currentCourses"] == []


def test_create_request_validation(client):
    profile = make_student()
    make_requirement("11 month")
    client.force_login(profile.user)
    assert _post(client, {"type": "audit", "course": "x", "reason": "y"}).status_code == 400
    assert _post(client, {"type": "drop", "course": "  ", "reason": "y"}).status_code == 400
    assert _post(client, {"type": "drop", "course": "x", "reason": None}).status_code == 400


def test_list_drafts_first_then_newest_submitted(client):
    profile = make_student()
    now = timezone.now()
    old = make_course_request(profile, status="submitted",
                              submitted_at=now - dt.timedelta(days=2))
    new = make_course_request(profile, status="submitted",
                              submitted_at=now - dt.timedelta(days=1))
    d1 = make_course_request(profile)   # drafts keep creation order
    d2 = make_course_request(profile)
    other = make_student(username="other")
    make_course_request(other)          # not mine

    client.force_login(profile.user)
    ids = [r["id"] for r in client.get("/api/thrive/requests").json()]
    assert ids == [f"req-{d1.pk}", f"req-{d2.pk}", f"req-{new.pk}", f"req-{old.pk}"]
```

- [ ] **Step 2: Run to verify failure** — Expected: 404/405.

- [ ] **Step 3: Implement**

Append to `views/requests.py`:

```python
from rsm_thrive.http import BadRequest, parse_body
from rsm_thrive.models import CourseRequest
from rsm_thrive.serializers.requests import request_payload

VALID_REQUEST_TYPES = {"enroll", "drop", "reduced load", "out of major"}


@api_login_required
def my_requests(request):
    rows = list(CourseRequest.objects.filter(user=request.user))
    rows.sort(key=lambda r: (
        r.submitted_at is not None,                                   # drafts first
        -(r.submitted_at.timestamp() if r.submitted_at else 0),      # newest submitted
        r.pk,                                                         # drafts: creation order
    ))
    return json_ok([request_payload(r) for r in rows])


@api_login_required
def create_request(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    req_type = body.get("type")
    course = body.get("course")
    reason = body.get("reason")
    if req_type not in VALID_REQUEST_TYPES:
        return json_error("bad_request", "type must be a known request type.", 400)
    if not isinstance(course, str) or not course.strip():
        return json_error("bad_request", "course is required.", 400)
    if not isinstance(reason, str) or not reason.strip():
        return json_error("bad_request", "reason is required.", 400)
    try:
        snapshot = build_prefill(request.user.thrive_profile)
    except NotConfigured as exc:
        return json_error("not_configured", str(exc), 503)
    row = CourseRequest.objects.create(
        user=request.user, type=req_type, course=course.strip(),
        reason=reason.strip(), prefill=snapshot,
    )
    return json_ok(request_payload(row), status=201)


def requests_dispatch(request):
    if request.method == "GET":
        return my_requests(request)
    if request.method == "POST":
        return create_request(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
```

Route: `path("requests", requests.requests_dispatch, name="requests")` (after `requests/prefill`).

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): create and list course requests with frozen prefill"
```

---

### Task 4: Submit request + TSS endpoints

**Files:**
- Modify: `backend/rsm_thrive/views/requests.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_submit_tss.py`

**Interfaces:**
- Produces:
  - `POST /api/thrive/requests/req-<pk>/submit` — draft → atomic conditional update (`status="draft"` → `"submitted"`, `submitted_at=now`), 200 payload; already-submitted/approved/denied → 200 payload UNCHANGED (idempotent, never re-stamped); unknown/not-owned/malformed id → 404 `unknown_request` (guard: prefix `req-`, `isascii() and isdigit()` — same pattern as appointments).
  - `GET /api/thrive/tss` → `{"connected": <profile.tss_connected>}`; `POST /api/thrive/tss/connect` → sets True, returns `{"connected": true}`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_submit_tss.py`:

```python
import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import make_course_request, make_student

pytestmark = pytest.mark.django_db


def test_submit_draft_then_idempotent(client):
    profile = make_student()
    req = make_course_request(profile)
    client.force_login(profile.user)

    first = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert first["status"] == "submitted" and first["submittedAt"] is not None

    second = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert second == first  # unchanged, not re-stamped


def test_submit_never_demotes_approved(client):
    profile = make_student()
    stamp = timezone.now() - dt.timedelta(days=3)
    req = make_course_request(profile, status="approved", submitted_at=stamp)
    client.force_login(profile.user)
    body = client.post(f"/api/thrive/requests/req-{req.pk}/submit").json()
    assert body["status"] == "approved"


def test_submit_unknown_and_malformed_404(client):
    profile = make_student()
    other = make_student(username="other")
    theirs = make_course_request(other)
    client.force_login(profile.user)
    for bad in (f"req-{theirs.pk}", "req-99999", "banana", "req-²"):
        assert client.post(f"/api/thrive/requests/{bad}/submit").status_code == 404


def test_tss_connect_roundtrip(client):
    profile = make_student()
    client.force_login(profile.user)
    assert client.get("/api/thrive/tss").json() == {"connected": False}
    assert client.post("/api/thrive/tss/connect").json() == {"connected": True}
    assert client.get("/api/thrive/tss").json() == {"connected": True}
    assert profile.user.thrive_profile.tss_connected or True  # persisted below
    from rsm_thrive.models import StudentProfile
    assert StudentProfile.objects.get(user=profile.user).tss_connected is True
```

- [ ] **Step 2: Run to verify failure** — Expected: 404s.

- [ ] **Step 3: Implement**

Append to `views/requests.py`:

```python
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from rsm_thrive.models import StudentProfile


def _own_request(user, request_id):
    if not request_id.startswith("req-"):
        return None
    pk = request_id.removeprefix("req-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return CourseRequest.objects.filter(pk=pk, user=user).first()


@api_login_required
@require_http_methods(["POST"])
def submit_request(request, request_id):
    row = _own_request(request.user, request_id)
    if row is None:
        return json_error("unknown_request", f"No request {request_id}.", 404)
    CourseRequest.objects.filter(pk=row.pk, status="draft").update(
        status="submitted", submitted_at=timezone.now())
    row.refresh_from_db()
    return json_ok(request_payload(row))


@api_login_required
def tss(request):
    return json_ok({"connected": request.user.thrive_profile.tss_connected})


@api_login_required
@require_http_methods(["POST"])
def tss_connect(request):
    StudentProfile.objects.filter(user=request.user).update(tss_connected=True)
    return json_ok({"connected": True})
```

Routes: `path("requests/<str:request_id>/submit", requests.submit_request, name="request-submit")`, `path("tss", requests.tss, name="tss")`, `path("tss/connect", requests.tss_connect, name="tss-connect")`.

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): idempotent request submission and TSS connection"
```

---

### Task 5: GET /resume/skills

**Files:**
- Create: `backend/rsm_thrive/serializers/resume.py`, `backend/rsm_thrive/views/resume.py`
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_skills.py`

**Interfaces:**
- Produces: `serializers.resume.skill_payload(skill) -> dict` (`{id: "skill-<pk>", name, source, optional courseId}`); route `GET /api/thrive/resume/skills` — own skills, ordered (name, pk).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_skills.py`:

```python
import pytest

from rsm_thrive.testing import enroll, make_course, make_skill, make_student

pytestmark = pytest.mark.django_db


def test_skills_shape_and_order(client):
    profile = make_student()
    course = make_course(id="c1")
    enroll(profile, course)
    sql = make_skill(profile, name="SQL", source="course", course=course)
    ab = make_skill(profile, name="A/B Testing")
    other = make_student(username="other")
    make_skill(other, name="Theirs")

    client.force_login(profile.user)
    body = client.get("/api/thrive/resume/skills").json()
    assert [s["name"] for s in body] == ["A/B Testing", "SQL"]
    assert body[1] == {"id": f"skill-{sql.pk}", "name": "SQL",
                       "source": "course", "courseId": "c1"}
    assert "courseId" not in body[0]
```

- [ ] **Step 2: Run to verify failure** — Expected: 404.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/serializers/resume.py`:

```python
from rsm_thrive.serialize import iso_instant


def skill_payload(skill) -> dict:
    payload = {"id": f"skill-{skill.pk}", "name": skill.name, "source": skill.source}
    if skill.course_id:
        payload["courseId"] = skill.course_id
    return payload


def version_payload(version) -> dict:
    return {
        "id": f"rv-{version.pk}",
        "label": version.label,
        "createdAt": iso_instant(version.created_at),
        "summary": version.summary,
        "skills": version.skills,
        "courses": version.courses,
        "experience": version.experience,
        "isCurrent": version.is_current,
    }
```

`backend/rsm_thrive/views/resume.py`:

```python
from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Skill
from rsm_thrive.serializers.resume import skill_payload, version_payload


@api_login_required
def skills(request):
    rows = Skill.objects.filter(user=request.user).order_by("name", "pk")
    return json_ok([skill_payload(s) for s in rows])
```

Route: `path("resume/skills", resume.skills, name="resume-skills")` (add `resume` to the alphabetical views import).

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): GET /resume/skills"
```

---

### Task 6: Resume version reads

**Files:**
- Modify: `backend/rsm_thrive/views/resume.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_resume_reads.py`

**Interfaces:**
- Produces: `GET /api/thrive/resume/versions` (own, ordered created_at desc then pk desc); `GET /api/thrive/resume/current` (the is_current row; none → 404 `no_resume`). Versions route registers a GET/POST dispatcher (`resume_versions_dispatch`; POST → `generate` arrives in Task 7 — until then POST returns 405 like the F2a pattern).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_resume_reads.py`:

```python
import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _mk(profile, label, current=False):
    return ResumeVersion.objects.create(
        user=profile.user, label=label, summary="s",
        skills=[{"id": "skill-1", "name": "SQL", "source": "manual"}],
        courses=[{"code": "MGTA 453", "title": "BA", "highlight": "h"}],
        experience=[], is_current=current,
    )


def test_versions_newest_first_and_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1")
    v2 = _mk(profile, "v2", current=True)
    client.force_login(profile.user)

    body = client.get("/api/thrive/resume/versions").json()
    assert [v["id"] for v in body] == [f"rv-{v2.pk}", f"rv-{v1.pk}"]
    assert body[0]["isCurrent"] is True and body[1]["isCurrent"] is False
    assert body[0]["skills"][0]["name"] == "SQL"

    current = client.get("/api/thrive/resume/current").json()
    assert current["id"] == f"rv-{v2.pk}"


def test_current_404_when_none(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/resume/current")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_resume"
```

- [ ] **Step 2: Run to verify failure** — Expected: 404 (route missing) — note the current test expects OUR 404 envelope, not Django's.

- [ ] **Step 3: Implement**

Append to `views/resume.py`:

```python
from rsm_thrive.models import ResumeVersion


@api_login_required
def resume_versions(request):
    rows = (ResumeVersion.objects.filter(user=request.user)
            .order_by("-created_at", "-pk"))
    return json_ok([version_payload(v) for v in rows])


@api_login_required
def resume_current(request):
    row = ResumeVersion.objects.filter(user=request.user, is_current=True).first()
    if row is None:
        return json_error("no_resume", "No resume versions yet.", 404)
    return json_ok(version_payload(row))


def resume_versions_dispatch(request):
    if request.method == "GET":
        return resume_versions(request)
    if request.method == "POST":
        return generate_version_view(request)  # Task 7
    return json_error("method_not_allowed", "Use GET or POST.", 405)
```

For THIS task, stub the POST branch as `return json_error("method_not_allowed", "Use GET or POST.", 405)` — Task 7 replaces it. Routes: `path("resume/versions", resume.resume_versions_dispatch, name="resume-versions")`, `path("resume/current", resume.resume_current, name="resume-current")`.

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): resume version reads with current lookup"
```

---

### Task 7: Generate new version (service + POST /resume/versions)

**Files:**
- Create: `backend/rsm_thrive/services/resume.py`
- Modify: `backend/rsm_thrive/views/resume.py`
- Test: `backend/rsm_thrive/tests/test_resume_generate.py`

**Interfaces:**
- Produces `services.resume`:
  - `compose_summary(goal: str, program: str, skill_names: list[str]) -> str` — byte-exact port of providers.ts:430-437.
  - `generate_version(profile) -> tuple[ResumeVersion, dict]` — snapshot skills (contract-shaped, ordered name/pk), resume courses = `ResumeCourseHighlight` rows whose code matches an enrolled course (ordered code), summary composed, diff vs previous current (`addedSkills` by name, `addedCourses` as `"CODE · TITLE"`, `summaryChanged`), experience carried from previous current (else `[]`), label `f"Regenerated from {profile.current_term} courses"`; inside `transaction.atomic()`: clear old current, create new current.
- View: POST branch of `resume_versions_dispatch` → 201 `{"version": version_payload(...), "diff": {...}}`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_resume_generate.py`:

```python
import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import (
    enroll, make_course, make_highlight, make_skill, make_student,
)

pytestmark = pytest.mark.django_db


def _setup(client):
    profile = make_student(goal="Data Scientist")   # program MSBA
    course = make_course(id="c1", code="MGTA 453", title="Business Analytics")
    enroll(profile, course)
    make_highlight("MGTA 453", title="Business Analytics",
                   highlight="Regression at scale")
    make_highlight("MGTA 999")                       # not enrolled: excluded
    for name in ("SQL", "Python", "Causal Inference", "Dashboards", "ML"):
        make_skill(profile, name=name)
    client.force_login(profile.user)
    return profile


def test_generate_first_version(client):
    _setup(client)
    resp = client.post("/api/thrive/resume/versions")
    assert resp.status_code == 201
    body = resp.json()
    version, diff = body["version"], body["diff"]
    assert version["isCurrent"] is True
    assert version["label"] == "Regenerated from Fall 2026 courses"
    assert version["summary"] == (
        "MSBA candidate at UC San Diego working toward a Data Scientist role. "
        "Coursework and projects across Causal Inference, Dashboards, ML, Python, "
        "and 1 more."
    )
    assert version["courses"] == [{"code": "MGTA 453", "title": "Business Analytics",
                                   "highlight": "Regression at scale"}]
    assert version["experience"] == []
    assert sorted(diff["addedSkills"]) == sorted(
        ["SQL", "Python", "Causal Inference", "Dashboards", "ML"])
    assert diff["addedCourses"] == ["MGTA 453 · Business Analytics"]
    assert diff["summaryChanged"] is True


def test_generate_second_version_diffs_and_carries_experience(client):
    profile = _setup(client)
    client.post("/api/thrive/resume/versions")
    first = ResumeVersion.objects.get(user=profile.user, is_current=True)
    first.experience = [{"id": "exp-1", "title": "Analyst", "organization": "Rady",
                         "period": "2026 - present", "bullets": ["did things"]}]
    first.save(update_fields=["experience"])
    make_skill(profile, name="Zsh")

    body = client.post("/api/thrive/resume/versions").json()
    assert body["diff"]["addedSkills"] == ["Zsh"]
    assert body["diff"]["addedCourses"] == []
    assert body["version"]["experience"][0]["title"] == "Analyst"
    assert ResumeVersion.objects.filter(user=profile.user, is_current=True).count() == 1
    assert ResumeVersion.objects.filter(user=profile.user).count() == 2
```

- [ ] **Step 2: Run to verify failure** — Expected: 405 (stub).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/services/resume.py`:

```python
"""Deterministic resume generation, ported from the frontend mock verbatim.
An LLM-written summary is a Phase C enhancement behind the same seam."""
from django.db import transaction

from rsm_thrive.models import Enrollment, ResumeCourseHighlight, ResumeVersion, Skill
from rsm_thrive.serializers.resume import skill_payload


def compose_summary(goal: str, program: str, skill_names: list[str]) -> str:
    headline = ", ".join(skill_names[:4])
    tail = (f", and {len(skill_names) - 4} more."
            if len(skill_names) > 4 else ".")
    return (f"{program} candidate at UC San Diego working toward a {goal} role. "
            f"Coursework and projects across {headline}{tail}")


def generate_version(profile):
    user = profile.user
    previous = ResumeVersion.objects.filter(user=user, is_current=True).first()

    skills = [skill_payload(s)
              for s in Skill.objects.filter(user=user).order_by("name", "pk")]
    enrolled_codes = set(
        Enrollment.objects.filter(user=user).values_list("course__code", flat=True))
    resume_courses = [
        {"code": h.code, "title": h.title, "highlight": h.highlight}
        for h in ResumeCourseHighlight.objects.filter(code__in=enrolled_codes)
                                              .order_by("code")
    ]
    summary = compose_summary(profile.goal, profile.program,
                              [s["name"] for s in skills])

    prev_skill_names = {s["name"] for s in (previous.skills if previous else [])}
    prev_codes = {c["code"] for c in (previous.courses if previous else [])}
    diff = {
        "addedSkills": [s["name"] for s in skills
                        if s["name"] not in prev_skill_names],
        "addedCourses": [f"{c['code']} · {c['title']}" for c in resume_courses
                         if c["code"] not in prev_codes],
        "summaryChanged": (previous.summary if previous else None) != summary,
    }
    with transaction.atomic():
        ResumeVersion.objects.filter(user=user, is_current=True).update(
            is_current=False)
        version = ResumeVersion.objects.create(
            user=user,
            label=f"Regenerated from {profile.current_term} courses",
            summary=summary,
            skills=skills,
            courses=resume_courses,
            experience=(previous.experience if previous else []),
            is_current=True,
        )
    return version, diff
```

In `views/resume.py`, add and wire the real POST branch:

```python
from rsm_thrive.services.resume import generate_version


@api_login_required
def generate_version_view(request):
    version, diff = generate_version(request.user.thrive_profile)
    return json_ok({"version": version_payload(version), "diff": diff}, status=201)
```

(and replace the Task 6 stub in `resume_versions_dispatch` with `return generate_version_view(request)`.)

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): deterministic resume generation with diff"
```

---

### Task 8: Set current version

**Files:**
- Modify: `backend/rsm_thrive/views/resume.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_resume_current_switch.py`

**Interfaces:**
- Produces: `POST /api/thrive/resume/versions/rv-<pk>/current` → 200 `version_payload` of the newly-current version. Unknown/not-owned/malformed id → 404 `unknown_version`, and — critical — the existing current is NOT cleared on a 404. Switch happens inside `transaction.atomic()` (existence check first, then clear+set). Idempotent when already current.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_resume_current_switch.py`:

```python
import pytest

from rsm_thrive.models import ResumeVersion
from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _mk(profile, label, current=False):
    return ResumeVersion.objects.create(user=profile.user, label=label,
                                        summary="s", is_current=current)


def test_switch_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1", current=True)
    v2 = _mk(profile, "v2")
    client.force_login(profile.user)

    body = client.post(f"/api/thrive/resume/versions/rv-{v2.pk}/current").json()
    assert body["id"] == f"rv-{v2.pk}" and body["isCurrent"] is True
    v1.refresh_from_db()
    assert v1.is_current is False

    # idempotent re-set
    again = client.post(f"/api/thrive/resume/versions/rv-{v2.pk}/current").json()
    assert again["isCurrent"] is True


def test_unknown_version_404_preserves_current(client):
    profile = make_student()
    v1 = _mk(profile, "v1", current=True)
    other = make_student(username="other")
    theirs = _mk(other, "theirs")
    client.force_login(profile.user)
    for bad in (f"rv-{theirs.pk}", "rv-99999", "banana", "rv-²"):
        assert client.post(f"/api/thrive/resume/versions/{bad}/current").status_code == 404
    v1.refresh_from_db()
    assert v1.is_current is True   # never cleared by a failed switch
```

- [ ] **Step 2: Run to verify failure** — Expected: 404 (route missing) — the preserve-current assert is the real teeth.

- [ ] **Step 3: Implement**

Append to `views/resume.py`:

```python
from django.db import transaction
from django.views.decorators.http import require_http_methods


def _own_version(user, version_id):
    if not version_id.startswith("rv-"):
        return None
    pk = version_id.removeprefix("rv-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return ResumeVersion.objects.filter(pk=pk, user=user).first()


@api_login_required
@require_http_methods(["POST"])
def set_current_version(request, version_id):
    with transaction.atomic():
        target = _own_version(request.user, version_id)
        if target is None:
            return json_error("unknown_version", f"No version {version_id}.", 404)
        ResumeVersion.objects.filter(user=request.user, is_current=True).update(
            is_current=False)
        target.is_current = True
        target.save(update_fields=["is_current"])
    return json_ok(version_payload(target))
```

Route: `path("resume/versions/<str:version_id>/current", resume.set_current_version, name="resume-set-current")`.

- [ ] **Step 4: Run tests** — all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): switch current resume version atomically"
```

---

### Task 9: Contract schemas + seed_demo additions

**Files:**
- Modify: `backend/rsm_thrive/tests/contract/schemas.py`, `backend/rsm_thrive/tests/contract/test_contract.py`, `backend/rsm_thrive/management/commands/seed_demo.py`

**Interfaces:**
- Produces schemas (all `additionalProperties: false`; transcribe from `types.ts`, verify against it):
  - `COURSE_REQUEST_PREFILL` — all 8 keys required (`studentName, program, track, term, currentCourses` (array of string), `currentUnits, unitsCompleted, unitsRequired` (numbers)); `track` reuses `TRACK`.
  - `COURSE_REQUEST` — all 7 keys required; `type` enum `["enroll", "drop", "reduced load", "out of major"]`; `status` enum `["draft", "submitted", "approved", "denied"]`; `submittedAt` = `{"anyOf": [ISO_INSTANT, {"type": "null"}]}`; `prefill` = `COURSE_REQUEST_PREFILL`.
  - `TSS` — `{"connected": boolean}` required, closed (our own aggregate; not in types.ts).
  - `SKILL` — required `[id, name, source]`, `source` enum `["course", "manual"]`, optional `courseId`.
  - `RESUME_COURSE` (`[code, title, highlight]` all required), `RESUME_EXPERIENCE` (`[id, title, organization, period, bullets]` all required, bullets array of string), `RESUME_VERSION` (all 8 required; `createdAt` ISO_INSTANT; skills/courses/experience arrays of the nested schemas; `isCurrent` boolean), `RESUME_DIFF` (`[addedSkills, addedCourses, summaryChanged]` all required).
- Contract CASES gain: `("/api/thrive/requests/prefill", COURSE_REQUEST_PREFILL, False)`, `("/api/thrive/requests", COURSE_REQUEST, True)`, `("/api/thrive/tss", TSS, False)`, `("/api/thrive/resume/skills", SKILL, True)`, `("/api/thrive/resume/versions", RESUME_VERSION, True)`, `("/api/thrive/resume/current", RESUME_VERSION, False)`.
- World fixture additions (before `force_login`... note: the version generation + request creation need the logged-in client OR direct ORM/service calls — use the service/ORM): two skills (`make_skill(profile, name="SQL", source="course", course=course)` + one manual), `make_highlight("MGTA 453", ...)` matching the fixture's course code — check the existing fixture's `make_course(id="c1")` default code and pass the highlight code to match (the factory default is `MGTA <450+n>` which varies; give the fixture course an explicit `code="MGTA 453"`), one draft + one submitted request via `make_course_request` (submitted one with `status="submitted", submitted_at=timezone.now()`), and one generated version via `services.resume.generate_version(profile)`.
- `seed_demo`: inside the atomic block — 3 skills for the demo student, highlights for the two demo courses (`t.make_highlight(...)` with the demo courses' actual codes — capture the codes from the created course objects), and one generated version via `generate_version` (import from `rsm_thrive.services.resume`).

- [ ] **Step 1: Extend fixture + CASES; run to confirm AttributeError.**
- [ ] **Step 2: Write all eight schemas (complete, no placeholders); iterate until the contract suite passes — never loosen a schema to pass; a genuine mismatch with types.ts is a DONE_WITH_CONCERNS report.**
- [ ] **Step 3: Extend seed_demo; verify `manage.py migrate && manage.py seed_demo` on a scratch DB (delete backend/db.sqlite3 first), run twice, second run no-ops.**
- [ ] **Step 4: Full suite** — `uv run pytest -v`, all PASS.
- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "test(backend): request and resume contract schemas, richer demo seed"
```

---

## Plan Self-Review (completed at authoring)

- **Spec coverage:** all 11 remaining providers have endpoints (prefill T2, create/list T3, submit + tss ×2 T4, skills T5, versions/current T6, generate T7, setCurrent T8) + contract layer T9. Provider semantics ported from providers.ts with line references in the Global Constraints.
- **Placeholder scan:** Task 9 keeps the F1/F2a convention (two-of-N schemas fully specified in constraints prose with transcription rules + source file named); all other tasks carry complete code.
- **Type consistency:** `request_payload`/`build_prefill`/`skill_payload`/`version_payload`/`compose_summary`/`generate_version` signatures and the id namespaces (`req-`, `skill-`, `rv-`) used identically across tasks; the T6 stub→T7 replacement of the dispatch POST branch is called out in both tasks.
