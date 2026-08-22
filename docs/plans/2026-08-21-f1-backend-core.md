# F1 — Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `rsm-django-thrive` Django backend with session-authenticated JSON endpoints for the student identity, academic reads (courses, syllabi, assignments, events, resources), the task list with per-student sparse overrides, the overlay stores (ignores, joins, prefs, notes), and degree progress/timeline — everything the finished dashboard + calendar surfaces need, validated by contract tests.

**Architecture:** Plain Django (no DRF) app `rsm_thrive` inside `backend/`, developed as a standalone project locally (`config/`), later mounted into the `rsm-msba-brain` platform site. Views are thin; JSON shapes match the frontend's `types.ts` byte-for-byte (camelCase, ISO-8601 dates, guaranteed sorts in querysets). Per-student state uses the sparse-override pattern: override rows store only what the student changed; absent = source value.

**Tech Stack:** Python ≥3.12, Django ≥5.2, uv, pytest + pytest-django, jsonschema (dev), SQLite for tests / Postgres for real runs.

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` (this plan implements spec §2–§4 except appointments; appointments = plan F2, Canvas ingestion = F3, frontend integration = F4, deployment = F5. Course-request and resume providers are also deferred to F2.)

## Global Constraints

- JSON keys are camelCase and match `frontend/src/lib/data/types.ts` exactly, including closed-union literals with spaces: `"11 month"`, `"17 month"`, `"in person"`.
- Every instant is ISO-8601 with offset (e.g. `"2026-08-11T09:00:00-07:00"`); every calendar date is `"YYYY-MM-DD"`. The backend never formats a date for humans. `CourseMeeting.startTime`/`endTime` stay wall-clock `"HH:mm"` strings.
- Guaranteed sorts live server-side: tasks done-last-then-due-asc, assignments due-asc, events future-only-by-start-asc.
- `[]` for empty collections; `null` body fields for unknown-id lookups are not used in F1 (F1 GET endpoints return collections); unknown resources → 404 JSON error.
- Three ID key spaces only (task id, calendar item id, raw event id). Task ids are namespaced strings: `asg:<assignmentId>`, `shared:<pk>`, `stu:<pk>`.
- Unauthenticated API access → `401` with body `{"error": {"code": "unauthenticated", "message": ...}}`. Every endpoint requires login except `/health`.
- `TIME_ZONE = "America/Los_Angeles"`, `USE_TZ = True`. Serializers reject naive datetimes.
- All commands run from `backend/` using `uv run`. Commit after every task (work in the `thrive-production` repo, branch `main`).

---

### Task 1: Project scaffold + health endpoint

**Files:**
- Create: `backend/pyproject.toml`, `backend/manage.py`, `backend/config/__init__.py`, `backend/config/settings.py`, `backend/config/urls.py`, `backend/rsm_thrive/__init__.py`, `backend/rsm_thrive/apps.py`, `backend/rsm_thrive/urls.py`, `backend/rsm_thrive/views/__init__.py`, `backend/rsm_thrive/views/health.py`, `backend/conftest.py`
- Test: `backend/rsm_thrive/tests/__init__.py`, `backend/rsm_thrive/tests/test_health.py`

**Interfaces:**
- Produces: Django project importable as `config`, app `rsm_thrive`, URL mount `api/thrive/` (all later routes register in `rsm_thrive/urls.py`), pytest wired via `pytest-django`.

- [ ] **Step 1: Write project files**

`backend/pyproject.toml`:

```toml
[project]
name = "rsm-django-thrive"
version = "0.1.0"
description = "THRIVE backend component (Rady MSBA)"
requires-python = ">=3.12"
dependencies = [
    "django>=5.2",
    "psycopg[binary]>=3.2",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-django>=4.9",
    "jsonschema>=4.22",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["test_*.py"]
```

`backend/manage.py` (standard):

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

`backend/config/settings.py`:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("THRIVE_SECRET_KEY", "dev-only-insecure")
DEBUG = os.environ.get("THRIVE_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rsm_thrive",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# SQLite by default (tests, quick local). THRIVE_PG=1 switches to Postgres —
# the shape production uses (spec §7: nothing debugged first on the server).
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if os.environ.get("THRIVE_PG") == "1":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "thrive_dev"),
        "USER": os.environ.get("PGUSER", "thrive"),
        "PASSWORD": os.environ.get("PGPASSWORD", "thrive"),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Los_Angeles"
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

`backend/config/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/thrive/", include("rsm_thrive.urls")),
]
```

`backend/rsm_thrive/apps.py`:

```python
from django.apps import AppConfig


class RsmThriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rsm_thrive"
```

`backend/rsm_thrive/urls.py`:

```python
from django.urls import path

from .views import health

app_name = "rsm_thrive"

urlpatterns = [
    path("health", health.health, name="health"),
]
```

`backend/rsm_thrive/views/health.py`:

```python
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})
```

`backend/conftest.py`:

```python
# pytest-django picks up DJANGO_SETTINGS_MODULE from pyproject.toml.
```

Empty `__init__.py` for `config/`, `rsm_thrive/`, `rsm_thrive/views/`, `rsm_thrive/tests/`.

- [ ] **Step 2: Write the failing test**

`backend/rsm_thrive/tests/test_health.py`:

```python
def test_health(client):
    resp = client.get("/api/thrive/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Install and run**

Run: `cd backend && uv sync && uv run pytest -v`
Expected: `test_health` PASSES (scaffold task: files first, test proves the wiring).

- [ ] **Step 4: Commit**

```bash
git add backend
git commit -m "feat(backend): scaffold rsm_thrive Django app with health endpoint"
```

---

### Task 2: Serialization + auth helpers

**Files:**
- Create: `backend/rsm_thrive/serialize.py`, `backend/rsm_thrive/http.py`
- Test: `backend/rsm_thrive/tests/test_helpers.py`

**Interfaces:**
- Produces:
  - `serialize.iso_instant(dt: datetime) -> str` — localtime ISO-8601 with offset; raises `ValueError` on naive input.
  - `serialize.iso_date(d: date) -> str` — `"YYYY-MM-DD"`.
  - `http.json_ok(payload, status=200) -> JsonResponse` (`safe=False`, so lists are allowed).
  - `http.json_error(code: str, message: str, status: int) -> JsonResponse` with body `{"error": {"code", "message"}}`.
  - `http.api_login_required(view)` — decorator returning 401 `json_error("unauthenticated", ...)` for anonymous users.
  - `http.parse_body(request) -> dict` — JSON body parse; raises `http.BadRequest` (an Exception carrying a message) on invalid JSON or non-object.

- [ ] **Step 1: Write the failing tests**

`backend/rsm_thrive/tests/test_helpers.py`:

```python
import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.serialize import iso_date, iso_instant


def test_iso_instant_localizes_with_offset():
    aware = dt.datetime(2026, 8, 11, 16, 0, tzinfo=dt.timezone.utc)
    out = iso_instant(aware)
    assert out == "2026-08-11T09:00:00-07:00"  # PDT


def test_iso_instant_rejects_naive():
    with pytest.raises(ValueError):
        iso_instant(dt.datetime(2026, 8, 11, 9, 0))


def test_iso_date():
    assert iso_date(dt.date(2026, 8, 11)) == "2026-08-11"


def test_api_login_required_returns_401_json(client):
    # /api/thrive/me does not exist yet; use a tiny throwaway view via RequestFactory.
    from django.test import RequestFactory
    from django.contrib.auth.models import AnonymousUser
    from rsm_thrive.http import api_login_required, json_ok

    @api_login_required
    def view(request):
        return json_ok({"fine": True})

    req = RequestFactory().get("/x")
    req.user = AnonymousUser()
    resp = view(req)
    assert resp.status_code == 401
    import json
    assert json.loads(resp.content)["error"]["code"] == "unauthenticated"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest rsm_thrive/tests/test_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: rsm_thrive.serialize`

- [ ] **Step 3: Implement**

`backend/rsm_thrive/serialize.py`:

```python
import datetime as dt

from django.utils import timezone


def iso_instant(value: dt.datetime) -> str:
    """ISO-8601 with offset, in the site timezone. The contract's ISODateTime."""
    if timezone.is_naive(value):
        raise ValueError("naive datetime crossed the serializer")
    return timezone.localtime(value).isoformat()


def iso_date(value: dt.date) -> str:
    """The contract's ISODate."""
    return value.isoformat()
```

`backend/rsm_thrive/http.py`:

```python
import functools
import json

from django.http import JsonResponse


class BadRequest(Exception):
    pass


def json_ok(payload, status=200):
    return JsonResponse(payload, status=status, safe=False)


def json_error(code: str, message: str, status: int):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def api_login_required(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return json_error("unauthenticated", "Log in to use THRIVE.", 401)
        return view(request, *args, **kwargs)
    return wrapper


def parse_body(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise BadRequest("Body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise BadRequest("Body must be a JSON object.")
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest rsm_thrive/tests/test_helpers.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): serialization and JSON auth helpers"
```

---

### Task 3: StudentProfile model + GET /me

**Files:**
- Create: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/models/students.py`, `backend/rsm_thrive/serializers/__init__.py`, `backend/rsm_thrive/serializers/students.py`, `backend/rsm_thrive/views/students.py`, `backend/rsm_thrive/testing.py`
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_me.py`

**Interfaces:**
- Consumes: `iso_date`, `json_ok`, `api_login_required` (Task 2).
- Produces:
  - Model `StudentProfile` — `user` OneToOne (related_name `thrive_profile`), fields `display_name`, `goal`, `track` (choices `"11 month"|"17 month"`), `program`, `standing` (`onTrack|watch|needsHelp`), `standing_summary`, `avatar_url`, `current_term`, `program_start` (DateField), four consent booleans (`consent_calendar_read`, `consent_lms_read`, `consent_career_recommendations`, `consent_advisor_sharing`).
  - `serializers.students.student_payload(profile) -> dict` matching the `Student` type.
  - `testing.make_student(username="ada", **overrides) -> StudentProfile` (creates User + profile; `overrides` set profile fields).
  - Route: `GET /api/thrive/me`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_me.py`:

```python
import pytest

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def test_me_requires_login(client):
    assert client.get("/api/thrive/me").status_code == 401


def test_me_returns_student_shape(client):
    profile = make_student(
        username="ada",
        display_name="Ada Lovelace",
        goal="Data Scientist",
        track="11 month",
        consent_lms_read=True,
    )
    client.force_login(profile.user)
    body = client.get("/api/thrive/me").json()
    assert body == {
        "id": "ada",
        "name": "Ada Lovelace",
        "goal": "Data Scientist",
        "track": "11 month",
        "program": "MSBA",
        "standingSummary": "You're on track.",
        "standing": "onTrack",
        "consent": {
            "calendarRead": False,
            "lmsRead": True,
            "careerRecommendations": False,
            "advisorSharing": False,
        },
        "currentTerm": "Fall 2026",
        "programStart": "2026-08-01",
    }
    # avatarUrl is optional in the contract: omitted when blank.
    assert "avatarUrl" not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest rsm_thrive/tests/test_me.py -v`
Expected: FAIL (`ImportError: rsm_thrive.testing`)

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/students.py`:

```python
from django.conf import settings
from django.db import models

TRACK_CHOICES = [("11 month", "11 month"), ("17 month", "17 month")]
STANDING_CHOICES = [("onTrack", "onTrack"), ("watch", "watch"), ("needsHelp", "needsHelp")]


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thrive_profile"
    )
    display_name = models.CharField(max_length=120)
    goal = models.CharField(max_length=120, blank=True, default="")
    track = models.CharField(max_length=16, choices=TRACK_CHOICES, default="11 month")
    program = models.CharField(max_length=120, default="MSBA")
    standing = models.CharField(max_length=16, choices=STANDING_CHOICES, default="onTrack")
    standing_summary = models.CharField(max_length=240, default="You're on track.")
    avatar_url = models.URLField(blank=True, default="")
    current_term = models.CharField(max_length=40, default="Fall 2026")
    program_start = models.DateField()
    consent_calendar_read = models.BooleanField(default=False)
    consent_lms_read = models.BooleanField(default=False)
    consent_career_recommendations = models.BooleanField(default=False)
    consent_advisor_sharing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
```

`backend/rsm_thrive/models/__init__.py`:

```python
from .students import StudentProfile  # noqa: F401
```

`backend/rsm_thrive/serializers/students.py`:

```python
from rsm_thrive.serialize import iso_date


def student_payload(profile) -> dict:
    payload = {
        "id": profile.user.username,
        "name": profile.display_name,
        "goal": profile.goal,
        "track": profile.track,
        "program": profile.program,
        "standingSummary": profile.standing_summary,
        "standing": profile.standing,
        "consent": {
            "calendarRead": profile.consent_calendar_read,
            "lmsRead": profile.consent_lms_read,
            "careerRecommendations": profile.consent_career_recommendations,
            "advisorSharing": profile.consent_advisor_sharing,
        },
        "currentTerm": profile.current_term,
        "programStart": iso_date(profile.program_start),
    }
    if profile.avatar_url:
        payload["avatarUrl"] = profile.avatar_url
    return payload
```

`backend/rsm_thrive/views/students.py`:

```python
from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.serializers.students import student_payload


@api_login_required
def me(request):
    return json_ok(student_payload(request.user.thrive_profile))
```

`backend/rsm_thrive/testing.py`:

```python
"""Factories shared by tests and the seed_demo command."""
import datetime as dt

from django.contrib.auth import get_user_model

from rsm_thrive.models import StudentProfile


def make_student(username="ada", **overrides) -> StudentProfile:
    user = get_user_model().objects.create_user(username=username)
    fields = {
        "display_name": "Ada Lovelace",
        "program_start": dt.date(2026, 8, 1),
    }
    fields.update(overrides)
    return StudentProfile.objects.create(user=user, **fields)
```

Add to `backend/rsm_thrive/urls.py` urlpatterns:

```python
path("me", students.me, name="me"),
```

(and `from .views import health, students`.)

- [ ] **Step 4: Make the migration, run tests**

Run: `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`
Expected: migration `0001_initial` created; all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): StudentProfile model and GET /me"
```

---

### Task 4: Academic models + factories

**Files:**
- Create: `backend/rsm_thrive/models/academic.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`
- Test: `backend/rsm_thrive/tests/test_academic_models.py`

**Interfaces:**
- Produces models (all catalog ids are `CharField(primary_key=True, max_length=64)` so Canvas external ids slot in later):
  - `Course(id, code, title, instructor, term, units)`
  - `CourseMeeting(course FK related_name="meetings", day_of_week: int, start_time: str "HH:mm", end_time: str, location)` with `Meta.ordering = ["day_of_week", "start_time"]`
  - `Syllabus(id, course OneToOne related_name="syllabus", description, grade_breakdown: JSON list of {"label","weight"}, policies: JSON list of str, office_hours, source_url blank, last_updated: Date)`
  - `Assignment(id, course FK related_name="assignments", title, due_date: DateTime, weight: int, description blank)`
  - `Enrollment(user FK, course FK, progress: int, standing, current_grade blank, nudge blank, bucket: "core"|"elective", completed: bool)` with unique `(user, course)`
  - `StudentAssignment(user FK, assignment FK, status: AssignmentStatus choices, grade blank)` with unique `(user, assignment)`; status literals: `not-started`, `in-progress`, `submitted`, `graded`, `late`
  - Factories: `make_course(id="mgta-453", **kw)`, `make_meeting(course, **kw)`, `make_syllabus(course, **kw)`, `make_assignment(course, id=None, due=None, **kw)`, `enroll(profile, course, **kw)`, `set_assignment_status(profile, assignment, status, grade="")`

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_academic_models.py`:

```python
import pytest
from django.db import IntegrityError

from rsm_thrive.testing import enroll, make_course, make_student

pytestmark = pytest.mark.django_db


def test_enrollment_unique_per_student_and_course():
    profile = make_student()
    course = make_course()
    enroll(profile, course)
    with pytest.raises(IntegrityError):
        enroll(profile, course)


def test_meetings_ordered_by_day_then_time():
    from rsm_thrive.testing import make_meeting
    course = make_course()
    make_meeting(course, day_of_week=3, start_time="09:00")
    make_meeting(course, day_of_week=1, start_time="14:00")
    make_meeting(course, day_of_week=1, start_time="09:00")
    got = [(m.day_of_week, m.start_time) for m in course.meetings.all()]
    assert got == [(1, "09:00"), (1, "14:00"), (3, "09:00")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest rsm_thrive/tests/test_academic_models.py -v`
Expected: FAIL (`ImportError: cannot import name 'enroll'`)

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/academic.py`:

```python
from django.conf import settings
from django.db import models

from .students import STANDING_CHOICES

ASSIGNMENT_STATUS_CHOICES = [
    ("not-started", "not-started"),
    ("in-progress", "in-progress"),
    ("submitted", "submitted"),
    ("graded", "graded"),
    ("late", "late"),
]
BUCKET_CHOICES = [("core", "core"), ("elective", "elective")]


class Course(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    instructor = models.CharField(max_length=120)
    term = models.CharField(max_length=40)
    units = models.PositiveSmallIntegerField(default=4)


class CourseMeeting(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="meetings")
    day_of_week = models.PositiveSmallIntegerField()  # 0=Sunday..6, matches JS getDay()
    start_time = models.CharField(max_length=5)  # wall-clock "HH:mm", per contract
    end_time = models.CharField(max_length=5)
    location = models.CharField(max_length=120)

    class Meta:
        ordering = ["day_of_week", "start_time"]


class Syllabus(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="syllabus")
    description = models.TextField()
    grade_breakdown = models.JSONField(default=list)  # [{"label": str, "weight": int}]
    policies = models.JSONField(default=list)  # [str]
    office_hours = models.CharField(max_length=200, default="")
    source_url = models.URLField(blank=True, default="")
    last_updated = models.DateField()


class Assignment(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    weight = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True, default="")


class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.PositiveSmallIntegerField(default=0)  # 0-100
    standing = models.CharField(max_length=16, choices=STANDING_CHOICES, default="onTrack")
    current_grade = models.CharField(max_length=16, blank=True, default="")
    nudge = models.CharField(max_length=240, blank=True, default="")
    bucket = models.CharField(max_length=16, choices=BUCKET_CHOICES, default="core")
    completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment"),
        ]


class StudentAssignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=ASSIGNMENT_STATUS_CHOICES, default="not-started")
    grade = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "assignment"], name="uniq_student_assignment"),
        ]
```

Re-export everything in `models/__init__.py`:

```python
from .academic import (  # noqa: F401
    Assignment, Course, CourseMeeting, Enrollment, StudentAssignment, Syllabus,
)
from .students import StudentProfile  # noqa: F401
```

Append to `backend/rsm_thrive/testing.py`:

```python
import itertools

from django.utils import timezone

from rsm_thrive.models import (
    Assignment, Course, CourseMeeting, Enrollment, StudentAssignment, Syllabus,
)

_counter = itertools.count(1)


def make_course(id=None, **overrides) -> Course:
    n = next(_counter)
    fields = {
        "id": id or f"course-{n}",
        "code": f"MGTA {450 + n}",
        "title": "Business Analytics",
        "instructor": "V. Nijs",
        "term": "Fall 2026",
        "units": 4,
    }
    fields.update(overrides)
    return Course.objects.create(**fields)


def make_meeting(course, **overrides) -> CourseMeeting:
    fields = {"day_of_week": 1, "start_time": "09:00", "end_time": "10:20",
              "location": "Rady 2S111"}
    fields.update(overrides)
    return CourseMeeting.objects.create(course=course, **fields)


def make_syllabus(course, **overrides) -> Syllabus:
    fields = {
        "id": f"syl-{course.id}",
        "description": "What the course covers.",
        "grade_breakdown": [{"label": "Final project", "weight": 40}],
        "policies": ["No late work"],
        "office_hours": "Tue 2-4pm",
        "last_updated": timezone.localdate(),
    }
    fields.update(overrides)
    return Syllabus.objects.create(course=course, **fields)


def make_assignment(course, id=None, due=None, **overrides) -> Assignment:
    n = next(_counter)
    fields = {
        "id": id or f"asg-{n}",
        "title": f"Homework {n}",
        "due_date": due or (timezone.now() + timezone.timedelta(days=7)),
        "weight": 10,
    }
    fields.update(overrides)
    return Assignment.objects.create(course=course, **fields)


def enroll(profile, course, **overrides) -> Enrollment:
    return Enrollment.objects.create(user=profile.user, course=course, **overrides)


def set_assignment_status(profile, assignment, status, grade="") -> StudentAssignment:
    return StudentAssignment.objects.create(
        user=profile.user, assignment=assignment, status=status, grade=grade
    )
```

- [ ] **Step 4: Make migration, run tests**

Run: `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): academic models and test factories"
```

---

### Task 5: GET /assignments

**Files:**
- Create: `backend/rsm_thrive/serializers/academic.py`, `backend/rsm_thrive/views/assignments.py`
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_assignments.py`

**Interfaces:**
- Consumes: Task 4 models/factories.
- Produces:
  - `serializers.academic.assignment_payload(assignment, student_assignment | None) -> dict` matching `Assignment` type (`grade`/`description` keys omitted when empty).
  - Route `GET /api/thrive/assignments` — assignments of the student's enrolled courses only, sorted `due_date` asc (contract guarantee).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_assignments.py`:

```python
import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_student, set_assignment_status,
)

pytestmark = pytest.mark.django_db


def test_assignments_scoped_sorted_and_shaped(client):
    profile = make_student()
    mine = make_course(id="c1")
    other = make_course(id="c2")
    enroll(profile, mine)
    late = make_assignment(mine, id="a-late", due=timezone.now() + timezone.timedelta(days=9))
    soon = make_assignment(mine, id="a-soon", due=timezone.now() + timezone.timedelta(days=1))
    make_assignment(other, id="a-other")  # not enrolled: must not appear
    set_assignment_status(profile, soon, "graded", grade="A-")

    client.force_login(profile.user)
    body = client.get("/api/thrive/assignments").json()

    assert [a["id"] for a in body] == ["a-soon", "a-late"]  # due asc
    graded = body[0]
    assert graded["courseId"] == "c1"
    assert graded["status"] == "graded"
    assert graded["grade"] == "A-"
    assert graded["weight"] == 10
    assert graded["dueDate"].endswith("-07:00") or graded["dueDate"].endswith("-08:00")
    unstarted = body[1]
    assert unstarted["status"] == "not-started"  # no StudentAssignment row yet
    assert "grade" not in unstarted


def test_assignments_requires_login(client):
    assert client.get("/api/thrive/assignments").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest rsm_thrive/tests/test_assignments.py -v`
Expected: FAIL with 404 (route not registered).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/serializers/academic.py`:

```python
from rsm_thrive.serialize import iso_instant


def assignment_payload(assignment, student_assignment=None) -> dict:
    payload = {
        "id": assignment.id,
        "courseId": assignment.course_id,
        "title": assignment.title,
        "dueDate": iso_instant(assignment.due_date),
        "weight": assignment.weight,
        "status": student_assignment.status if student_assignment else "not-started",
    }
    if student_assignment and student_assignment.grade:
        payload["grade"] = student_assignment.grade
    if assignment.description:
        payload["description"] = assignment.description
    return payload
```

`backend/rsm_thrive/views/assignments.py`:

```python
from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Assignment, Enrollment, StudentAssignment
from rsm_thrive.serializers.academic import assignment_payload


def _my_assignments(user):
    """Assignments of enrolled courses, due asc — the contract's guaranteed sort."""
    course_ids = Enrollment.objects.filter(user=user).values_list("course_id", flat=True)
    return Assignment.objects.filter(course_id__in=course_ids).order_by("due_date", "id")


@api_login_required
def assignments(request):
    rows = _my_assignments(request.user)
    statuses = {
        sa.assignment_id: sa
        for sa in StudentAssignment.objects.filter(user=request.user, assignment__in=rows)
    }
    return json_ok([assignment_payload(a, statuses.get(a.id)) for a in rows])
```

Register in `urls.py`: `path("assignments", assignments.assignments, name="assignments")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest rsm_thrive/tests/test_assignments.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): GET /assignments with per-student status"
```

---

### Task 6: GET /courses and GET /syllabi

**Files:**
- Modify: `backend/rsm_thrive/serializers/academic.py`, `backend/rsm_thrive/urls.py`
- Create: `backend/rsm_thrive/views/courses.py`
- Test: `backend/rsm_thrive/tests/test_courses.py`

**Interfaces:**
- Consumes: Task 4 models; `_my_assignments` pattern from Task 5.
- Produces:
  - `course_payload(course, enrollment, next_assignment | None) -> dict` matching `Course` (`nudge`/`currentGrade` omitted when blank; `schedule` from meetings; `syllabusId` from the OneToOne; `progress`/`standing` from the enrollment).
  - `syllabus_payload(syllabus) -> dict` matching `Syllabus` (`sourceUrl` omitted when blank).
  - `next_assignment_for(course, now) -> dict` — earliest assignment with `due_date >= now`, else the latest past one, else `{"title": "Nothing scheduled yet", "due": iso_instant(now)}` (neutral fallback; Canvas sync keeps this rare).
  - Routes: `GET /api/thrive/courses`, `GET /api/thrive/syllabi` (both scoped to enrollments; courses ordered by `code`, syllabi by `course__code`).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_courses.py`:

```python
import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_meeting, make_student, make_syllabus,
)

pytestmark = pytest.mark.django_db


def test_courses_shape_and_next_assignment(client):
    profile = make_student()
    course = make_course(id="c1", code="MGTA 453")
    make_meeting(course, day_of_week=2, start_time="09:00", end_time="10:20",
                 location="Rady 2S111")
    make_syllabus(course, id="syl-c1")
    make_assignment(course, id="past", due=timezone.now() - timezone.timedelta(days=3))
    make_assignment(course, id="next", title="Case write-up",
                    due=timezone.now() + timezone.timedelta(days=2))
    make_assignment(course, id="later", due=timezone.now() + timezone.timedelta(days=20))
    enroll(profile, course, progress=40, standing="watch", nudge="Submit the case",
           current_grade="B+")

    client.force_login(profile.user)
    [row] = client.get("/api/thrive/courses").json()

    assert row["id"] == "c1"
    assert row["code"] == "MGTA 453"
    assert row["schedule"] == [{"dayOfWeek": 2, "startTime": "09:00",
                                "endTime": "10:20", "location": "Rady 2S111"}]
    assert row["progress"] == 40
    assert row["standing"] == "watch"
    assert row["nextAssignment"]["title"] == "Case write-up"
    assert row["nudge"] == "Submit the case"
    assert row["currentGrade"] == "B+"
    assert row["syllabusId"] == "syl-c1"
    assert row["units"] == 4


def test_syllabi_scoped_to_enrollments(client):
    profile = make_student()
    mine = make_course(id="c1")
    other = make_course(id="c2")
    make_syllabus(mine, id="syl-1")
    make_syllabus(other, id="syl-2")
    enroll(profile, mine)

    client.force_login(profile.user)
    body = client.get("/api/thrive/syllabi").json()
    assert [s["id"] for s in body] == ["syl-1"]
    assert body[0]["courseId"] == "c1"
    assert body[0]["gradeBreakdown"] == [{"label": "Final project", "weight": 40}]
    assert "sourceUrl" not in body[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest rsm_thrive/tests/test_courses.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement**

Append to `backend/rsm_thrive/serializers/academic.py`:

```python
from rsm_thrive.serialize import iso_date  # add to imports at top


def next_assignment_for(course, now) -> dict:
    upcoming = course.assignments.filter(due_date__gte=now).order_by("due_date").first()
    chosen = upcoming or course.assignments.order_by("-due_date").first()
    if chosen is None:
        return {"title": "Nothing scheduled yet", "due": iso_instant(now)}
    return {"title": chosen.title, "due": iso_instant(chosen.due_date)}


def course_payload(course, enrollment, now) -> dict:
    payload = {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "instructor": course.instructor,
        "schedule": [
            {"dayOfWeek": m.day_of_week, "startTime": m.start_time,
             "endTime": m.end_time, "location": m.location}
            for m in course.meetings.all()
        ],
        "term": course.term,
        "progress": enrollment.progress,
        "standing": enrollment.standing,
        "nextAssignment": next_assignment_for(course, now),
        "syllabusId": course.syllabus.id,
        "units": course.units,
    }
    if enrollment.nudge:
        payload["nudge"] = enrollment.nudge
    if enrollment.current_grade:
        payload["currentGrade"] = enrollment.current_grade
    return payload


def syllabus_payload(syllabus) -> dict:
    payload = {
        "id": syllabus.id,
        "courseId": syllabus.course_id,
        "description": syllabus.description,
        "gradeBreakdown": syllabus.grade_breakdown,
        "policies": syllabus.policies,
        "officeHours": syllabus.office_hours,
        "lastUpdated": iso_date(syllabus.last_updated),
    }
    if syllabus.source_url:
        payload["sourceUrl"] = syllabus.source_url
    return payload
```

`backend/rsm_thrive/views/courses.py`:

```python
from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Enrollment, Syllabus
from rsm_thrive.serializers.academic import course_payload, syllabus_payload


@api_login_required
def courses(request):
    now = timezone.now()
    enrollments = (
        Enrollment.objects.filter(user=request.user)
        .select_related("course", "course__syllabus")
        .prefetch_related("course__meetings", "course__assignments")
        .order_by("course__code")
    )
    return json_ok([course_payload(e.course, e, now) for e in enrollments])


@api_login_required
def syllabi(request):
    course_ids = Enrollment.objects.filter(user=request.user).values_list("course_id", flat=True)
    rows = Syllabus.objects.filter(course_id__in=course_ids).order_by("course__code")
    return json_ok([syllabus_payload(s) for s in rows])
```

Register: `path("courses", courses.courses)`, `path("syllabi", courses.syllabi)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest rsm_thrive/tests/test_courses.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): GET /courses and GET /syllabi"
```

---

### Task 7: Event model + GET /events

**Files:**
- Create: `backend/rsm_thrive/models/events.py`, `backend/rsm_thrive/views/events.py`, `backend/rsm_thrive/serializers/events.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_events.py`

**Interfaces:**
- Produces:
  - Model `Event(id: Char pk, title, type: rady|ucsd|sandiego|club|career, start: DateTime, end: DateTime null, location, description blank, register_url blank, goal_tags: JSON list of str)`
  - `event_payload(event, goal: str) -> dict` matching `Event`; `relevantToGoal` = case-insensitive membership of the student's goal in `goal_tags` (deterministic v1 rule; upgraded in Phase C).
  - Factory `make_event(id=None, start=None, **kw)`.
  - Route `GET /api/thrive/events` — the contract's filter and sort: keep events where `(end or start) >= now`, ordered by `start` asc.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_events.py`:

```python
import pytest
from django.utils import timezone

from rsm_thrive.testing import make_event, make_student

pytestmark = pytest.mark.django_db


def test_events_future_filter_sort_and_relevance(client):
    profile = make_student(goal="Data Scientist")
    now = timezone.now()
    day = timezone.timedelta(days=1)
    make_event(id="past", start=now - 3 * day)                      # gone
    make_event(id="running", start=now - 2 * day, end=now + day)    # kept: end >= now
    make_event(id="soon", start=now + day,
               goal_tags=["data scientist", "ml engineer"])          # relevant
    make_event(id="later", start=now + 5 * day)

    client.force_login(profile.user)
    body = client.get("/api/thrive/events").json()

    assert [e["id"] for e in body] == ["running", "soon", "later"]  # start asc
    by_id = {e["id"]: e for e in body}
    assert by_id["soon"]["relevantToGoal"] is True
    assert by_id["later"]["relevantToGoal"] is False
    assert "end" in by_id["running"] and "end" not in by_id["soon"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest rsm_thrive/tests/test_events.py -v`
Expected: FAIL (`ImportError: make_event`).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/events.py`:

```python
from django.db import models

EVENT_TYPE_CHOICES = [
    ("rady", "rady"), ("ucsd", "ucsd"), ("sandiego", "sandiego"),
    ("club", "club"), ("career", "career"),
]


class Event(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=16, choices=EVENT_TYPE_CHOICES, default="rady")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, default="")
    description = models.TextField(blank=True, default="")
    register_url = models.URLField(blank=True, default="")
    goal_tags = models.JSONField(default=list)  # lowercase role names this event serves
```

Re-export in `models/__init__.py` (`from .events import Event`).

`backend/rsm_thrive/serializers/events.py`:

```python
from rsm_thrive.serialize import iso_instant


def event_payload(event, goal: str) -> dict:
    payload = {
        "id": event.id,
        "title": event.title,
        "type": event.type,
        "start": iso_instant(event.start),
        "location": event.location,
        "relevantToGoal": bool(goal) and goal.lower() in
                          [t.lower() for t in event.goal_tags],
    }
    if event.end:
        payload["end"] = iso_instant(event.end)
    if event.description:
        payload["description"] = event.description
    if event.register_url:
        payload["registerUrl"] = event.register_url
    return payload
```

`backend/rsm_thrive/views/events.py`:

```python
from django.db.models import F, Q
from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Event
from rsm_thrive.serializers.events import event_payload


@api_login_required
def events(request):
    now = timezone.now()
    rows = (
        Event.objects
        .filter(Q(end__isnull=False, end__gte=now) | Q(end__isnull=True, start__gte=now))
        .order_by("start", "id")
    )
    goal = request.user.thrive_profile.goal
    return json_ok([event_payload(e, goal) for e in rows])
```

Factory in `testing.py`:

```python
from rsm_thrive.models import Event


def make_event(id=None, start=None, **overrides) -> Event:
    n = next(_counter)
    fields = {
        "id": id or f"evt-{n}",
        "title": f"Event {n}",
        "start": start or (timezone.now() + timezone.timedelta(days=2)),
        "location": "Rady Courtyard",
    }
    fields.update(overrides)
    return Event.objects.create(**fields)
```

Register route; run `makemigrations`.

- [ ] **Step 4: Run tests**

Run: `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): Event model and GET /events"
```

---

### Task 8: ResourceLink + GET /resources

**Files:**
- Create: `backend/rsm_thrive/models/resources.py`, `backend/rsm_thrive/views/resources.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_resources.py`

**Interfaces:**
- Produces: model `ResourceLink(id: Char pk, title, description, url, category: academic|career|wellness|technical|administrative, owner blank)`; factory `make_resource(id=None, **kw)`; route `GET /api/thrive/resources` ordered `(category, title)`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_resources.py`:

```python
import pytest

from rsm_thrive.testing import make_resource, make_student

pytestmark = pytest.mark.django_db


def test_resources_shape_and_order(client):
    profile = make_student()
    make_resource(id="r2", title="Zoom help", category="technical")
    make_resource(id="r1", title="CMC coaching", category="career",
                  owner="Rady Career Management")

    client.force_login(profile.user)
    body = client.get("/api/thrive/resources").json()
    assert [r["id"] for r in body] == ["r1", "r2"]  # career < technical
    assert body[0] == {
        "id": "r1", "title": "CMC coaching", "description": "What this is for.",
        "url": "https://rady.ucsd.edu/", "category": "career",
        "owner": "Rady Career Management",
    }
    assert "owner" not in body[1]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_resources.py -v` — Expected: FAIL (import error).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/resources.py`:

```python
from django.db import models

RESOURCE_CATEGORY_CHOICES = [
    ("academic", "academic"), ("career", "career"), ("wellness", "wellness"),
    ("technical", "technical"), ("administrative", "administrative"),
]


class ResourceLink(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=400)
    url = models.URLField()
    category = models.CharField(max_length=20, choices=RESOURCE_CATEGORY_CHOICES)
    owner = models.CharField(max_length=120, blank=True, default="")
```

View:

```python
from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import ResourceLink


@api_login_required
def resources(request):
    rows = ResourceLink.objects.order_by("category", "title")
    out = []
    for r in rows:
        item = {"id": r.id, "title": r.title, "description": r.description,
                "url": r.url, "category": r.category}
        if r.owner:
            item["owner"] = r.owner
        out.append(item)
    return json_ok(out)
```

Factory:

```python
from rsm_thrive.models import ResourceLink


def make_resource(id=None, **overrides) -> ResourceLink:
    n = next(_counter)
    fields = {
        "id": id or f"res-{n}",
        "title": f"Resource {n}",
        "description": "What this is for.",
        "url": "https://rady.ucsd.edu/",
        "category": "academic",
    }
    fields.update(overrides)
    return ResourceLink.objects.create(**fields)
```

Register route; `makemigrations`.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): ResourceLink model and GET /resources"
```

---

### Task 9: Task assembly + GET /tasks

**Files:**
- Create: `backend/rsm_thrive/models/overlay.py`, `backend/rsm_thrive/services/__init__.py`, `backend/rsm_thrive/services/tasks.py`, `backend/rsm_thrive/views/tasks.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_tasks.py`

**Interfaces:**
- Produces models:
  - `SharedTask(id: BigAuto, title, due_date: DateTime, source: class|career|admin|event, priority: low|medium|high, subtasks: JSON list of {"id","title","done"}, course FK null, active: bool default True)` — staff/ingestion-authored tasks for everyone.
  - `StudentTask(user FK, title, due_date, source default "admin", priority default "medium", subtasks JSON default list)` — self-added.
  - `TaskOverride(user FK, task_key: Char(80), done: Bool null, title: Char null/blank, priority: Char null, due_date: DateTime null, sort_order: Int null, subtask_done: JSON null)` — sparse; unique `(user, task_key)`. **Nullable columns are the point**: null = "student never touched this facet".
- Produces service `services.tasks.assemble_tasks(user) -> list[dict]`:
  - Task ids: assignment-derived `asg:<assignmentId>` (source `"class"`, done = StudentAssignment status in `{"submitted","graded"}`, priority from weight: ≥25 `"high"`, ≥10 `"medium"`, else `"low"`, carries `courseId`+`courseCode`); shared `shared:<pk>`; self-added `stu:<pk>`.
  - Overlay applied per facet when the override column is non-null (title, priority, dueDate, done, per-subtask done via `subtask_done` map).
  - Sort: done last, then (`sort_order` if set else ∞), then due asc, then id — the contract's guarantee plus stable manual ordering.
- Route `GET /api/thrive/tasks`.
- Factories: `make_shared_task(**kw)`, `make_student_task(profile, **kw)`, `set_override(profile, task_key, **facets)`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_tasks.py`:

```python
import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_shared_task, make_student,
    make_student_task, set_assignment_status, set_override,
)

pytestmark = pytest.mark.django_db
DAY = timezone.timedelta(days=1)


def _setup(client):
    profile = make_student()
    course = make_course(id="c1", code="MGTA 453")
    enroll(profile, course)
    client.force_login(profile.user)
    return profile, course


def test_assignment_derived_task_shape(client):
    profile, course = _setup(client)
    asg = make_assignment(course, id="a1", title="Case study",
                          due=timezone.now() + DAY, weight=30)
    [task] = client.get("/api/thrive/tasks").json()
    assert task["id"] == "asg:a1"
    assert task["title"] == "Case study"
    assert task["source"] == "class"
    assert task["priority"] == "high"        # weight 30 >= 25
    assert task["done"] is False
    assert task["subtasks"] == []
    assert task["courseId"] == "c1"
    assert task["courseCode"] == "MGTA 453"


def test_sort_done_last_then_due(client):
    profile, course = _setup(client)
    a = make_assignment(course, id="a1", due=timezone.now() + 1 * DAY)
    make_assignment(course, id="a2", due=timezone.now() + 2 * DAY)
    make_student_task(profile, title="Print resume", due=timezone.now() + 3 * DAY)
    set_assignment_status(profile, a, "submitted")  # a1 becomes done -> sinks
    ids = [t["id"] for t in client.get("/api/thrive/tasks").json()]
    assert ids[:2] == ["asg:a2", ids[1]] and ids[-1] == "asg:a1"


def test_override_can_untick_a_shipped_done_task(client):
    profile, course = _setup(client)
    a = make_assignment(course, id="a1", due=timezone.now() + DAY)
    set_assignment_status(profile, a, "graded")           # ships done
    set_override(profile, "asg:a1", done=False)           # student unticks
    [task] = client.get("/api/thrive/tasks").json()
    assert task["done"] is False                          # override wins


def test_override_title_and_priority_absent_means_source(client):
    profile, course = _setup(client)
    make_assignment(course, id="a1", title="Original", due=timezone.now() + DAY)
    set_override(profile, "asg:a1", title="Renamed")
    [task] = client.get("/api/thrive/tasks").json()
    assert task["title"] == "Renamed"
    assert task["priority"] == "medium"  # untouched facet: source value (weight 10)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_tasks.py -v` — Expected: FAIL (import errors).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/overlay.py`:

```python
from django.conf import settings
from django.db import models

TASK_SOURCE_CHOICES = [
    ("class", "class"), ("career", "career"), ("admin", "admin"), ("event", "event"),
]
PRIORITY_CHOICES = [("low", "low"), ("medium", "medium"), ("high", "high")]


class SharedTask(models.Model):
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    source = models.CharField(max_length=16, choices=TASK_SOURCE_CHOICES, default="admin")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    subtasks = models.JSONField(default=list)  # [{"id","title","done"}]
    course = models.ForeignKey("rsm_thrive.Course", null=True, blank=True,
                               on_delete=models.SET_NULL)
    active = models.BooleanField(default=True)


class StudentTask(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    source = models.CharField(max_length=16, choices=TASK_SOURCE_CHOICES, default="admin")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    subtasks = models.JSONField(default=list)


class TaskOverride(models.Model):
    """Sparse per-student task edits. A null column = 'use the source value'."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_key = models.CharField(max_length=80)
    done = models.BooleanField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES,
                                null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(null=True, blank=True)
    subtask_done = models.JSONField(null=True, blank=True)  # {"subtaskId": bool}

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "task_key"], name="uniq_task_override"),
        ]
```

`backend/rsm_thrive/services/tasks.py`:

```python
"""Assemble the per-student task list: derive, overlay, sort."""
from rsm_thrive.models import (
    Assignment, Enrollment, SharedTask, StudentAssignment, StudentTask, TaskOverride,
)
from rsm_thrive.serialize import iso_instant

DONE_STATUSES = {"submitted", "graded"}


def _priority_for_weight(weight: int) -> str:
    if weight >= 25:
        return "high"
    if weight >= 10:
        return "medium"
    return "low"


def _base_tasks(user):
    course_ids = dict(
        Enrollment.objects.filter(user=user).values_list("course_id", "course__code")
    )
    done_by_asg = {
        sa.assignment_id: sa.status in DONE_STATUSES
        for sa in StudentAssignment.objects.filter(user=user)
    }
    tasks = []
    for a in Assignment.objects.filter(course_id__in=course_ids).select_related("course"):
        tasks.append({
            "id": f"asg:{a.id}",
            "title": a.title,
            "dueDate": iso_instant(a.due_date),
            "_due": a.due_date,
            "source": "class",
            "priority": _priority_for_weight(a.weight),
            "done": done_by_asg.get(a.id, False),
            "subtasks": [],
            "courseId": a.course_id,
            "courseCode": a.course.code,
        })
    for s in SharedTask.objects.filter(active=True).select_related("course"):
        row = {
            "id": f"shared:{s.pk}",
            "title": s.title,
            "dueDate": iso_instant(s.due_date),
            "_due": s.due_date,
            "source": s.source,
            "priority": s.priority,
            "done": False,
            "subtasks": [dict(st) for st in s.subtasks],
        }
        if s.course_id:
            row["courseId"] = s.course_id
            row["courseCode"] = s.course.code
        tasks.append(row)
    for t in StudentTask.objects.filter(user=user):
        tasks.append({
            "id": f"stu:{t.pk}",
            "title": t.title,
            "dueDate": iso_instant(t.due_date),
            "_due": t.due_date,
            "source": t.source,
            "priority": t.priority,
            "done": False,
            "subtasks": [dict(st) for st in t.subtasks],
        })
    return tasks


def _apply_override(task: dict, ov: TaskOverride) -> None:
    if ov.done is not None:
        task["done"] = ov.done
    if ov.title is not None:
        task["title"] = ov.title
    if ov.priority is not None:
        task["priority"] = ov.priority
    if ov.due_date is not None:
        task["dueDate"] = iso_instant(ov.due_date)
        task["_due"] = ov.due_date
    if ov.sort_order is not None:
        task["_order"] = ov.sort_order
    if ov.subtask_done:
        for st in task["subtasks"]:
            if st["id"] in ov.subtask_done:
                st["done"] = ov.subtask_done[st["id"]]


def assemble_tasks(user) -> list[dict]:
    tasks = _base_tasks(user)
    overrides = {o.task_key: o for o in TaskOverride.objects.filter(user=user)}
    for task in tasks:
        if task["id"] in overrides:
            _apply_override(task, overrides[task["id"]])
    tasks.sort(key=lambda t: (t["done"], t.get("_order", float("inf")), t["_due"], t["id"]))
    for task in tasks:
        task.pop("_due", None)
        task.pop("_order", None)
    return tasks
```

`backend/rsm_thrive/views/tasks.py`:

```python
from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.services.tasks import assemble_tasks


@api_login_required
def tasks(request):
    return json_ok(assemble_tasks(request.user))
```

Factories:

```python
from rsm_thrive.models import SharedTask, StudentTask, TaskOverride


def make_shared_task(**overrides) -> SharedTask:
    n = next(_counter)
    fields = {"title": f"Shared task {n}",
              "due_date": timezone.now() + timezone.timedelta(days=4)}
    fields.update(overrides)
    return SharedTask.objects.create(**fields)


def make_student_task(profile, due=None, **overrides) -> StudentTask:
    n = next(_counter)
    fields = {"title": f"My task {n}",
              "due_date": due or (timezone.now() + timezone.timedelta(days=4))}
    if "due" in overrides:
        fields["due_date"] = overrides.pop("due")
    fields.update(overrides)
    return StudentTask.objects.create(user=profile.user, **fields)


def set_override(profile, task_key, **facets) -> TaskOverride:
    field_map = {"dueDate": "due_date", "order": "sort_order",
                 "subtaskDone": "subtask_done"}
    row, _ = TaskOverride.objects.get_or_create(user=profile.user, task_key=task_key)
    for key, value in facets.items():
        setattr(row, field_map.get(key, key), value)
    row.save()
    return row
```

Register `path("tasks", tasks.tasks)`; re-export models; `makemigrations`.

Note: `make_student_task(profile, title=..., due=...)` — the test calls it with `due=`; keep the signature exactly as above.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): task assembly with sparse overrides and GET /tasks"
```

---

### Task 10: Overlay write endpoints (task override, create/delete student task)

**Files:**
- Modify: `backend/rsm_thrive/views/tasks.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_task_writes.py`

**Interfaces:**
- Consumes: Task 9 models + `assemble_tasks`; `parse_body`/`BadRequest` (Task 2).
- Produces:
  - `PATCH /api/thrive/tasks/<task_id>/override` — body: any subset of `{"done": bool|null, "title": str|null, "priority": str|null, "dueDate": ISO str|null, "order": int|null, "subtaskDone": {id: bool}|null}`. Non-null sets the facet; explicit null clears it (back to source). Row deleted when every facet is null after applying. Returns the merged task dict, or 404 `json_error("unknown_task", ...)` if the id isn't in the student's assembled list.
  - `POST /api/thrive/tasks` — body `{"title": str, "dueDate": ISO str, "priority"?: str, "source"?: str}` → 201 with the new task dict (id `stu:<pk>`).
  - `DELETE /api/thrive/tasks/stu:<pk>` — 204; non-`stu:` ids → 400 `json_error("not_deletable", ...)`.
  - All writes are POST/PATCH/DELETE with CSRF handled by Django's middleware (test client sends the token automatically with `enforce_csrf_checks=False` default).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_task_writes.py`:

```python
import json

import pytest
from django.utils import timezone

from rsm_thrive.models import TaskOverride
from rsm_thrive.testing import enroll, make_assignment, make_course, make_student

pytestmark = pytest.mark.django_db


def _setup(client):
    profile = make_student()
    course = make_course(id="c1")
    enroll(profile, course)
    make_assignment(course, id="a1", due=timezone.now() + timezone.timedelta(days=1))
    client.force_login(profile.user)
    return profile


def _patch(client, task_id, body):
    return client.patch(
        f"/api/thrive/tasks/{task_id}/override",
        data=json.dumps(body), content_type="application/json",
    )


def test_override_set_and_clear(client):
    profile = _setup(client)
    resp = _patch(client, "asg:a1", {"done": True, "title": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["done"] is True and resp.json()["title"] == "Renamed"

    resp = _patch(client, "asg:a1", {"title": None})  # clear one facet
    assert resp.json()["title"] == "Homework 1"        # back to source
    assert resp.json()["done"] is True                 # other facet untouched

    _patch(client, "asg:a1", {"done": None})           # last facet cleared
    assert TaskOverride.objects.count() == 0           # row garbage-collected


def test_override_unknown_task_404(client):
    _setup(client)
    assert _patch(client, "asg:nope", {"done": True}).status_code == 404


def test_create_and_delete_student_task(client):
    _setup(client)
    resp = client.post(
        "/api/thrive/tasks",
        data=json.dumps({"title": "Print resume",
                         "dueDate": "2026-09-01T12:00:00-07:00"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    assert task_id.startswith("stu:")

    assert client.delete(f"/api/thrive/tasks/{task_id}").status_code == 204
    assert client.delete("/api/thrive/tasks/asg:a1").status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_task_writes.py -v` — Expected: FAIL with 404s (routes missing).

- [ ] **Step 3: Implement**

Append to `backend/rsm_thrive/views/tasks.py`:

```python
import datetime as dt

from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, parse_body
from rsm_thrive.models import StudentTask, TaskOverride

OVERRIDE_FACETS = {
    "done": "done", "title": "title", "priority": "priority",
    "dueDate": "due_date", "order": "sort_order", "subtaskDone": "subtask_done",
}


def _parse_instant(value: str) -> dt.datetime:
    parsed = parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        raise BadRequest("dueDate must be an ISO-8601 instant with offset.")
    return parsed


@api_login_required
@require_http_methods(["PATCH"])
def override(request, task_id):
    current = {t["id"]: t for t in assemble_tasks(request.user)}
    if task_id not in current:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    try:
        body = parse_body(request)
        row, _ = TaskOverride.objects.get_or_create(user=request.user, task_key=task_id)
        for key, value in body.items():
            if key not in OVERRIDE_FACETS:
                raise BadRequest(f"Unknown facet {key}.")
            if key == "dueDate" and value is not None:
                value = _parse_instant(value)
            setattr(row, OVERRIDE_FACETS[key], value)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    if all(getattr(row, f) is None for f in OVERRIDE_FACETS.values()):
        row.delete()
    else:
        row.save()
    merged = {t["id"]: t for t in assemble_tasks(request.user)}
    return json_ok(merged[task_id])


@api_login_required
@require_http_methods(["POST"])
def create_task(request):
    try:
        body = parse_body(request)
        title = body.get("title") or ""
        if not title.strip():
            raise BadRequest("title is required.")
        due = _parse_instant(body.get("dueDate") or "")
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    row = StudentTask.objects.create(
        user=request.user, title=title.strip(), due_date=due,
        priority=body.get("priority", "medium"), source=body.get("source", "admin"),
    )
    merged = {t["id"]: t for t in assemble_tasks(request.user)}
    return json_ok(merged[f"stu:{row.pk}"], status=201)


@api_login_required
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    if not task_id.startswith("stu:"):
        return json_error("not_deletable", "Only self-added tasks can be deleted.", 400)
    deleted, _ = StudentTask.objects.filter(
        user=request.user, pk=task_id.removeprefix("stu:")
    ).delete()
    if not deleted:
        return json_error("unknown_task", f"No task {task_id}.", 404)
    TaskOverride.objects.filter(user=request.user, task_key=task_id).delete()
    from django.http import HttpResponse
    return HttpResponse(status=204)
```

Routes in `urls.py`:

```python
path("tasks", tasks.tasks_dispatch, name="tasks"),
path("tasks/<str:task_id>", tasks.delete_task, name="task-delete"),
path("tasks/<str:task_id>/override", tasks.override, name="task-override"),
```

with a small dispatcher in `views/tasks.py` (GET list / POST create on one path):

```python
def tasks_dispatch(request):
    if request.method == "POST":
        return create_task(request)
    return tasks(request)
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): task override and student task write endpoints"
```

---

### Task 11: Event ignores/joins, calendar prefs, task notes + GET /overlay

**Files:**
- Create: `backend/rsm_thrive/views/overlay.py`
- Modify: `backend/rsm_thrive/models/overlay.py`, `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_overlay.py`

**Interfaces:**
- Produces models (append to `models/overlay.py`):
  - `IgnoredEvent(user FK, event_id: Char(64))` unique `(user, event_id)`
  - `EventJoin(user FK, event_id: Char(64))` unique `(user, event_id)`
  - `CalendarPrefs(user OneToOne, prefs: JSON dict default {})`
  - `TaskNote(user FK, task_key: Char(80), note: Text)` unique `(user, task_key)`
- Produces routes:
  - `GET /api/thrive/overlay` → `{"ignoredEventIds": [...], "joinedEventIds": [...], "calendarPrefs": {...}, "taskNotes": {taskKey: note}}` (one call hydrates all client stores).
  - `PUT /api/thrive/events/<event_id>/ignore` + `DELETE` same path (idempotent).
  - `PUT /api/thrive/events/<event_id>/join` + `DELETE` same path (idempotent).
  - `PUT /api/thrive/calendar-prefs` — body is the whole prefs object (client-owned shape, ≤8KB or 400).
  - `PUT /api/thrive/tasks/<task_id>/note` — body `{"note": str}`; empty/whitespace note deletes the row.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_overlay.py`:

```python
import json

import pytest

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def _put(client, path, body=None):
    return client.put(path, data=json.dumps(body or {}),
                      content_type="application/json")


def test_overlay_roundtrip(client):
    profile = make_student()
    client.force_login(profile.user)

    assert _put(client, "/api/thrive/events/evt-1/ignore").status_code == 204
    assert _put(client, "/api/thrive/events/evt-1/ignore").status_code == 204  # idempotent
    assert _put(client, "/api/thrive/events/evt-2/join").status_code == 204
    assert _put(client, "/api/thrive/calendar-prefs",
                {"view": "week", "filters": ["rady"]}).status_code == 204
    assert _put(client, "/api/thrive/tasks/asg:a1/note",
                {"note": "ask about rubric"}).status_code == 204

    body = client.get("/api/thrive/overlay").json()
    assert body == {
        "ignoredEventIds": ["evt-1"],
        "joinedEventIds": ["evt-2"],
        "calendarPrefs": {"view": "week", "filters": ["rady"]},
        "taskNotes": {"asg:a1": "ask about rubric"},
    }

    client.delete("/api/thrive/events/evt-1/ignore")
    _put(client, "/api/thrive/tasks/asg:a1/note", {"note": "  "})  # empty deletes
    body = client.get("/api/thrive/overlay").json()
    assert body["ignoredEventIds"] == [] and body["taskNotes"] == {}
```

- [ ] **Step 2: Run to verify failure** — Expected: 404s.

- [ ] **Step 3: Implement**

Models (append to `models/overlay.py`):

```python
class IgnoredEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "event_id"],
                                               name="uniq_ignored_event")]


class EventJoin(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "event_id"],
                                               name="uniq_event_join")]


class CalendarPrefs(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prefs = models.JSONField(default=dict)


class TaskNote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_key = models.CharField(max_length=80)
    note = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "task_key"],
                                               name="uniq_task_note")]
```

`backend/rsm_thrive/views/overlay.py`:

```python
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import BadRequest, api_login_required, json_error, json_ok, parse_body
from rsm_thrive.models import CalendarPrefs, EventJoin, IgnoredEvent, TaskNote


@api_login_required
def overlay(request):
    prefs = CalendarPrefs.objects.filter(user=request.user).first()
    return json_ok({
        "ignoredEventIds": sorted(
            IgnoredEvent.objects.filter(user=request.user)
            .values_list("event_id", flat=True)
        ),
        "joinedEventIds": sorted(
            EventJoin.objects.filter(user=request.user)
            .values_list("event_id", flat=True)
        ),
        "calendarPrefs": prefs.prefs if prefs else {},
        "taskNotes": {
            n.task_key: n.note for n in TaskNote.objects.filter(user=request.user)
        },
    })


def _flag_views(model):
    @api_login_required
    @require_http_methods(["PUT", "DELETE"])
    def view(request, event_id):
        if request.method == "PUT":
            model.objects.get_or_create(user=request.user, event_id=event_id)
        else:
            model.objects.filter(user=request.user, event_id=event_id).delete()
        return HttpResponse(status=204)
    return view


ignore_event = _flag_views(IgnoredEvent)
join_event = _flag_views(EventJoin)


@api_login_required
@require_http_methods(["PUT"])
def calendar_prefs(request):
    if len(request.body) > 8192:
        return json_error("too_large", "Prefs object too large.", 400)
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    row, _ = CalendarPrefs.objects.get_or_create(user=request.user)
    row.prefs = body
    row.save()
    return HttpResponse(status=204)


@api_login_required
@require_http_methods(["PUT"])
def task_note(request, task_id):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    note = (body.get("note") or "").strip()
    if note:
        TaskNote.objects.update_or_create(
            user=request.user, task_key=task_id, defaults={"note": note}
        )
    else:
        TaskNote.objects.filter(user=request.user, task_key=task_id).delete()
    return HttpResponse(status=204)
```

Routes:

```python
path("overlay", overlay.overlay, name="overlay"),
path("events/<str:event_id>/ignore", overlay.ignore_event, name="event-ignore"),
path("events/<str:event_id>/join", overlay.join_event, name="event-join"),
path("calendar-prefs", overlay.calendar_prefs, name="calendar-prefs"),
path("tasks/<str:task_id>/note", overlay.task_note, name="task-note"),
```

Re-export models; `makemigrations`.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): overlay stores (ignores, joins, prefs, notes)"
```

---

### Task 12: Degree progress + program timeline

**Files:**
- Create: `backend/rsm_thrive/models/degree.py`, `backend/rsm_thrive/services/degree.py`, `backend/rsm_thrive/views/degree.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_degree.py`

**Interfaces:**
- Produces models:
  - `ProgramPhaseRow(track, phase_id: orientation|fall|winter|spring|summer|optional-fall, label, term, start: Date, end: Date, optional: bool)` — one active cohort per track (documented limitation; a cohort FK arrives when a second cohort exists). `Meta.ordering = ["start"]`, unique `(track, phase_id)`.
  - `DegreeRequirement(track unique, units_required, core_required, elective_required)`
  - `DegreeGap(user FK, label, detail, severity: Standing)`
- Produces service `services.degree`:
  - `program_timeline(profile, today: date) -> dict` matching `ProgramTimeline`: phase `status` = `complete` (end < today) / `current` (start ≤ today ≤ end) / `upcoming`; `currentPhaseId` = current phase's id else `None`; `programEnd` = max end of non-optional phases for the track; `percentComplete` = position of today between `programStart` and `programEnd`, clamped to 0–100, rounded to int; `expectedFinishTerm` = term of the phase whose end is `programEnd`.
  - `degree_progress(profile) -> dict` matching `DegreeProgress`: `unitsCompleted` = sum of units of completed enrollments; `coreDone`/`electiveDone` = counts of completed enrollments by bucket; requirements from `DegreeRequirement` for the track; `gaps` from `DegreeGap` rows (id serialized as `gap-<pk>`).
- Routes: `GET /api/thrive/degree/timeline`, `GET /api/thrive/degree/progress`.
- Factories: `make_phase(track, phase_id, start, end, **kw)`, `make_requirement(track, **kw)`, `make_gap(profile, **kw)`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_degree.py`:

```python
import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_course, make_gap, make_phase, make_requirement, make_student,
)

pytestmark = pytest.mark.django_db


def _phases(track="11 month"):
    today = timezone.localdate()
    make_phase(track, "orientation", today - dt.timedelta(days=40),
               today - dt.timedelta(days=30), label="Orientation", term="Fall 2026")
    make_phase(track, "fall", today - dt.timedelta(days=29),
               today + dt.timedelta(days=30), label="Fall Quarter", term="Fall 2026")
    make_phase(track, "winter", today + dt.timedelta(days=31),
               today + dt.timedelta(days=120), label="Winter Quarter", term="Winter 2027")


def test_timeline_statuses_and_percent(client):
    profile = make_student(program_start=timezone.localdate() - dt.timedelta(days=40))
    _phases()
    client.force_login(profile.user)
    body = client.get("/api/thrive/degree/timeline").json()

    statuses = {p["id"]: p["status"] for p in body["phases"]}
    assert statuses == {"orientation": "complete", "fall": "current",
                        "winter": "upcoming"}
    assert body["currentPhaseId"] == "fall"
    assert body["track"] == "11 month"
    assert body["expectedFinishTerm"] == "Winter 2027"
    assert 0 <= body["percentComplete"] <= 100
    assert body["programEnd"] == body["phases"][-1]["end"]


def test_degree_progress_counts(client):
    profile = make_student()
    make_requirement("11 month", units_required=50, core_required=8,
                     elective_required=4)
    done_core = make_course(id="c1", units=4)
    done_elec = make_course(id="c2", units=4)
    pending = make_course(id="c3", units=4)
    enroll(profile, done_core, bucket="core", completed=True)
    enroll(profile, done_elec, bucket="elective", completed=True)
    enroll(profile, pending, bucket="core", completed=False)
    make_gap(profile, label="Capstone not scheduled", severity="watch")

    client.force_login(profile.user)
    body = client.get("/api/thrive/degree/progress").json()
    assert body["unitsCompleted"] == 8
    assert body["unitsRequired"] == 50
    assert body["coreDone"] == 1 and body["coreRequired"] == 8
    assert body["electiveDone"] == 1 and body["electiveRequired"] == 4
    assert body["gaps"][0]["label"] == "Capstone not scheduled"
    assert body["track"] == "11 month"
```

- [ ] **Step 2: Run to verify failure** — Expected: import errors.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/degree.py`:

```python
from django.conf import settings
from django.db import models

from .students import STANDING_CHOICES, TRACK_CHOICES

PHASE_ID_CHOICES = [
    ("orientation", "orientation"), ("fall", "fall"), ("winter", "winter"),
    ("spring", "spring"), ("summer", "summer"), ("optional-fall", "optional-fall"),
]


class ProgramPhaseRow(models.Model):
    track = models.CharField(max_length=16, choices=TRACK_CHOICES)
    phase_id = models.CharField(max_length=16, choices=PHASE_ID_CHOICES)
    label = models.CharField(max_length=60)
    term = models.CharField(max_length=40)
    start = models.DateField()
    end = models.DateField()
    optional = models.BooleanField(default=False)

    class Meta:
        ordering = ["start"]
        constraints = [models.UniqueConstraint(fields=["track", "phase_id"],
                                               name="uniq_phase_per_track")]


class DegreeRequirement(models.Model):
    track = models.CharField(max_length=16, choices=TRACK_CHOICES, unique=True)
    units_required = models.PositiveSmallIntegerField()
    core_required = models.PositiveSmallIntegerField()
    elective_required = models.PositiveSmallIntegerField()


class DegreeGap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=120)
    detail = models.CharField(max_length=400, default="")
    severity = models.CharField(max_length=16, choices=STANDING_CHOICES, default="watch")
```

`backend/rsm_thrive/services/degree.py`:

```python
from rsm_thrive.models import DegreeGap, DegreeRequirement, Enrollment, ProgramPhaseRow
from rsm_thrive.serialize import iso_date


def _phase_status(phase, today):
    if phase.end < today:
        return "complete"
    if phase.start <= today:
        return "current"
    return "upcoming"


def program_timeline(profile, today) -> dict:
    rows = list(ProgramPhaseRow.objects.filter(track=profile.track))
    required = [p for p in rows if not p.optional]
    program_end = max(p.end for p in required)
    finish_term = max(required, key=lambda p: p.end).term
    span = (program_end - profile.program_start).days or 1
    pct = round(100 * (today - profile.program_start).days / span)
    current = next((p for p in rows if _phase_status(p, today) == "current"), None)
    return {
        "phases": [{
            "id": p.phase_id, "label": p.label, "term": p.term,
            "start": iso_date(p.start), "end": iso_date(p.end),
            "optional": p.optional, "status": _phase_status(p, today),
        } for p in rows],
        "currentPhaseId": current.phase_id if current else None,
        "percentComplete": max(0, min(100, pct)),
        "programStart": iso_date(profile.program_start),
        "programEnd": iso_date(program_end),
        "expectedFinishTerm": finish_term,
        "track": profile.track,
    }


def degree_progress(profile) -> dict:
    req = DegreeRequirement.objects.get(track=profile.track)
    completed = (Enrollment.objects.filter(user=profile.user, completed=True)
                 .select_related("course"))
    return {
        "unitsCompleted": sum(e.course.units for e in completed),
        "unitsRequired": req.units_required,
        "coreDone": sum(1 for e in completed if e.bucket == "core"),
        "coreRequired": req.core_required,
        "electiveDone": sum(1 for e in completed if e.bucket == "elective"),
        "electiveRequired": req.elective_required,
        "gaps": [{
            "id": f"gap-{g.pk}", "label": g.label, "detail": g.detail,
            "severity": g.severity,
        } for g in DegreeGap.objects.filter(user=profile.user).order_by("pk")],
        "track": profile.track,
    }
```

`backend/rsm_thrive/views/degree.py`:

```python
from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.services.degree import degree_progress, program_timeline


@api_login_required
def timeline(request):
    return json_ok(program_timeline(request.user.thrive_profile, timezone.localdate()))


@api_login_required
def progress(request):
    return json_ok(degree_progress(request.user.thrive_profile))
```

Factories:

```python
from rsm_thrive.models import DegreeGap, DegreeRequirement, ProgramPhaseRow


def make_phase(track, phase_id, start, end, **overrides) -> ProgramPhaseRow:
    fields = {"label": phase_id.title(), "term": "Fall 2026", "optional": False}
    fields.update(overrides)
    return ProgramPhaseRow.objects.create(
        track=track, phase_id=phase_id, start=start, end=end, **fields
    )


def make_requirement(track, **overrides) -> DegreeRequirement:
    fields = {"units_required": 50, "core_required": 8, "elective_required": 4}
    fields.update(overrides)
    return DegreeRequirement.objects.create(track=track, **fields)


def make_gap(profile, **overrides) -> DegreeGap:
    fields = {"label": "Gap", "detail": "Why it matters.", "severity": "watch"}
    fields.update(overrides)
    return DegreeGap.objects.create(user=profile.user, **fields)
```

Routes: `path("degree/timeline", degree.timeline)`, `path("degree/progress", degree.progress)`. Re-export models; `makemigrations`.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): degree progress and program timeline"
```

---

### Task 13: Contract test suite + seed_demo command

**Files:**
- Create: `backend/rsm_thrive/tests/contract/__init__.py`, `backend/rsm_thrive/tests/contract/schemas.py`, `backend/rsm_thrive/tests/contract/test_contract.py`, `backend/rsm_thrive/management/__init__.py`, `backend/rsm_thrive/management/commands/__init__.py`, `backend/rsm_thrive/management/commands/seed_demo.py`

**Interfaces:**
- Consumes: every factory and endpoint from Tasks 3–12.
- Produces:
  - `schemas.py` — JSON Schemas (draft 2020-12) transcribed from `frontend/src/lib/data/types.ts` for: `STUDENT`, `COURSE`, `SYLLABUS`, `ASSIGNMENT`, `TASK`, `EVENT`, `RESOURCE_LINK`, `DEGREE_PROGRESS`, `PROGRAM_TIMELINE`, `OVERLAY`. Each schema sets `"additionalProperties": false` and marks contract-optional keys as optional — a stray or misnamed key fails the suite. Shared `ISO_INSTANT = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$"}` and `ISO_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}` subschemas; closed unions as `"enum"` lists copied verbatim from `types.ts` (e.g. `"track": {"enum": ["11 month", "17 month"]}`).
  - `test_contract.py` — one seeded world, then every GET endpoint's response validated item-by-item with `jsonschema.validate`.
  - `manage.py seed_demo` — idempotent demo world reusing `testing.py` factories (one student `demo` with profile, two courses with meetings/syllabi/assignments, four events, three resources, phases + requirement for both tracks, one shared task) for local browsing and later server demos.

- [ ] **Step 1: Write schemas and the failing contract test**

`backend/rsm_thrive/tests/contract/schemas.py` (transcribe every schema fully; the two shown here set the pattern — the rest follow `types.ts` field-for-field):

```python
ISO_INSTANT = {"type": "string",
               "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$"}
ISO_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
STANDING = {"enum": ["onTrack", "watch", "needsHelp"]}
TRACK = {"enum": ["11 month", "17 month"]}
PRIORITY = {"enum": ["low", "medium", "high"]}

STUDENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "goal", "track", "program", "standingSummary",
                 "standing", "consent", "currentTerm", "programStart"],
    "properties": {
        "id": {"type": "string"}, "name": {"type": "string"},
        "goal": {"type": "string"}, "track": TRACK, "program": {"type": "string"},
        "standingSummary": {"type": "string"}, "standing": STANDING,
        "consent": {
            "type": "object", "additionalProperties": False,
            "required": ["calendarRead", "lmsRead", "careerRecommendations",
                         "advisorSharing"],
            "properties": {k: {"type": "boolean"} for k in
                           ["calendarRead", "lmsRead", "careerRecommendations",
                            "advisorSharing"]},
        },
        "avatarUrl": {"type": "string"},
        "currentTerm": {"type": "string"}, "programStart": ISO_DATE,
    },
}

TASK = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "dueDate", "source", "priority", "done", "subtasks"],
    "properties": {
        "id": {"type": "string"}, "title": {"type": "string"},
        "dueDate": ISO_INSTANT,
        "source": {"enum": ["class", "career", "admin", "event"]},
        "priority": PRIORITY, "done": {"type": "boolean"},
        "subtasks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "title", "done"],
            "properties": {"id": {"type": "string"}, "title": {"type": "string"},
                           "done": {"type": "boolean"}},
        }},
        "courseId": {"type": "string"}, "courseCode": {"type": "string"},
    },
}

# COURSE, SYLLABUS, ASSIGNMENT, EVENT, RESOURCE_LINK, DEGREE_PROGRESS,
# PROGRAM_TIMELINE, OVERLAY: transcribe from frontend/src/lib/data/types.ts
# with the same rigor — additionalProperties false, optionals omitted from
# "required", enums copied verbatim.
```

`backend/rsm_thrive/tests/contract/test_contract.py`:

```python
import datetime as dt

import jsonschema
import pytest
from django.utils import timezone

from rsm_thrive.testing import (
    enroll, make_assignment, make_course, make_event, make_gap, make_meeting,
    make_phase, make_requirement, make_resource, make_shared_task, make_student,
    make_student_task, make_syllabus, set_assignment_status, set_override,
)
from . import schemas

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(client):
    profile = make_student(goal="Data Scientist")
    course = make_course(id="c1")
    make_meeting(course)
    make_syllabus(course, source_url="https://rady.ucsd.edu/syllabus.pdf")
    a1 = make_assignment(course, id="a1", weight=30)
    make_assignment(course, id="a2", due=timezone.now() + timezone.timedelta(days=9))
    enroll(profile, course, nudge="Check in", current_grade="A-",
           bucket="core", completed=False)
    set_assignment_status(profile, a1, "graded", grade="A")
    set_override(profile, "asg:a1", done=False, title="Renamed")
    make_shared_task(source="career")
    make_student_task(profile)
    make_event(goal_tags=["data scientist"], end=timezone.now() + timezone.timedelta(days=3))
    make_resource(owner="Rady CMC")
    today = timezone.localdate()
    make_phase("11 month", "fall", today - dt.timedelta(days=10),
               today + dt.timedelta(days=60))
    make_requirement("11 month")
    make_gap(profile)
    client.force_login(profile.user)
    return profile


CASES = [
    ("/api/thrive/me", schemas.STUDENT, False),
    ("/api/thrive/courses", schemas.COURSE, True),
    ("/api/thrive/syllabi", schemas.SYLLABUS, True),
    ("/api/thrive/assignments", schemas.ASSIGNMENT, True),
    ("/api/thrive/tasks", schemas.TASK, True),
    ("/api/thrive/events", schemas.EVENT, True),
    ("/api/thrive/resources", schemas.RESOURCE_LINK, True),
    ("/api/thrive/degree/progress", schemas.DEGREE_PROGRESS, False),
    ("/api/thrive/degree/timeline", schemas.PROGRAM_TIMELINE, False),
    ("/api/thrive/overlay", schemas.OVERLAY, False),
]


@pytest.mark.parametrize("path,schema,is_list", CASES)
def test_contract(world, client, path, schema, is_list):
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    if is_list:
        assert isinstance(body, list) and body, f"{path} returned an empty list"
        for item in body:
            jsonschema.validate(item, schema)
    else:
        jsonschema.validate(body, schema)
```

- [ ] **Step 2: Run to verify failure** — schemas incomplete → `AttributeError` on missing schema names. Complete all ten schemas until the suite runs.

- [ ] **Step 3: Write seed_demo**

`backend/rsm_thrive/management/commands/seed_demo.py`:

```python
import datetime as dt

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from rsm_thrive import testing as t
from rsm_thrive.models import StudentProfile


class Command(BaseCommand):
    help = "Seed an idempotent demo world for local browsing."

    def handle(self, *args, **options):
        if get_user_model().objects.filter(username="demo").exists():
            self.stdout.write("demo world already seeded")
            return
        profile = t.make_student(username="demo", display_name="Demo Student",
                                 goal="Data Scientist")
        for i in (1, 2):
            course = t.make_course(id=f"demo-c{i}")
            t.make_meeting(course, day_of_week=1 + i)
            t.make_syllabus(course)
            t.make_assignment(course, weight=30)
            t.make_assignment(course, due=timezone.now() + dt.timedelta(days=10 + i))
            t.enroll(profile, course, bucket="core" if i == 1 else "elective")
        for _ in range(4):
            t.make_event(goal_tags=["data scientist"])
        for cat in ("academic", "career", "technical"):
            t.make_resource(category=cat)
        t.make_shared_task(source="career")
        today = timezone.localdate()
        for track in ("11 month", "17 month"):
            t.make_phase(track, "fall", today - dt.timedelta(days=10),
                         today + dt.timedelta(days=60), term="Fall 2026")
            t.make_requirement(track)
        self.stdout.write(self.style.SUCCESS("demo world seeded (user: demo)"))
```

- [ ] **Step 4: Run everything**

Run: `uv run pytest -v && uv run python manage.py migrate && uv run python manage.py seed_demo`
Expected: full suite PASSES (contract cases included); seed command prints success and is a no-op on the second run.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "test(backend): contract schema suite and seed_demo command"
```

---

## Plan Self-Review (completed at authoring)

- **Spec coverage:** F1 scope = spec §2 (identity mechanics live in F4's frontend half; the Django `/me` half is Task 3), §3.1–3.2 (Tasks 3–4, 7–9, 12), §4 read endpoints + overlay writes (Tasks 5–6, 8–11) and contract-test layer (Task 13). Appointments (§3.3, §3.5), chat (§5), jobs (§6), Canvas sync (§3.1 ingestion), deployment (§7) are explicitly out of F1 → plans F2–F5.
- **Placeholder scan:** the one intentional summary is Task 13's schema list (two schemas shown fully, eight transcribed from `types.ts` by the same explicit rules — the source of truth is named and the rules are stated; duplicating all ten inline would drift from `types.ts` faster than it would help).
- **Type consistency:** task-id prefixes (`asg:`/`shared:`/`stu:`), `assemble_tasks(user)`, facet map keys (`dueDate→due_date`, `order→sort_order`, `subtaskDone→subtask_done`), and factory signatures are used identically across Tasks 9, 10, 11, and 13.
