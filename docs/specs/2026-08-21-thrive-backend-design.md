# THRIVE Backend — Design Specification

**Date:** 2026-08-21
**Status:** Approved in discussion; pending final review of this document
**Owner:** Shankar Deenadayalan (sdeenadayalan)

---

## 1. What we are building

A production backend for the THRIVE SvelteKit frontend (github.com/rsm-msaad/thrive — **read-only for us; never push to it**), deployed on the Rady Mac Studio (`ms-macos.tail37260b.ts.net`) inside the existing `rsm-msba-brain` Django platform.

The product pieces:

1. **FAQ chatbot** — answers MSBA program/policy questions from a curated + scraped document corpus (RAG).
2. **Electives recommender chatbot** — takes a career goal ("data scientist") and recommends electives via a deterministic scoring engine, explained conversationally by an LLM.
3. **Job-search tab** — new left-nav surface: upload resume, search jobs, get a ranked suitability assessment per job.
4. **Foundation** — real auth (UCSD AD), per-student data isolation, Canvas-fed academic data, and real appointment booking (CMC + GSA advisors) with Zoom meetings and calendar-invite emails.

### Design stance

- **Keep the contract, own the rest.** The frontend's 27 provider function signatures, domain types (`frontend/src/lib/data/types.ts`), ISO-8601 date rules, sort guarantees, and error semantics are honored exactly. Everything behind that seam — models, endpoints, services, pipelines — is our own design. `BACKEND.md`'s prescriptions beyond the contract are not binding.
- The contract is functions, not HTTP ("how they map onto HTTP is yours to choose" — BACKEND.md §1). We choose a resource-shaped REST JSON API.
- Frontend must run as a Node server (all routes are SSR by design; no static build exists).

### Repo strategy

A **new repo owned by the user** is the single source of truth:

```
<new-repo>/
├── frontend/   copied from thrive, then patched (base path, hooks, provider bodies)
├── backend/    Django component `rsm-django-thrive` + deploy scripts
└── docs/       this spec, runbooks
```

- The original `thrive` repo is never pushed to (local clone has push URL disabled).
- Deployment pulls from the new repo. The Django component is synced/installed into the platform checkout (`/srv/django/rsm-guild-ai-brain`, branch `feat/msba-brain`) — exact mechanism (symlink / pip path-install / mirrored push) to be confirmed with Vincent.

### Build order (agreed)

Overall architecture designed up front (this document); implementation phased:

1. **Phase F — Foundation**: auth flow, models, the 27-provider API, Canvas ingestion, appointments (Zoom + ICS email).
2. **Phase C — Chatbots**: chat write path, RAG pipeline, electives engine, eval harness.
3. **Phase J — Job search**: ingestion pipeline, resume parsing, two-stage ranking, new UI tab.
4. **Phase L — Long tail**: consent enforcement, group projects (not designed here; own cycle later).

---

## 2. Identity & request flow

**Topology.** Fleet Caddy routes `/msba-brain/thrive/*` → SvelteKit Node process on `127.0.0.1:8037`. Everything else under `/msba-brain/` continues to the existing Django site (gunicorn on `127.0.0.1:8036`).

**Login is Django's.** No login UI of ours. New `frontend/src/hooks.server.ts`:

1. Read the browser's Django session cookie.
2. `GET /msba-brain/api/thrive/me` (server-to-server, `127.0.0.1:8036`).
3. Valid → store identity in `event.locals`; invalid/absent → redirect to Django login with `?next=` back to THRIVE.

Django users must pre-exist (platform LDAP backend never creates users) → seed the cohort's AD usernames up front.

**Identity threading without breaking the contract.** Provider signatures have no user parameter and are not changed. The hook opens a per-request `AsyncLocalStorage` context carrying `{student, sessionCookie, csrfToken}`; provider bodies read it ambiently. UI untouched.

**Server-to-server calls.** Provider bodies `fetch()` Django directly at `127.0.0.1:8036`, forwarding the session cookie (+ CSRF token on writes). Django enforces auth on every call — the Node layer is never trusted (closes MIGRATION.md §9 defect 2: unauthenticated direct POST).

**Frontend fork patches (mechanical, from the repo audit):**

- Add `kit.paths.base = '/msba-brain/thrive'` (no `svelte.config.js` exists today; config is inline in `vite.config.ts`).
- Fix `lib/nav.ts` literal-href comparisons (`isActiveRoute`, `isKnownRoute`, `allNav`) and the ~11 hard-coded root hrefs across shell/home/appointments components.
- Fix `routes/ask/+page.server.ts` hard-coded `redirect(307, '/ask/…')`.
- Set `ORIGIN=https://ms-macos.tail37260b.ts.net` (or `PROTOCOL_HEADER`/`HOST_HEADER`) for the adapter-node CSRF origin check — otherwise every form POST 403s silently. Never disable `checkOrigin`.

---

## 3. Data model (Postgres — existing `msba_brain_db`)

All tables namespaced under the `rsm_thrive` Django app, keyed to Django `User`.

### 3.1 Shared academic truth (no student FK; written by ingestion)

`Course`, `CourseMeeting`, `Syllabus`, `Assignment`, `Event`, `ResourceLink`, `Advisor`, `AdvisorTeam` (CMC | GSA), `AppointmentSlot`. `StudentProfile` extends `User`: programStart, track, `StudentConsent` flags, encrypted per-student Canvas token (optional).

**Canvas is the source for academic data.** Celery jobs upsert Courses/Assignments/course Events from the Canvas REST API. Dedup key: Canvas object IDs (fits the existing "raw event id" key space). Credential paths: (a) institutional/service-account API access (preferred; requires an ask to IT), (b) per-student Canvas access token or per-user ICS feed URL, stored encrypted — works day one with nobody's permission. Design supports (b) now, upgrades to (a). Audit `rsm-django-canvas` component first — it may already implement this.

### 3.2 Per-student overlay — sparse override pattern

Overrides record **only what the student personally changed; absent = use source value** (BACKEND.md §7, preserved exactly):

- `TaskOverride` — nullable done/title/priority/dueDate/order; row exists only if edited; nullable `done` expresses "unticked a task that ships done".
- `StudentTask` (self-added), `TaskNote`, `IgnoredEvent`, `EventJoin`, `CalendarPrefs`.

Keyed on the three existing ID spaces (task id, calendar item id, raw event id). **No fourth ID space.** These tables replace the seven `localStorage` groups; the frontend stores are patched to read/write the new endpoints with identical semantics.

### 3.3 Transactions

- `Appointment` — FK slot + student; **DB unique constraint on slot** makes double-booking impossible at the database level. Cancel releases the slot.
- `AppointmentNotification` — audit row per outbound side effect (email sent, Zoom created), with status + retry; failures visible in admin, never silent.
- `CourseRequest` (+ TSS connection state), `ResumeVersion`, `Skill`.

### 3.4 Intelligence

- `Conversation`, `Message` — FK student; destination enum (faq | electives); `updatedAt` ordering matches `getConversations` contract.
- The frontend's third Ask destination (`career`) is retired in the fork: its tab is removed from `lib/ask.ts` and `/ask/career` redirects to the new job-search tab, so no dead chat surface ships.
- `Document`, `Chunk` — retrieval corpus with embeddings. **pgvector** extension (one `CREATE EXTENSION`, needs Vincent). Fallback if declined: corpus is small (hundreds of chunks) → brute-force cosine in Python.
- `JobSource`, `JobPosting` (dedup: source + external id; skills extracted at ingest; expiry), `ResumeDocument` (file + parsed text + LLM-extracted structured profile), `MatchReport` (cached per student × posting).

### 3.5 Appointments — real booking flow

On book:

1. Create `Appointment` (unique constraint guards the race; taken slot → 409).
2. Celery task calls **Zoom API** (Server-to-Server OAuth app; one-time admin creation on the UCSD Zoom account); join URL stored on the appointment.
3. **ICS email invite** (`METHOD:REQUEST`) sent to student and advisor — Gmail and Outlook both auto-place it on the calendar; Zoom link embedded. Cancellation sends `METHOD:CANCEL`.
4. Direct calendar-API sync (Google Calendar / Microsoft Graph) is a v2 behind a `CalendarNotifier` interface — swap touches one module.

Slot inventory: advisor availability rules generate `AppointmentSlot` rows. Email rides Django's email backend + campus SMTP (check `rsm-django-email` first).

---

## 4. API layer

JSON API under `/msba-brain/api/thrive/`, session-authenticated, resource-shaped:

| Provider(s) | Endpoint |
|---|---|
| getStudent | `GET /me` |
| getCourses / getSyllabi / getAssignments | `GET /courses` · `/syllabi` · `/assignments` |
| getTasks (overlay applied) | `GET /tasks` |
| getEvents | `GET /events` |
| getDegreeProgress / getProgramTimeline | `GET /degree/progress` · `/degree/timeline` |
| getResources | `GET /resources` |
| getAdvisors / getSlots / getMyAppointments | `GET /advisors` · `/advisors/{id}/slots` · `/appointments` |
| bookAppointment / cancelAppointment | `POST /appointments` · `POST /appointments/{id}/cancel` |
| course requests (6) | `GET/POST /requests…` |
| resume (5) | `GET/POST /resume…` |
| getConversations / getConversation | `GET /conversations` · `/conversations/{id}` |
| **new:** chat writes | `POST /conversations` · `POST /conversations/{id}/messages` |
| **new:** overlay writes | `PATCH /tasks/{id}/override`, ignore/join/prefs/notes endpoints |
| **new:** job search | `GET /jobs?q=…`, `POST /resume/upload`, `GET/POST /jobs/{id}/match` |

Rules enforced server-side, per contract:

- JSON keys camelCase, byte-for-byte match with `types.ts`; closed unions preserved verbatim (incl. `"11 month"`, `"in person"`, `"reduced load"`, `"out of major"`).
- Every date an ISO-8601 string (offset for instants, bare date for calendar dates); **Django never formats a date**; `CourseMeeting` times stay wall-clock `"HH:mm"`.
- Guaranteed sorts live in querysets: tasks done-last-then-due-asc, assignments due-asc, events future-only sorted by start, appointments confirmed-only start-asc, conversations updatedAt-desc.
- `[]` for empty; `null` for unknown-id lookups; the one sanctioned throw: booking a taken slot → `409` + machine code → provider raises `SlotUnavailableError` (existing UI copy keeps working).

Frontend fork: each provider body becomes a ~3-line call through one shared authenticated client (base URL, cookie forwarding, error translation in one place). All 27 implemented, including the 13 currently uncalled. The two SvelteKit form actions (`/appointments?/book`, `?/cancel`) keep their exact response shapes and error strings, now calling Django with an in-action auth check.

**Why REST over per-function RPC** (decided): the API outlives the seam (job tab, admin surface, Zoom callbacks want resource semantics); HTTP semantics do real work (cacheable GETs, self-describing 201/409, per-resource permissions, legible logs); drift is prevented more cheaply by contract tests than by URL mirroring.

---

## 5. Chatbots

### Shared chat spine

`POST /conversations` (create, tagged with destination) and `POST /conversations/{id}/messages`: persist student turn → run bot → persist assistant turn → return it. v1 synchronous (matches current UI); URL design admits SSE streaming later without moving endpoints. History per-student in Postgres.

**LLM access:** the platform's shared `ai_service` (`rsm-django-assessment/rsm_assessment/services/ai_service.py`) — multi-provider (OpenAI / Anthropic / Gemini / shared ChatGPT-OAuth default) with fallback chains ("rescue the turn instead of 500"). No new keys or billing; confirm usage pattern with Vincent. Fallback if unavailable: our own Gemini client (exists from the prior Rady Recommender project, with 503 retry + model fallback).

### FAQ bot — RAG with citations and a refusal rule

- Corpus: MSBA program handbook + policies, MGTA syllabus PDFs, scraped Rady/UCSD pages (Celery refresh), reused Rady Recommender assets.
- Ingestion: heading-aware chunking → embeddings → pgvector; scheduled refresh.
- Answering: embed query → top-k retrieve → LLM answers **only from retrieved context**, citing source documents. Thin retrieval → the bot says it doesn't know and points to advising. The refusal rule is in the prompt **and** asserted in evals (a confident wrong policy answer is worse than none).

### Electives recommender — deterministic engine, conversational shell

- LLM roles: extract the career goal from conversation; explain the results grounded in syllabus chunks.
- Recommendation itself: Python scoring engine — role→skills mapping (ported from Rady Recommender `careers.json`) × elective catalog (from syllabi), filtered by courses already taken (Canvas) and quarter offered. Same goal → same defensible ranking, reproducible in tests.

### Tunability (explicit requirement)

Prompts, retrieval params (top-k, thresholds), and model choice live in versioned config editable without deploys. **Eval harness from day one**: golden Q&A set (real questions, handbook-verified answers) runs on every prompt change; each turn logs retrieved chunk IDs so wrong answers are diagnosable in one look.

---

## 6. Job search & suitability ranking

- **Ingestion:** `JobSource` abstraction; implementations: aggregator API (Adzuna or JSearch/RapidAPI) for breadth + Greenhouse/Lever public JSON APIs for a curated list of companies MSBA grads join. Celery beat nightly: normalize → dedup (source + external id) → extract skill list per posting → expire stale rows.
- **Resume:** upload PDF/DOCX → parse text → LLM-extract structured profile (skills, experience, education) → store as current `ResumeVersion`.
- **Search + two-stage ranking:**
  - Stage 1 (instant, no LLM): Postgres full-text search over postings; whole result list ranked by embedding similarity (resume profile ↔ job description).
  - Stage 2 (on demand / top-10): LLM rubric scorer → `MatchReport`: competency level, matched skills, gaps, plain-English competitiveness verdict; cached.
- **"People who hold this job" signal, legally:** no LinkedIn scraping (ToS). Proxy: **role benchmark** = aggregated skill requirements across all ingested postings for that title ("what the market says this job needs"); ranking = resume × job description × role benchmark. Explainable, self-refreshing.
- **UI:** new left-nav tab in the fork (search page, ranked results, report view), following the repo's component conventions and design-token rules (no hardcoded colors — a repo test enforces this).

---

## 7. Deployment, ops, testing

### Deployment

- Django component `rsm-django-thrive` developed in the new repo, synced/installed into `/srv/django/rsm-guild-ai-brain` (branch `feat/msba-brain`) and wired into the `rsm-msba-brain` site (settings + urls).
- Frontend fork built with `adapter-node`; runs as **LaunchDaemon** `com.rsm.thrive.web` on `127.0.0.1:8037` with `ORIGIN` set (daemon, not agent — fleet convention, survives reboots).
- One new Caddy route: `/msba-brain/thrive/*` → `:8037`.
- Local dev: full stack on the laptop — Postgres (Docker) + Django + SvelteKit — nothing debugged first on the server. Verify live site from another machine (the Mac hairpins its own tailnet name).

### Depends on other people (front-load these asks)

| Ask | Who |
|---|---|
| Caddy route, LaunchDaemon install (sudo), `CREATE EXTENSION pgvector`, `ai_service` access, SMTP settings, component wiring preference | Vincent |
| Zoom Server-to-Server OAuth app | UCSD/Rady Zoom admin |
| Canvas institutional API access (else start per-student tokens) | IT / program |
| Job aggregator API key (free tier) | ourselves |

### Ops

- Celery: own `thrive` queue + beat schedule on the existing Redis (Canvas sync, scrapes, job ingest, embedding refresh).
- Secrets: platform `.env` owner-only pattern; per-student Canvas tokens encrypted at rest.
- Outbound side effects audited in `AppointmentNotification` with retry; admin-visible.
- Logs per fleet convention (`logs/*.err.log`); health via `launchctl list` + `status_all.sh`.

### Testing (four layers)

1. **Contract tests** — every endpoint's JSON validated against shapes generated from `types.ts`; drift fails CI, not production.
2. **Django unit tests** — sparse-override semantics (incl. untick-a-shipped-done-task), booking race vs unique constraint, ICS generation, ranking determinism.
3. **Bot evals** — golden Q&A harness on every prompt change; refusal rule asserted.
4. **Fork keeps the repo's six gates green** (unit suite, svelte-check at 0/0, build, contrast, layout, interaction) + the timezone sweep.

---

## 8. Out of scope (deliberately)

- Group projects and consent *enforcement* design (flags stored, not yet read) — own design cycle in Phase L.
- SSE streaming for chat (URL design admits it; not built in v1).
- Direct advisor calendar-API sync (v2 behind `CalendarNotifier`).
- Floating assistant widget (feature-flagged off in the frontend; unchanged).
- `/swatch` route removal and other frontend cleanups beyond integration patches.
