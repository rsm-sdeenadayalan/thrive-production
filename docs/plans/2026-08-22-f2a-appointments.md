# F2a — Appointments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real appointment booking with CMC/GSA advisors: race-safe slot claiming at the database level, ICS calendar-invite emails to student and advisor, Zoom meetings behind a swappable client (fake until credentials exist), and an auditable notification trail.

**Architecture:** Extends the F1 `rsm_thrive` Django app. New models in `models/appointments.py`; read endpoints mirror the F1 pattern (thin views, contract-exact serializers, sorts in querysets). Booking integrity comes from a partial unique constraint (`slot` unique among `status="confirmed"` rows) so double-booking is impossible even under races, and cancelling frees the slot automatically. Side effects (Zoom, emails) run through `services/notifications.py`, which records every attempt in `AppointmentNotification` and never breaks a booking — Celery migration later is a `.delay()`-shaped change, deliberately deferred until server deployment (F5) where the queue exists.

**Tech Stack:** Python ≥3.12, Django ≥5.2, uv, pytest + pytest-django, `requests` (new runtime dep, Zoom API), Django email framework (locmem in tests).

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §3.3, §3.5, §4 (appointments rows). Course requests + resume providers are F2b, NOT here. Real Zoom credentials and SMTP are external asks (`docs/VINCENT-ASKS.md` #5, #8); everything here works without them.

## Global Constraints

- JSON keys camelCase matching `frontend/src/lib/data/types.ts` exactly. Closed unions verbatim: `AdvisingService` = `"advising" | "career"`; `MeetingMode` = `"in person" | "zoom"` (space preserved); `AppointmentStatus` = `"confirmed" | "cancelled"`.
- Contract shapes: `Advisor{id,name,role,service,avatar?,location,blurb?}` (optional keys omitted when blank); `AppointmentSlot{id,advisorId,start,end,mode,available}` (all required — taken slots are still returned, with `available: false`); `Appointment{id,advisorId,studentId,slotId,start,end,mode,reason,status}` (all required; `studentId` = username).
- Instants via `iso_instant`; guaranteed sorts in querysets: advisors (service, name, id), slots (start, id), my-appointments confirmed-only (start, id).
- Error envelope `{"error": {"code", "message"}}`; unauthenticated → 401. Booking error copy is user-facing contract text: unknown slot → **404** code `slot_unknown` message `"That time is no longer listed."`; taken slot → **409** code `slot_unavailable` message `"That time was just taken. Pick another."` (F4 maps these onto `SlotUnavailableError`).
- Side effects NEVER fail a booking or cancel: every Zoom/email attempt lands in `AppointmentNotification` as sent/failed/skipped.
- All commands from `backend/` via `uv run`. Commit after every task on `main`.

---

### Task 1: Appointment models + factories

**Files:**
- Create: `backend/rsm_thrive/models/appointments.py`
- Modify: `backend/rsm_thrive/models/__init__.py`, `backend/rsm_thrive/testing.py`
- Test: `backend/rsm_thrive/tests/test_appointment_models.py`

**Interfaces:**
- Produces models:
  - `Advisor(id: Char pk 64, name, role, service: advising|career, avatar_url blank, location, blurb blank, email)` — `email` is internal (never serialized).
  - `AppointmentSlot(id: Char pk 64, advisor FK related_name="slots", start: DateTime, end: DateTime, mode: "in person"|"zoom")`.
  - `Appointment(pk BigAuto, slot FK, student FK user, reason: Text, status: confirmed|cancelled default confirmed, zoom_join_url blank, created_at auto_now_add)` with `UniqueConstraint(fields=["slot"], condition=Q(status="confirmed"), name="uniq_confirmed_slot")`.
  - `AppointmentNotification(appointment FK related_name="notifications", kind: zoom|email_request|email_cancel, status: sent|failed|skipped, detail: Text blank, attempts: int default 1, created_at auto_now_add, updated_at auto_now)`.
- Produces factories: `make_advisor(id=None, **overrides)` (defaults: name "Casey Advisor <n>", role "Graduate Student Advisor", service "advising", location "Rady 2S111", email "advisor<n>@ucsd.edu"); `make_slot(advisor, start=None, **overrides)` (defaults: start now+2d, end start+30min, mode "zoom").
- Also: `make_student` gains a real email — `create_user(username=username, email=f"{username}@ucsd.edu")`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_appointment_models.py`:

```python
import pytest
from django.db import IntegrityError, transaction

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_only_one_confirmed_appointment_per_slot():
    slot = make_slot(make_advisor())
    a = make_student(username="a")
    b = make_student(username="b")
    Appointment.objects.create(slot=slot, student=a.user, reason="r1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Appointment.objects.create(slot=slot, student=b.user, reason="r2")


def test_cancelled_appointment_frees_the_slot():
    slot = make_slot(make_advisor())
    a = make_student(username="a")
    b = make_student(username="b")
    first = Appointment.objects.create(slot=slot, student=a.user, reason="r1")
    first.status = "cancelled"
    first.save()
    second = Appointment.objects.create(slot=slot, student=b.user, reason="r2")
    assert second.pk != first.pk


def test_student_factory_has_email():
    profile = make_student(username="ada")
    assert profile.user.email == "ada@ucsd.edu"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest rsm_thrive/tests/test_appointment_models.py -v`
Expected: FAIL (`ImportError: make_advisor`).

- [ ] **Step 3: Implement**

`backend/rsm_thrive/models/appointments.py`:

```python
from django.conf import settings
from django.db import models
from django.db.models import Q

SERVICE_CHOICES = [("advising", "advising"), ("career", "career")]
MODE_CHOICES = [("in person", "in person"), ("zoom", "zoom")]
APPOINTMENT_STATUS_CHOICES = [("confirmed", "confirmed"), ("cancelled", "cancelled")]
NOTIFICATION_KIND_CHOICES = [
    ("zoom", "zoom"), ("email_request", "email_request"), ("email_cancel", "email_cancel"),
]
NOTIFICATION_STATUS_CHOICES = [("sent", "sent"), ("failed", "failed"), ("skipped", "skipped")]


class Advisor(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    service = models.CharField(max_length=16, choices=SERVICE_CHOICES)
    avatar_url = models.URLField(blank=True, default="")
    location = models.CharField(max_length=200)
    blurb = models.CharField(max_length=240, blank=True, default="")
    email = models.EmailField()  # internal: invite recipient, never serialized


class AppointmentSlot(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    advisor = models.ForeignKey(Advisor, on_delete=models.CASCADE, related_name="slots")
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="zoom")


class Appointment(models.Model):
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.PROTECT)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=APPOINTMENT_STATUS_CHOICES,
                              default="confirmed")
    zoom_join_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slot"], condition=Q(status="confirmed"),
                name="uniq_confirmed_slot",
            ),
        ]


class AppointmentNotification(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE,
                                    related_name="notifications")
    kind = models.CharField(max_length=16, choices=NOTIFICATION_KIND_CHOICES)
    status = models.CharField(max_length=16, choices=NOTIFICATION_STATUS_CHOICES)
    detail = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Re-export all four in `models/__init__.py` (keep alphabetical grouping by module).

`testing.py`: change `make_student`'s user creation to
`get_user_model().objects.create_user(username=username, email=f"{username}@ucsd.edu")`,
and append (merging model imports into the existing import):

```python
from rsm_thrive.models import Advisor, AppointmentSlot


def make_advisor(id=None, **overrides) -> Advisor:
    n = next(_counter)
    fields = {
        "id": id or f"adv-{n}",
        "name": f"Casey Advisor {n}",
        "role": "Graduate Student Advisor",
        "service": "advising",
        "location": "Rady 2S111",
        "email": f"advisor{n}@ucsd.edu",
    }
    fields.update(overrides)
    return Advisor.objects.create(**fields)


def make_slot(advisor, start=None, **overrides) -> AppointmentSlot:
    n = next(_counter)
    start = start or (timezone.now() + timezone.timedelta(days=2))
    fields = {
        "id": f"slot-{n}",
        "start": start,
        "end": start + timezone.timedelta(minutes=30),
        "mode": "zoom",
    }
    fields.update(overrides)
    return AppointmentSlot.objects.create(advisor=advisor, **fields)
```

- [ ] **Step 4: Migrate + run tests**

Run: `uv run python manage.py makemigrations rsm_thrive && uv run pytest -v`
Expected: all PASS (54 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): appointment models with race-safe slot constraint"
```

---

### Task 2: GET /advisors and GET /advisors/{id}/slots

**Files:**
- Create: `backend/rsm_thrive/serializers/appointments.py`, `backend/rsm_thrive/views/advisors.py`
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_advisors.py`

**Interfaces:**
- Consumes: Task 1 models/factories; `iso_instant`, `api_login_required`, `json_ok`, `json_error`.
- Produces:
  - `serializers.appointments.advisor_payload(advisor) -> dict` (avatar/blurb omitted when blank; `avatar` key from `avatar_url` field).
  - `serializers.appointments.slot_payload(slot, available: bool) -> dict`.
  - Routes: `GET /api/thrive/advisors` (sorted service, name, id), `GET /api/thrive/advisors/<advisor_id>/slots` (sorted start, id; unknown advisor → 404 `unknown_advisor`; `available` computed = no confirmed appointment on the slot).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_advisors.py`:

```python
import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_advisors_shape_and_sort(client):
    profile = make_student()
    make_advisor(id="a2", name="Zoe", service="career", blurb="Careers")
    make_advisor(id="a1", name="Ana", service="advising",
                 avatar_url="https://rady.ucsd.edu/a.png")
    client.force_login(profile.user)
    body = client.get("/api/thrive/advisors").json()
    assert [a["id"] for a in body] == ["a1", "a2"]  # advising < career
    assert body[0]["avatar"] == "https://rady.ucsd.edu/a.png"
    assert "blurb" not in body[0]
    assert body[1]["blurb"] == "Careers"
    assert "avatar" not in body[1]
    assert "email" not in body[0] and "email" not in body[1]  # internal field


def test_slots_availability_and_sort(client):
    profile = make_student()
    other = make_student(username="other")
    adv = make_advisor(id="a1")
    import datetime as dt
    from django.utils import timezone
    base = timezone.now() + dt.timedelta(days=3)
    s2 = make_slot(adv, start=base + dt.timedelta(hours=1))
    s1 = make_slot(adv, start=base)
    Appointment.objects.create(slot=s1, student=other.user, reason="x")

    client.force_login(profile.user)
    body = client.get(f"/api/thrive/advisors/{adv.id}/slots").json()
    assert [s["id"] for s in body] == [s1.id, s2.id]       # start asc
    assert body[0]["available"] is False                    # taken, still listed
    assert body[1]["available"] is True
    assert body[0]["advisorId"] == "a1"
    assert body[0]["mode"] == "zoom"


def test_slots_unknown_advisor_404(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/advisors/nope/slots")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "unknown_advisor"
```

- [ ] **Step 2: Run to verify failure** — Expected: 404s / import errors.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/serializers/appointments.py`:

```python
from rsm_thrive.serialize import iso_instant


def advisor_payload(advisor) -> dict:
    payload = {
        "id": advisor.id,
        "name": advisor.name,
        "role": advisor.role,
        "service": advisor.service,
        "location": advisor.location,
    }
    if advisor.avatar_url:
        payload["avatar"] = advisor.avatar_url
    if advisor.blurb:
        payload["blurb"] = advisor.blurb
    return payload


def slot_payload(slot, available: bool) -> dict:
    return {
        "id": slot.id,
        "advisorId": slot.advisor_id,
        "start": iso_instant(slot.start),
        "end": iso_instant(slot.end),
        "mode": slot.mode,
        "available": available,
    }
```

`backend/rsm_thrive/views/advisors.py`:

```python
from django.db.models import Exists, OuterRef

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Advisor, Appointment, AppointmentSlot
from rsm_thrive.serializers.appointments import advisor_payload, slot_payload


@api_login_required
def advisors(request):
    rows = Advisor.objects.order_by("service", "name", "id")
    return json_ok([advisor_payload(a) for a in rows])


@api_login_required
def advisor_slots(request, advisor_id):
    if not Advisor.objects.filter(pk=advisor_id).exists():
        return json_error("unknown_advisor", f"No advisor {advisor_id}.", 404)
    taken = Appointment.objects.filter(slot=OuterRef("pk"), status="confirmed")
    rows = (AppointmentSlot.objects.filter(advisor_id=advisor_id)
            .annotate(taken=Exists(taken)).order_by("start", "id"))
    return json_ok([slot_payload(s, not s.taken) for s in rows])
```

Routes (alphabetical import; add): `path("advisors", advisors.advisors, name="advisors")`, `path("advisors/<str:advisor_id>/slots", advisors.advisor_slots, name="advisor-slots")`.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): GET /advisors and advisor slots with availability"
```

---

### Task 3: GET /appointments

**Files:**
- Modify: `backend/rsm_thrive/serializers/appointments.py`, `backend/rsm_thrive/urls.py`
- Create: `backend/rsm_thrive/views/appointments.py`
- Test: `backend/rsm_thrive/tests/test_appointments_read.py`

**Interfaces:**
- Produces: `appointment_payload(appointment) -> dict` — id `f"appt-{pk}"`, advisorId via `slot.advisor_id`, studentId = username, slotId, start/end from the slot, mode from the slot, reason, status; route `GET /api/thrive/appointments` — **confirmed only**, own only, sorted (slot start, pk).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_appointments_read.py`:

```python
import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_my_appointments_confirmed_only_sorted(client):
    me = make_student()
    other = make_student(username="other")
    adv = make_advisor(id="a1")
    base = timezone.now() + dt.timedelta(days=3)
    late = make_slot(adv, start=base + dt.timedelta(hours=2))
    early = make_slot(adv, start=base, mode="in person")
    gone = make_slot(adv, start=base + dt.timedelta(hours=4))
    theirs = make_slot(adv, start=base + dt.timedelta(hours=6))

    a_late = Appointment.objects.create(slot=late, student=me.user, reason="r")
    a_early = Appointment.objects.create(slot=early, student=me.user, reason="q")
    Appointment.objects.create(slot=gone, student=me.user, reason="x",
                               status="cancelled")          # excluded
    Appointment.objects.create(slot=theirs, student=other.user, reason="y")  # not mine

    client.force_login(me.user)
    body = client.get("/api/thrive/appointments").json()
    assert [a["id"] for a in body] == [f"appt-{a_early.pk}", f"appt-{a_late.pk}"]
    first = body[0]
    assert first == {
        "id": f"appt-{a_early.pk}",
        "advisorId": "a1",
        "studentId": me.user.username,
        "slotId": early.id,
        "start": first["start"],
        "end": first["end"],
        "mode": "in person",
        "reason": "q",
        "status": "confirmed",
    }
    assert first["start"].endswith(("-07:00", "-08:00"))
```

- [ ] **Step 2: Run to verify failure** — Expected: 404.

- [ ] **Step 3: Implement**

Append to `serializers/appointments.py`:

```python
def appointment_payload(appointment) -> dict:
    slot = appointment.slot
    return {
        "id": f"appt-{appointment.pk}",
        "advisorId": slot.advisor_id,
        "studentId": appointment.student.username,
        "slotId": slot.id,
        "start": iso_instant(slot.start),
        "end": iso_instant(slot.end),
        "mode": slot.mode,
        "reason": appointment.reason,
        "status": appointment.status,
    }
```

`backend/rsm_thrive/views/appointments.py`:

```python
from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Appointment
from rsm_thrive.serializers.appointments import appointment_payload


@api_login_required
def my_appointments(request):
    rows = (Appointment.objects.filter(student=request.user, status="confirmed")
            .select_related("slot", "student").order_by("slot__start", "pk"))
    return json_ok([appointment_payload(a) for a in rows])
```

Route: `path("appointments", appointments.appointments_dispatch, name="appointments")` — for now `appointments_dispatch` handles GET only (`POST` arrives in Task 4):

```python
from rsm_thrive.http import json_error


def appointments_dispatch(request):
    if request.method == "GET":
        return my_appointments(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): GET /appointments (own, confirmed, sorted)"
```

---

### Task 4: POST /appointments — race-safe booking

**Files:**
- Modify: `backend/rsm_thrive/views/appointments.py`, `backend/rsm_thrive/urls.py` (none if dispatch already routed)
- Test: `backend/rsm_thrive/tests/test_booking.py`

**Interfaces:**
- Consumes: `parse_body`/`BadRequest`; Task 1 constraint.
- Produces: `POST /api/thrive/appointments` body `{"slotId": str, "reason": str}` → 201 with `appointment_payload`. Rules: reason required non-empty (truncated to `REASON_MAX = 500` chars); unknown slotId → 404 `slot_unknown` "That time is no longer listed."; slot already confirmed-booked → 409 `slot_unavailable` "That time was just taken. Pick another." (both the pre-check AND the IntegrityError race path return the same 409). Booking is `create` inside an inner `transaction.atomic()`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_booking.py`:

```python
import json

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def _book(client, slot_id, reason="Talk about electives"):
    return client.post(
        "/api/thrive/appointments",
        data=json.dumps({"slotId": slot_id, "reason": reason}),
        content_type="application/json",
    )


def test_booking_happy_path(client):
    me = make_student()
    slot = make_slot(make_advisor(id="a1"))
    client.force_login(me.user)
    resp = _book(client, slot.id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["slotId"] == slot.id and body["status"] == "confirmed"
    assert body["studentId"] == me.user.username
    # and the slot now reads unavailable
    slots = client.get("/api/thrive/advisors/a1/slots").json()
    assert slots[0]["available"] is False


def test_booking_unknown_slot_404(client):
    me = make_student()
    client.force_login(me.user)
    resp = _book(client, "slot-nope")
    assert resp.status_code == 404
    assert resp.json()["error"] == {
        "code": "slot_unknown", "message": "That time is no longer listed."}


def test_booking_taken_slot_409(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    Appointment.objects.create(slot=slot, student=other.user, reason="x")
    client.force_login(me.user)
    resp = _book(client, slot.id)
    assert resp.status_code == 409
    assert resp.json()["error"] == {
        "code": "slot_unavailable", "message": "That time was just taken. Pick another."}


def test_booking_requires_reason_and_truncates(client):
    me = make_student()
    slot = make_slot(make_advisor())
    client.force_login(me.user)
    assert _book(client, slot.id, reason="   ").status_code == 400
    resp = _book(client, slot.id, reason="x" * 600)
    assert resp.status_code == 201
    assert len(resp.json()["reason"]) == 500
```

- [ ] **Step 2: Run to verify failure** — Expected: 405 (dispatch rejects POST).

- [ ] **Step 3: Implement**

Append to `views/appointments.py` and route POST through the dispatcher:

```python
from django.db import IntegrityError, transaction

from rsm_thrive.http import BadRequest, json_error, parse_body
from rsm_thrive.models import AppointmentSlot

REASON_MAX = 500


@api_login_required
def book_appointment(request):
    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    slot_id = body.get("slotId")
    reason = (body.get("reason") or "")
    if not isinstance(reason, str) or not reason.strip():
        return json_error("bad_request", "reason is required.", 400)
    slot = AppointmentSlot.objects.filter(pk=slot_id).first() if slot_id else None
    if slot is None:
        return json_error("slot_unknown", "That time is no longer listed.", 404)
    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                slot=slot, student=request.user, reason=reason.strip()[:REASON_MAX],
            )
    except IntegrityError:
        return json_error("slot_unavailable",
                          "That time was just taken. Pick another.", 409)
    return json_ok(appointment_payload(appointment), status=201)


def appointments_dispatch(request):
    if request.method == "GET":
        return my_appointments(request)
    if request.method == "POST":
        return book_appointment(request)
    return json_error("method_not_allowed", "Use GET or POST.", 405)
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): race-safe POST /appointments with contract error copy"
```

---

### Task 5: POST /appointments/{id}/cancel

**Files:**
- Modify: `backend/rsm_thrive/views/appointments.py`, `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_cancel.py`

**Interfaces:**
- Produces: `POST /api/thrive/appointments/appt-<pk>/cancel` → 200 with the cancelled `appointment_payload`. Own appointments only; unknown id / someone else's / malformed id → 404 `unknown_appointment`. Cancelling an already-cancelled appointment is idempotent (200, same payload, no side effects re-fired — assertable in Task 6+ via notification counts). Cancel frees the slot (partial constraint no longer matches).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_cancel.py`:

```python
import json

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_cancel_own_appointment_and_rebook(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    client.force_login(me.user)

    resp = client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # idempotent second cancel
    again = client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    assert again.status_code == 200 and again.json()["status"] == "cancelled"

    # slot is free again for someone else
    client.force_login(other.user)
    resp = client.post(
        "/api/thrive/appointments",
        data=json.dumps({"slotId": slot.id, "reason": "mine now"}),
        content_type="application/json",
    )
    assert resp.status_code == 201


def test_cancel_not_yours_or_unknown_404(client):
    me = make_student()
    other = make_student(username="other")
    slot = make_slot(make_advisor())
    theirs = Appointment.objects.create(slot=slot, student=other.user, reason="r")
    client.force_login(me.user)
    assert client.post(f"/api/thrive/appointments/appt-{theirs.pk}/cancel").status_code == 404
    assert client.post("/api/thrive/appointments/appt-99999/cancel").status_code == 404
    assert client.post("/api/thrive/appointments/banana/cancel").status_code == 404
```

- [ ] **Step 2: Run to verify failure** — Expected: 404 (route missing).

- [ ] **Step 3: Implement**

Append to `views/appointments.py`:

```python
from django.views.decorators.http import require_http_methods


def _own_appointment(user, appointment_id):
    if not appointment_id.startswith("appt-"):
        return None
    pk = appointment_id.removeprefix("appt-")
    if not pk.isdigit():
        return None
    return (Appointment.objects.select_related("slot", "student")
            .filter(pk=pk, student=user).first())


@api_login_required
@require_http_methods(["POST"])
def cancel_appointment(request, appointment_id):
    appointment = _own_appointment(request.user, appointment_id)
    if appointment is None:
        return json_error("unknown_appointment", f"No appointment {appointment_id}.", 404)
    if appointment.status != "cancelled":
        appointment.status = "cancelled"
        appointment.save(update_fields=["status"])
    return json_ok(appointment_payload(appointment))
```

Route: `path("appointments/<str:appointment_id>/cancel", appointments.cancel_appointment, name="appointment-cancel")`.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): idempotent appointment cancel that frees the slot"
```

---

### Task 6: ICS invite builder

**Files:**
- Create: `backend/rsm_thrive/services/ics.py`
- Test: `backend/rsm_thrive/tests/test_ics.py`

**Interfaces:**
- Produces: `build_ics(appointment, method: str) -> str` — `method` ∈ {"REQUEST", "CANCEL"}. RFC 5545 text with CRLF line endings; `UID` = `thrive-appt-<pk>@thrive.rady.ucsd.edu`; `DTSTART`/`DTEND` in UTC (`YYYYMMDDTHHMMSSZ`); `SUMMARY` = `THRIVE: <advisor name> — <service>` with commas/semicolons escaped; `LOCATION` = zoom join URL when mode is zoom and one exists, else slot advisor's location; `ORGANIZER` = `settings.DEFAULT_FROM_EMAIL`; two `ATTENDEE` lines (student email, advisor email); `SEQUENCE:0` for REQUEST, `SEQUENCE:1` and `STATUS:CANCELLED` for CANCEL. Raises `ValueError` on any other method.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_ics.py`:

```python
import datetime as dt

import pytest

from rsm_thrive.models import Appointment
from rsm_thrive.services.ics import build_ics
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def appt():
    adv = make_advisor(id="a1", name="Casey, PhD", email="casey@ucsd.edu")
    slot = make_slot(adv, start=dt.datetime(2026, 9, 1, 16, 0, tzinfo=dt.timezone.utc))
    student = make_student(username="ada")
    return Appointment.objects.create(slot=slot, student=student.user, reason="r",
                                      zoom_join_url="https://ucsd.zoom.us/j/123")


def test_request_ics(appt):
    ics = build_ics(appt, "REQUEST")
    assert "BEGIN:VCALENDAR" in ics and ics.endswith("END:VCALENDAR\r\n")
    assert "METHOD:REQUEST" in ics
    assert f"UID:thrive-appt-{appt.pk}@thrive.rady.ucsd.edu" in ics
    assert "DTSTART:20260901T160000Z" in ics
    assert "DTEND:20260901T163000Z" in ics
    assert "SUMMARY:THRIVE: Casey\\, PhD — advising" in ics
    assert "LOCATION:https://ucsd.zoom.us/j/123" in ics
    assert "ATTENDEE:mailto:ada@ucsd.edu" in ics
    assert "ATTENDEE:mailto:casey@ucsd.edu" in ics
    assert "SEQUENCE:0" in ics
    assert "\r\n" in ics


def test_cancel_ics_and_bad_method(appt):
    ics = build_ics(appt, "CANCEL")
    assert "METHOD:CANCEL" in ics and "STATUS:CANCELLED" in ics and "SEQUENCE:1" in ics
    with pytest.raises(ValueError):
        build_ics(appt, "PUBLISH")
```

- [ ] **Step 2: Run to verify failure** — Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/services/ics.py`:

```python
"""RFC 5545 invites for appointment emails. Pure text building, no I/O."""
import datetime as dt

from django.conf import settings


def _utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def build_ics(appointment, method: str) -> str:
    if method not in ("REQUEST", "CANCEL"):
        raise ValueError(f"Unsupported ICS method {method!r}")
    slot = appointment.slot
    advisor = slot.advisor
    location = (appointment.zoom_join_url
                if slot.mode == "zoom" and appointment.zoom_join_url
                else advisor.location)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//THRIVE//Rady MSBA//EN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:thrive-appt-{appointment.pk}@thrive.rady.ucsd.edu",
        f"DTSTAMP:{_utc(dt.datetime.now(dt.timezone.utc))}",
        f"DTSTART:{_utc(slot.start)}",
        f"DTEND:{_utc(slot.end)}",
        f"SUMMARY:{_escape(f'THRIVE: {advisor.name} — {advisor.service}')}",
        f"LOCATION:{_escape(location)}",
        f"ORGANIZER:mailto:{settings.DEFAULT_FROM_EMAIL}",
        f"ATTENDEE:mailto:{appointment.student.email}",
        f"ATTENDEE:mailto:{advisor.email}",
        f"SEQUENCE:{1 if method == 'CANCEL' else 0}",
    ]
    if method == "CANCEL":
        lines.append("STATUS:CANCELLED")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"
```

Add to `backend/config/settings.py` (near the bottom):

```python
DEFAULT_FROM_EMAIL = os.environ.get("THRIVE_FROM_EMAIL", "thrive-noreply@rady.ucsd.edu")
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive backend/config
git commit -m "feat(backend): RFC 5545 ICS builder for appointment invites"
```

---

### Task 7: Zoom client behind an interface

**Files:**
- Create: `backend/rsm_thrive/services/zoom.py`
- Modify: `backend/pyproject.toml` (add `"requests>=2.32"` to `[project] dependencies`; run `uv sync`)
- Test: `backend/rsm_thrive/tests/test_zoom.py`

**Interfaces:**
- Produces:
  - `class ZoomError(Exception)`
  - `class FakeZoomClient` with `create_meeting(topic: str, start, duration_minutes: int) -> str` returning `f"https://ucsd.zoom.us/j/fake-{abs(hash(topic)) % 10**9}"` — deterministic per topic, records calls in `self.calls` list.
  - `class ServerToServerZoomClient(account_id, client_id, client_secret)` — same method; POSTs `https://zoom.us/oauth/token` (`grant_type=account_credentials`, HTTP basic auth client_id/client_secret) then `https://api.zoom.us/v2/users/me/meetings` (json: topic, type 2, start_time ISO UTC, duration, timezone "UTC"); returns `join_url`; wraps any requests/HTTP failure in `ZoomError`. Network code lives only here; no test may hit the network.
  - `get_zoom_client()` — reads `THRIVE_ZOOM_ACCOUNT_ID`, `THRIVE_ZOOM_CLIENT_ID`, `THRIVE_ZOOM_CLIENT_SECRET` from `os.environ`; returns a `ServerToServerZoomClient` when all three are set, else `None`.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_zoom.py`:

```python
import datetime as dt

from rsm_thrive.services.zoom import (
    FakeZoomClient, ServerToServerZoomClient, get_zoom_client,
)


def test_fake_client_is_deterministic_and_records():
    fake = FakeZoomClient()
    url1 = fake.create_meeting("Advising", dt.datetime(2026, 9, 1, 16,
                                                       tzinfo=dt.timezone.utc), 30)
    url2 = fake.create_meeting("Advising", dt.datetime(2026, 9, 2, 16,
                                                       tzinfo=dt.timezone.utc), 30)
    assert url1 == url2 and url1.startswith("https://ucsd.zoom.us/j/fake-")
    assert len(fake.calls) == 2


def test_get_zoom_client_env_selection(monkeypatch):
    for var in ("THRIVE_ZOOM_ACCOUNT_ID", "THRIVE_ZOOM_CLIENT_ID",
                "THRIVE_ZOOM_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert get_zoom_client() is None
    monkeypatch.setenv("THRIVE_ZOOM_ACCOUNT_ID", "acc")
    monkeypatch.setenv("THRIVE_ZOOM_CLIENT_ID", "cid")
    monkeypatch.setenv("THRIVE_ZOOM_CLIENT_SECRET", "sec")
    client = get_zoom_client()
    assert isinstance(client, ServerToServerZoomClient)


def test_real_client_wraps_failures(monkeypatch):
    import requests
    def boom(*a, **kw):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("requests.post", boom)
    client = ServerToServerZoomClient("acc", "cid", "sec")
    import pytest
    from rsm_thrive.services.zoom import ZoomError
    with pytest.raises(ZoomError):
        client.create_meeting("t", __import__("datetime").datetime(
            2026, 9, 1, tzinfo=__import__("datetime").timezone.utc), 30)
```

- [ ] **Step 2: Run to verify failure** — Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/services/zoom.py`:

```python
"""Zoom meeting creation. Real client uses Server-to-Server OAuth; the fake
is for tests and for environments without credentials (VINCENT-ASKS #8)."""
import datetime as dt
import os

import requests


class ZoomError(Exception):
    pass


class FakeZoomClient:
    def __init__(self):
        self.calls = []

    def create_meeting(self, topic: str, start: dt.datetime,
                       duration_minutes: int) -> str:
        self.calls.append((topic, start, duration_minutes))
        return f"https://ucsd.zoom.us/j/fake-{abs(hash(topic)) % 10**9}"


class ServerToServerZoomClient:
    def __init__(self, account_id: str, client_id: str, client_secret: str):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret

    def _token(self) -> str:
        resp = requests.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials",
                    "account_id": self.account_id},
            auth=(self.client_id, self.client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def create_meeting(self, topic: str, start: dt.datetime,
                       duration_minutes: int) -> str:
        try:
            token = self._token()
            resp = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "topic": topic,
                    "type": 2,
                    "start_time": start.astimezone(dt.timezone.utc)
                                       .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "duration": duration_minutes,
                    "timezone": "UTC",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["join_url"]
        except requests.RequestException as exc:
            raise ZoomError(str(exc)) from exc


def get_zoom_client():
    account_id = os.environ.get("THRIVE_ZOOM_ACCOUNT_ID")
    client_id = os.environ.get("THRIVE_ZOOM_CLIENT_ID")
    client_secret = os.environ.get("THRIVE_ZOOM_CLIENT_SECRET")
    if account_id and client_id and client_secret:
        return ServerToServerZoomClient(account_id, client_id, client_secret)
    return None
```

- [ ] **Step 4: uv sync + run tests** — `uv sync && uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat(backend): Zoom client interface with S2S OAuth and fake"
```

---

### Task 8: Notification dispatch + wiring into book/cancel

**Files:**
- Create: `backend/rsm_thrive/services/notifications.py`
- Modify: `backend/rsm_thrive/views/appointments.py`
- Test: `backend/rsm_thrive/tests/test_notifications.py`

**Interfaces:**
- Consumes: `build_ics` (Task 6), `get_zoom_client`/`ZoomError` (Task 7), `AppointmentNotification` (Task 1).
- Produces in `services/notifications.py`:
  - `dispatch_booking_side_effects(appointment) -> None` — step 1: if `slot.mode == "zoom"`: `client = get_zoom_client()`; None → record kind `zoom` status `skipped` detail `"no zoom credentials configured"`; else create meeting (topic `f"THRIVE advising: {advisor.name}"`, slot start, duration from slot span), save `zoom_join_url` on the appointment, record `sent` with the URL in detail; `ZoomError` → record `failed` with the message. Step 2: send REQUEST email (subject `f"THRIVE: appointment confirmed — {advisor.name}"`, to student + advisor, body 2 lines with local time + reason, attach `("invite.ics", build_ics(appointment, "REQUEST"), 'text/calendar; method=REQUEST; charset=UTF-8')`), record kind `email_request` sent/failed. Every step in its own try/except; **the function never raises**.
  - `dispatch_cancel_side_effects(appointment) -> None` — CANCEL email only (subject `f"THRIVE: appointment cancelled — {advisor.name}"`, ICS with method CANCEL), kind `email_cancel`.
- Wiring: `book_appointment` calls `dispatch_booking_side_effects(appointment)` after create (response includes any zoom URL implicitly next fetch — response payload unchanged); `cancel_appointment` calls `dispatch_cancel_side_effects` ONLY when the status actually flipped (idempotent re-cancels fire nothing).

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_notifications.py`:

```python
import json
from unittest.mock import patch

import pytest
from django.core import mail

from rsm_thrive.models import Appointment, AppointmentNotification
from rsm_thrive.services.zoom import FakeZoomClient, ZoomError
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def _book(client, slot):
    return client.post("/api/thrive/appointments",
                       data=json.dumps({"slotId": slot.id, "reason": "r"}),
                       content_type="application/json")


def test_booking_fires_zoom_and_email(client):
    me = make_student()
    adv = make_advisor(email="casey@ucsd.edu")
    slot = make_slot(adv, mode="zoom")
    client.force_login(me.user)
    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=FakeZoomClient()):
        assert _book(client, slot).status_code == 201

    appt = Appointment.objects.get()
    assert appt.zoom_join_url.startswith("https://ucsd.zoom.us/j/fake-")
    kinds = {n.kind: n.status for n in appt.notifications.all()}
    assert kinds == {"zoom": "sent", "email_request": "sent"}
    [msg] = mail.outbox
    assert msg.subject == f"THRIVE: appointment confirmed — {adv.name}"
    assert set(msg.to) == {"ada@ucsd.edu", "casey@ucsd.edu"}
    name, content, mimetype = msg.attachments[0]
    assert name == "invite.ics" and "METHOD:REQUEST" in content
    assert mimetype.startswith("text/calendar")


def test_zoom_missing_credentials_is_skipped_not_fatal(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    client.force_login(me.user)
    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=None):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    assert appt.notifications.get(kind="zoom").status == "skipped"
    assert appt.notifications.get(kind="email_request").status == "sent"


def test_zoom_failure_recorded_booking_survives(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    client.force_login(me.user)

    class BoomClient:
        def create_meeting(self, *a, **kw):
            raise ZoomError("zoom down")

    with patch("rsm_thrive.services.notifications.get_zoom_client",
               return_value=BoomClient()):
        assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    zoom_row = appt.notifications.get(kind="zoom")
    assert zoom_row.status == "failed" and "zoom down" in zoom_row.detail


def test_in_person_booking_skips_zoom_entirely(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="in person")
    client.force_login(me.user)
    assert _book(client, slot).status_code == 201
    appt = Appointment.objects.get()
    assert not appt.notifications.filter(kind="zoom").exists()
    assert appt.notifications.get(kind="email_request").status == "sent"


def test_cancel_fires_cancel_email_once(client):
    me = make_student()
    adv = make_advisor()
    slot = make_slot(adv, mode="in person")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    client.force_login(me.user)
    client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")
    client.post(f"/api/thrive/appointments/appt-{appt.pk}/cancel")  # idempotent
    assert appt.notifications.filter(kind="email_cancel").count() == 1
    [msg] = mail.outbox
    assert "cancelled" in msg.subject
    assert "METHOD:CANCEL" in msg.attachments[0][1]
```

- [ ] **Step 2: Run to verify failure** — Expected: `ModuleNotFoundError` / missing notifications.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/services/notifications.py`:

```python
"""Appointment side effects: Zoom + ICS emails, audited, never fatal.

Runs in-request for now; when the Celery queue exists on the server (F5),
each dispatch_* becomes a task body and the call sites gain .delay().
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from rsm_thrive.models import AppointmentNotification
from rsm_thrive.services.ics import build_ics
from rsm_thrive.services.zoom import ZoomError, get_zoom_client

logger = logging.getLogger(__name__)


def _record(appointment, kind, status, detail=""):
    AppointmentNotification.objects.create(
        appointment=appointment, kind=kind, status=status, detail=detail[:2000],
    )


def _send_invite(appointment, method, kind):
    slot = appointment.slot
    advisor = slot.advisor
    verb = "confirmed" if method == "REQUEST" else "cancelled"
    local = timezone.localtime(slot.start).strftime("%A %b %-d, %-I:%M %p")
    try:
        message = EmailMessage(
            subject=f"THRIVE: appointment {verb} — {advisor.name}",
            body=(f"Your appointment with {advisor.name} on {local} is {verb}.\n"
                  f"Reason: {appointment.reason}\n"),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[appointment.student.email, advisor.email],
        )
        message.attach("invite.ics", build_ics(appointment, method),
                       f"text/calendar; method={method}; charset=UTF-8")
        message.send()
        _record(appointment, kind, "sent")
    except Exception as exc:  # audited, never fatal
        logger.exception("appointment email failed")
        _record(appointment, kind, "failed", str(exc))


def _create_zoom(appointment):
    slot = appointment.slot
    client = get_zoom_client()
    if client is None:
        _record(appointment, "zoom", "skipped", "no zoom credentials configured")
        return
    duration = max(1, int((slot.end - slot.start).total_seconds() // 60))
    try:
        url = client.create_meeting(
            f"THRIVE advising: {slot.advisor.name}", slot.start, duration)
        appointment.zoom_join_url = url
        appointment.save(update_fields=["zoom_join_url"])
        _record(appointment, "zoom", "sent", url)
    except ZoomError as exc:
        _record(appointment, "zoom", "failed", str(exc))


def dispatch_booking_side_effects(appointment) -> None:
    if appointment.slot.mode == "zoom":
        _create_zoom(appointment)
    _send_invite(appointment, "REQUEST", "email_request")


def dispatch_cancel_side_effects(appointment) -> None:
    _send_invite(appointment, "CANCEL", "email_cancel")
```

Wire into `views/appointments.py`: after the successful `create` in `book_appointment`, add `dispatch_booking_side_effects(appointment)`; in `cancel_appointment`, move the dispatch inside the `if appointment.status != "cancelled":` block after `save`, i.e. only when the flip happened. Import both at top.

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): audited zoom+ICS email side effects on book/cancel"
```

---

### Task 9: retry_notifications management command

**Files:**
- Create: `backend/rsm_thrive/management/commands/retry_notifications.py`
- Test: `backend/rsm_thrive/tests/test_retry_notifications.py`

**Interfaces:**
- Produces: `manage.py retry_notifications` — for each `AppointmentNotification` with `status="failed"` whose appointment is still `confirmed` (or kind `email_cancel` regardless): re-run just that step (`zoom` → `_create_zoom`, `email_request`/`email_cancel` → `_send_invite`), then update the ORIGINAL row: increment `attempts`, set status/detail from the retry outcome, and delete the duplicate row the service `_record` call just created (simplest: capture rows before/after by pk). Prints `retried <n>: <sent>/<failed>` summary.

- [ ] **Step 1: Write the failing test**

`backend/rsm_thrive/tests/test_retry_notifications.py`:

```python
from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.management import call_command

from rsm_thrive.models import Appointment, AppointmentNotification
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_retry_failed_email_succeeds_and_updates_row(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="in person")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    row = AppointmentNotification.objects.create(
        appointment=appt, kind="email_request", status="failed", detail="smtp down")

    out = StringIO()
    call_command("retry_notifications", stdout=out)

    row.refresh_from_db()
    assert row.status == "sent" and row.attempts == 2
    assert AppointmentNotification.objects.count() == 1  # no duplicate rows
    assert len(mail.outbox) == 1
    assert "retried 1" in out.getvalue()


def test_retry_skips_sent_and_skipped_rows(client):
    me = make_student()
    slot = make_slot(make_advisor(), mode="zoom")
    appt = Appointment.objects.create(slot=slot, student=me.user, reason="r")
    AppointmentNotification.objects.create(appointment=appt, kind="zoom",
                                           status="skipped", detail="no creds")
    out = StringIO()
    call_command("retry_notifications", stdout=out)
    assert "retried 0" in out.getvalue()
    assert len(mail.outbox) == 0
```

- [ ] **Step 2: Run to verify failure** — Expected: unknown command.

- [ ] **Step 3: Implement**

`backend/rsm_thrive/management/commands/retry_notifications.py`:

```python
from django.core.management.base import BaseCommand

from rsm_thrive.models import AppointmentNotification
from rsm_thrive.services import notifications as svc


class Command(BaseCommand):
    help = "Retry failed appointment notifications (zoom / invite emails)."

    def handle(self, *args, **options):
        failed = list(AppointmentNotification.objects.filter(status="failed"))
        sent = 0
        for row in failed:
            appointment = row.appointment
            if row.kind != "email_cancel" and appointment.status != "confirmed":
                continue
            before = set(appointment.notifications.values_list("pk", flat=True))
            if row.kind == "zoom":
                svc._create_zoom(appointment)
            elif row.kind == "email_request":
                svc._send_invite(appointment, "REQUEST", "email_request")
            else:
                svc._send_invite(appointment, "CANCEL", "email_cancel")
            new = appointment.notifications.exclude(pk__in=before).first()
            if new is not None:
                row.status, row.detail = new.status, new.detail
                row.attempts += 1
                row.save(update_fields=["status", "detail", "attempts", "updated_at"])
                new.delete()
                if row.status == "sent":
                    sent += 1
        self.stdout.write(f"retried {len(failed)}: {sent} sent, "
                          f"{len(failed) - sent} still failed/skipped")
```

- [ ] **Step 4: Run tests** — `uv run pytest -v`, all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "feat(backend): retry_notifications management command"
```

---

### Task 10: Contract schemas + seed_demo advisors

**Files:**
- Modify: `backend/rsm_thrive/tests/contract/schemas.py`, `backend/rsm_thrive/tests/contract/test_contract.py`, `backend/rsm_thrive/management/commands/seed_demo.py`

**Interfaces:**
- Consumes: everything above; the existing contract-suite `world` fixture and CASES table.
- Produces: schemas `ADVISOR`, `APPOINTMENT_SLOT`, `APPOINTMENT` transcribed from `frontend/src/lib/data/types.ts` (`Advisor`: required id,name,role,service,location, optional avatar/blurb; `AppointmentSlot`: all 6 required, `mode` enum `["in person", "zoom"]`; `Appointment`: all 9 required, `status` enum `["confirmed", "cancelled"]`) — `additionalProperties: false`, service enum `["advising", "career"]`. Contract CASES gain: `/api/thrive/advisors` (list), `/api/thrive/advisors/adv-c1/slots` (list), `/api/thrive/appointments` (list). The `world` fixture books one appointment through `Appointment.objects.create` so the appointments list is non-empty and one slot reads unavailable. `seed_demo` adds two advisors (`demo-adv-gsa` service advising, `demo-adv-cmc` service career, distinct emails) with 3 future slots each.

- [ ] **Step 1: Extend the world fixture and CASES (failing)**

In `tests/contract/test_contract.py`, add to imports `make_advisor, make_slot`; extend the `world` fixture (before `client.force_login`):

```python
    adv = make_advisor(id="adv-c1", blurb="Ask me anything",
                       avatar_url="https://rady.ucsd.edu/a.png")
    slot_a = make_slot(adv)
    make_slot(adv, mode="in person")
    from rsm_thrive.models import Appointment
    Appointment.objects.create(slot=slot_a, student=profile.user, reason="contract")
```

Add to CASES:

```python
    ("/api/thrive/advisors", schemas.ADVISOR, True),
    ("/api/thrive/advisors/adv-c1/slots", schemas.APPOINTMENT_SLOT, True),
    ("/api/thrive/appointments", schemas.APPOINTMENT, True),
```

Run: `uv run pytest rsm_thrive/tests/contract -v` — Expected: FAIL (`AttributeError: ADVISOR`).

- [ ] **Step 2: Write the three schemas**

Append to `tests/contract/schemas.py`:

```python
SERVICE = {"enum": ["advising", "career"]}
MEETING_MODE = {"enum": ["in person", "zoom"]}

ADVISOR = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "name", "role", "service", "location"],
    "properties": {
        "id": {"type": "string"}, "name": {"type": "string"},
        "role": {"type": "string"}, "service": SERVICE,
        "avatar": {"type": "string"}, "location": {"type": "string"},
        "blurb": {"type": "string"},
    },
}

APPOINTMENT_SLOT = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "advisorId", "start", "end", "mode", "available"],
    "properties": {
        "id": {"type": "string"}, "advisorId": {"type": "string"},
        "start": ISO_INSTANT, "end": ISO_INSTANT,
        "mode": MEETING_MODE, "available": {"type": "boolean"},
    },
}

APPOINTMENT = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "advisorId", "studentId", "slotId", "start", "end",
                 "mode", "reason", "status"],
    "properties": {
        "id": {"type": "string"}, "advisorId": {"type": "string"},
        "studentId": {"type": "string"}, "slotId": {"type": "string"},
        "start": ISO_INSTANT, "end": ISO_INSTANT, "mode": MEETING_MODE,
        "reason": {"type": "string"},
        "status": {"enum": ["confirmed", "cancelled"]},
    },
}
```

- [ ] **Step 3: Extend seed_demo**

In `seed_demo.py` `handle`, before the success write:

```python
        gsa = t.make_advisor(id="demo-adv-gsa", name="Gail Advisor",
                             service="advising", email="gsa-demo@ucsd.edu")
        cmc = t.make_advisor(id="demo-adv-cmc", name="Cam Coach", service="career",
                             role="Career Coach", location="CMC office / Zoom",
                             email="cmc-demo@ucsd.edu")
        for adv in (gsa, cmc):
            for d in (3, 4, 5):
                t.make_slot(adv, start=timezone.now() + dt.timedelta(days=d))
```

- [ ] **Step 4: Run everything**

Run: `uv run pytest -v && uv run python manage.py migrate && uv run python manage.py seed_demo`
Expected: full suite PASSES (13 contract cases); seed still idempotent.

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive
git commit -m "test(backend): appointment contract schemas and demo advisors"
```

---

## Plan Self-Review (completed at authoring)

- **Spec coverage:** §3.3 transactions (Task 1, 4, 5), §3.5 booking flow steps 1–3 (Tasks 4, 6, 7, 8 — step 4 calendar-API sync is explicitly v2), §4 appointment endpoints incl. the 409 machine-code contract (Tasks 2–5), notification audit + retry (Tasks 8–9), contract layer (Task 10). Deliberate deviation from spec §3.5: side effects run in-request behind `dispatch_*` functions instead of Celery — the queue only exists on the server; function shape keeps the Celery move mechanical (noted in Task 8's module docstring). `AdvisorTeam` from spec §3.3 is folded into `Advisor.service` (the contract's `AdvisingService` already encodes CMC=career/GSA=advising; a separate table adds nothing yet — YAGNI).
- **Placeholder scan:** none — every task carries complete code and tests.
- **Type consistency:** `appointment_payload`, `advisor_payload`, `slot_payload`, `dispatch_booking_side_effects`, `dispatch_cancel_side_effects`, `get_zoom_client`, `build_ics(appointment, method)`, factory signatures (`make_advisor(id=None, **overrides)`, `make_slot(advisor, start=None, **overrides)`) used identically across Tasks 1–10; error codes (`slot_unknown`, `slot_unavailable`, `unknown_appointment`, `unknown_advisor`) consistent between Tasks 4, 5 and their tests.
