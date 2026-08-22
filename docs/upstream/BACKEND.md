# BACKEND

**The contract Django has to satisfy.** Written for an engineer who has never seen
this frontend, derived by reading `frontend/src/lib/data/` at commit `7d8b24e`
rather than from memory.

If something here disagrees with another doc in this repo, this file is the one
that was checked against the code. Known disagreements are listed at the end.

---

## 1. The shape of the thing

Every screen in this app gets its data from **one layer of 27 functions** in
`frontend/src/lib/data/providers.ts`. Nothing else reaches for data. Components
import from `$lib/data` and never from anything deeper.

Each function returns a `Promise`. Today the bodies read fixtures from
`frontend/src/lib/data/mock/`. **Django replaces the bodies. The signatures do not
move.** That is the whole design: because every caller already `await`s these, the
UI does not change when the backend arrives.

Three consequences worth being explicit about:

- **You are implementing functions, not endpoints.** How they map onto HTTP is
  yours to choose. The frontend only requires that `getTasks()` resolves to
  `Task[]`. One endpoint per provider is the obvious mapping and probably the right
  one, but nothing here depends on it.
- **Shaping belongs behind the seam.** Sorting, filtering and deriving that every
  caller would otherwise repeat is already done inside these functions, and should
  keep being done server-side. Examples are marked in the table below.
- **The current latency is deliberate.** Every provider resolves through a fixed
  120 ms delay (`mock/latency.ts`) so that missing loading states show up during
  development. Delete that when there is a real network; do not reproduce it.

### What is actually reached today

**14 of the 27 have a call site. 13 do not.** They are all implemented and tested,
but nothing in the UI calls them, because the surfaces that would are not built.
Marked **UNREACHED** in the table. Do not spend time on those first — and check
with the owner before spending time on them at all, because a provider with no
consumer has no one to say whether its shape is right.

---

## 2. Dates. Read this before writing a model.

**Every provider returns ISO-8601 strings. Django never formats a date for
display. Not once.**

Two field types, both aliases for `string`:

| Alias | Format | Example |
|---|---|---|
| `ISODateTime` | ISO-8601 instant | `"2026-08-11T09:00:00-07:00"` |
| `ISODate` | ISO-8601 calendar date | `"2026-08-11"` |

An offset is expected on `ISODateTime` — `Z` is fine, so is `-07:00`. What matters
is that it is unambiguous.

### Why no formatting

The frontend classifies and formats every date **server-side, in one place, from
one clock read.** A SvelteKit `load` function calls `new Date()` once and passes
the result into a pure classifier; components receive finished strings like
`"Overdue"`, `"in 3 days"`, `"2:30 PM"`. A component never sees an instant it has
to interpret.

This exists because of two failures that are invisible in normal use: a browser in
a different timezone from the server disagreeing about what "today" is, and a
client-computed date freezing in a tab left open overnight.

**So if Django sends `"Due tomorrow"` or `"Aug 11"`, that string is unusable.** It
cannot be reclassified, it cannot be compared, and it will be wrong for anyone in
another timezone. Send the instant.

### The consequence to expect, which is not a bug

The server decides what "today" is, so a deployment running in UTC will show a
different day than a viewer in California for the hours between UTC midnight and
local midnight. **That is the rule working, not a fault.** If it should follow the
viewer instead, that is a product decision about storing a per-student timezone
and reading it in the `load` — not a formatting change.

### Two things that are NOT dates

- `CourseMeeting.startTime` / `endTime` are **wall-clock strings, `"HH:mm"`, with
  no date and no timezone.** A recurring class is a weekday rule, not a series of
  instants, so it can be expanded onto any month client-side without a round trip.
  Keep them wall-clock.
- `ResumeExperience.period` is **free text** (`"Jun 2026 - present"`). It is
  displayed verbatim and never parsed.

---

## 3. The 27 providers

`R` = read, `W` = writes to a store. Purpose is one sentence; the rules that the
signature does not show are in §5.

### Student, courses, coursework

| | Signature | | Notes |
|---|---|---|---|
| R | `getStudent(): Promise<Student>` | ✅ | The signed-in student. One record. |
| R | `getCourses(): Promise<Course[]>` | ✅ | Current-term enrolment. |
| R | `getSyllabi(): Promise<Syllabus[]>` | **UNREACHED** | One per course. |
| R | `getAssignments(): Promise<Assignment[]>` | ✅ | **Sorted `dueDate` ascending.** |
| R | `getTasks(): Promise<Task[]>` | ✅ | **`done` sorts last, then `dueDate` ascending.** |
| R | `getEvents(): Promise<Event[]>` | ✅ | **Filters out anything finished**, then sorts by `start`. See §5. |
| R | `getDegreeProgress(): Promise<DegreeProgress>` | ✅ | Unit and requirement counts. |
| R | `getProgramTimeline(): Promise<ProgramTimeline>` | ✅ | **Fully derived** from `student.programStart` + `student.track`. See §5. |
| R | `getResources(): Promise<ResourceLink[]>` | **UNREACHED** | Campus support links. |

### Appointments — the only surface with writes today

| | Signature | | Notes |
|---|---|---|---|
| R | `getAdvisors(): Promise<Advisor[]>` | ✅ | Two today: one advising, one career. |
| R | `getSlots(advisorId: string): Promise<AppointmentSlot[]>` | ✅ | Published slots for one advisor, with claimed ones marked `available: false`. |
| R | `getMyAppointments(): Promise<Appointment[]>` | ✅ | **`status === "confirmed"` only**, sorted by `start`. Cancelled ones do not appear. |
| W | `bookAppointment(slotId: string, reason: string): Promise<Appointment>` | ✅ | Claims a slot. **Throws `SlotUnavailableError`** — see §5. |
| W | `cancelAppointment(appointmentId: string): Promise<Appointment \| null>` | ✅ | Sets `status: "cancelled"` and releases the slot **by `slotId`**. `null` for an unknown id. |

### Course action requests (TSS / EASy style) — entirely unreached

The whole feature is implemented behind the seam and reached by no UI.

| | Signature | | Notes |
|---|---|---|---|
| R | `getRequestPrefill(): Promise<CourseRequestPrefill>` | **UNREACHED** | Student context stamped onto a new request. Called internally by `createRequest`. |
| W | `createRequest(input: CourseRequestInput): Promise<CourseRequest>` | **UNREACHED** | Creates a `status: "draft"` record. |
| W | `submitRequest(requestId: string): Promise<CourseRequest \| null>` | **UNREACHED** | Draft → submitted. **Idempotent** — see §5. |
| R | `getMyRequests(): Promise<CourseRequest[]>` | **UNREACHED** | **Drafts first**, then newest `submittedAt` first. |
| R | `getTssConnection(): Promise<boolean>` | **UNREACHED** | Whether the record is "linked" to TSS. Simulated end to end. |
| W | `connectTss(): Promise<boolean>` | **UNREACHED** | Always resolves `true`. |

### Living resume — entirely unreached

| | Signature | | Notes |
|---|---|---|---|
| R | `getSkills(): Promise<Skill[]>` | **UNREACHED** | Skills, each carrying its origin course when derived. |
| R | `getResumeVersions(): Promise<ResumeVersion[]>` | **UNREACHED** | Newest `createdAt` first. |
| R | `getCurrentResume(): Promise<ResumeVersion \| null>` | **UNREACHED** | The one with `isCurrent`. |
| W | `generateNewVersion(): Promise<{ version: ResumeVersion; diff: ResumeDiff }>` | **UNREACHED** | Builds a version from current courses and skills, makes it current, returns what changed. |
| W | `setCurrentVersion(versionId: string): Promise<ResumeVersion \| null>` | **UNREACHED** | Restores an earlier version. **History is never deleted.** |

### Ask THRIVE

| | Signature | | Notes |
|---|---|---|---|
| R | `getConversations(): Promise<Conversation[]>` | ✅ | All saved conversations, **newest `updatedAt` first**. Not filtered by destination — the caller does that. |
| R | `getConversation(id: string): Promise<Conversation \| null>` | ✅ | One by id. `null`, not a throw, for an unknown id. |

**There is no write here yet, and that is the biggest gap in this document.**
Nothing creates or appends to a conversation, because there is no retrieval service
to produce an answer. When one exists it needs at least "start a conversation" and
"append a turn", and their shapes have not been designed. See §8.

### Not providers, but exported from the same barrel

- `SlotUnavailableError` — see §5.
- `requestTypeLabel`, `requestTypeHelp` (`data/labels.ts`) — presentation strings
  for the `CourseRequestType` union. Public because they are labels for a closed
  set, not data. Django does not supply them.

---

## 4. The domain types, in full

This is the schema the Django models have to satisfy. Copied from
`frontend/src/lib/data/types.ts`, which is one file on purpose.

**`?` means optional and genuinely absent, not empty-string.** The UI branches on
presence for several of these — see §5.

### Shared unions

```ts
type Standing        = "onTrack" | "watch" | "needsHelp";
type Track           = "11 month" | "17 month";
type Priority        = "low" | "medium" | "high";
type TaskSource      = "class" | "career" | "admin" | "event";
type AssignmentStatus = "not-started" | "in-progress" | "submitted" | "graded" | "late";
type EventType       = "rady" | "ucsd" | "sandiego" | "club" | "career";
type PhaseId         = "orientation" | "fall" | "winter" | "spring" | "summer" | "optional-fall";
type PhaseStatus     = "complete" | "current" | "upcoming";
type AdvisingService = "advising" | "career";
type MeetingMode     = "in person" | "zoom";
type AppointmentStatus = "confirmed" | "cancelled";
type CourseRequestType   = "enroll" | "drop" | "reduced load" | "out of major";
type CourseRequestStatus = "draft" | "submitted" | "approved" | "denied";
type SkillSource     = "course" | "manual";
type ResourceCategory = "academic" | "career" | "wellness" | "technical" | "administrative";
type AskDestination  = "resources" | "courses" | "career";
type ChatRole        = "student" | "thrive";
```

**These are CLOSED sets and the frontend relies on it.** `EventType` in particular
is load-bearing: the calendar derives "can this be ignored" from membership in
exactly that set. A value outside a union will not render — it will fall through a
lookup and produce a blank. Adding a member is a frontend change as well as a
backend one.

Note the two with spaces in them (`"11 month"`, `"reduced load"`, `"in person"`,
`"out of major"`). They are compared as literal strings. Do not normalise them to
snake_case on the way out.

### Student

```ts
interface StudentConsent {
  calendarRead: boolean;          // read the student's calendar. THRIVE never writes to it.
  lmsRead: boolean;               // read LMS/Canvas coursework
  careerRecommendations: boolean; // personalised career and event recommendations
  advisorSharing: boolean;        // share anonymised progress with advisors
}

interface Student {
  id: string;
  name: string;
  goal: string;              // the career being worked toward, e.g. "Data Scientist"
  track: Track;
  program: string;
  standingSummary: string;   // one-line plain-language summary
  standing: Standing;
  consent: StudentConsent;
  avatarUrl?: string;        // absent → the UI renders initials
  currentTerm: string;       // e.g. "Summer 2026"
  programStart: ISODate;     // the whole timeline is derived from this + track
}
```

`consent` is part of the model rather than an afterthought because this app reads
from a lot of systems. Nothing currently enforces it — see §8.

### Program timeline — fully derived, store none of it

```ts
interface ProgramPhase {
  id: PhaseId;
  label: string;   // "Fall Quarter"
  term: string;    // "Fall 2025"
  start: ISODate;
  end: ISODate;
  optional: boolean;      // true for phases outside the shorter track
  status: PhaseStatus;    // derived from today against the window
}

interface ProgramTimeline {
  phases: ProgramPhase[];
  currentPhaseId: PhaseId | null;  // null before the start or after the finish
  percentComplete: number;         // 0-100, today between start and end
  programStart: ISODate;
  programEnd: ISODate;             // end of the last phase this track requires
  expectedFinishTerm: string;      // e.g. "Summer 2026"
  track: Track;
}
```

**Every field here is computed from `programStart` and `track`.** Do not add a
stored completion date; there was one on `DegreeProgress` and it disagreed with
the derived value, which is recorded as a defect in `MIGRATION.md` §9.

### Courses and syllabi

```ts
interface CourseMeeting {
  dayOfWeek: number;   // 0 = Sunday … 6 = Saturday
  startTime: string;   // wall clock "HH:mm", no date, no timezone
  endTime: string;
  location: string;
}

interface NextAssignment { title: string; due: ISODateTime; }

interface Course {
  id: string;
  code: string;        // "MGT 142"
  title: string;
  instructor: string;
  schedule: CourseMeeting[];
  term: string;
  progress: number;    // 0-100
  standing: Standing;
  nextAssignment: NextAssignment;
  nudge?: string;      // short prompt, only when the course needs attention
  syllabusId: string;
  units: number;
  currentGrade?: string;
}

interface SyllabusGradeComponent { label: string; weight: number; }  // weight 0-100

interface Syllabus {
  id: string;
  courseId: string;
  description: string;
  gradeBreakdown: SyllabusGradeComponent[];
  policies: string[];
  officeHours: string;
  sourceUrl?: string;
  lastUpdated: ISODate;   // when THRIVE last read it from source
}
```

`nudge` is expected on **at most a course or two at a time** — the UI's comment is
"a nudge on everything is a nudge on nothing". If a rule produces one per course,
the design intent is lost even though nothing breaks.

### Work

```ts
interface Assignment {
  id: string;
  courseId: string;
  title: string;
  dueDate: ISODateTime;
  weight: number;          // share of the course grade, 0-100
  status: AssignmentStatus;
  grade?: string;          // populated once status is "graded"
  description?: string;
}

interface Subtask { id: string; title: string; done: boolean; }

interface Task {
  id: string;
  title: string;
  dueDate: ISODateTime;
  source: TaskSource;
  priority: Priority;
  done: boolean;
  subtasks: Subtask[];
  courseId?: string;
  courseCode?: string;   // cached for display so a row needs no second lookup
}
```

### Events

```ts
interface Event {
  id: string;
  title: string;
  type: EventType;
  start: ISODateTime;
  end?: ISODateTime;        // absent → treated as a marker at `start`
  location: string;
  description?: string;
  registerUrl?: string;
  relevantToGoal: boolean;  // scored behind the seam; the UI only renders the badge
}
```

`relevantToGoal` is a **server-side judgement**. The UI has no scoring logic and
should not acquire any.

### Degree progress

```ts
interface DegreeGap { id: string; label: string; detail: string; severity: Standing; }

interface DegreeProgress {
  unitsCompleted: number;
  unitsRequired: number;
  coreDone: number;
  coreRequired: number;
  electiveDone: number;
  electiveRequired: number;
  gaps: DegreeGap[];
  track: Track;
}
```

### Appointments

```ts
interface Advisor {
  id: string;
  name: string;
  role: string;              // job title
  service: AdvisingService;
  avatar?: string;
  location: string;          // "Rady 2S111", or something naming Zoom for remote
  blurb?: string;
}

interface AppointmentSlot {
  id: string;
  advisorId: string;
  start: ISODateTime;
  end: ISODateTime;
  mode: MeetingMode;
  available: boolean;   // false when taken. Taken slots STILL RETURN — see §5.
}

interface Appointment {
  id: string;
  advisorId: string;
  studentId: string;
  slotId: string;       // required. See §5.
  start: ISODateTime;
  end: ISODateTime;
  mode: MeetingMode;
  reason: string;
  status: AppointmentStatus;
}
```

`Advisor.location` is the **only** signal of whether an advisor works remotely —
there is no boolean. The UI substring-matches for "zoom" to pick an icon. If you
add a proper field, tell the frontend; if you do not, keep the convention.

### Course action requests

```ts
interface CourseRequest {
  id: string;
  type: CourseRequestType;
  course: string;                  // code and title, or a term-wide marker
  reason: string;
  status: CourseRequestStatus;
  submittedAt: ISODateTime | null; // null WHILE DRAFT. Explicitly nullable.
  prefill: CourseRequestPrefill;   // snapshot, not a live lookup
}

interface CourseRequestPrefill {
  studentName: string;
  program: string;
  track: Track;
  term: string;
  currentCourses: string[];   // "MGT 142 · Machine Learning" form
  currentUnits: number;
  unitsCompleted: number;
  unitsRequired: number;
}

interface CourseRequestInput { type: CourseRequestType; course: string; reason: string; }
```

`prefill` is deliberately **denormalised onto the request**: a submitted request
must show what was actually sent, not today's values. Do not replace it with a
join.

### Living resume

```ts
interface Skill { id: string; name: string; source: SkillSource; courseId?: string; }

interface ResumeExperience {
  id: string; title: string; organization: string;
  period: string;      // FREE TEXT, never parsed
  bullets: string[];
}

interface ResumeCourse { code: string; title: string; highlight: string; }

interface ResumeVersion {
  id: string;
  label: string;
  createdAt: ISODateTime;
  summary: string;
  skills: Skill[];
  courses: ResumeCourse[];
  experience: ResumeExperience[];
  isCurrent: boolean;   // exactly one version at a time
}

interface ResumeDiff { addedSkills: string[]; addedCourses: string[]; summaryChanged: boolean; }
```

`experience` is **student-authored and carries forward untouched** when a version
is regenerated. Everything else is rebuilt.

### Resources

```ts
interface ResourceLink {
  id: string; title: string; description: string;
  url: string; category: ResourceCategory;
  owner?: string;   // owning office, e.g. "Rady Career Management"
}
```

### Ask THRIVE

```ts
interface ChatMessage { id: string; role: ChatRole; body: string; sentAt: ISODateTime; }

interface Conversation {
  id: string;
  destination: AskDestination;
  title: string;          // short label for the history list
  messages: ChatMessage[];
  updatedAt: ISODateTime; // when the last message landed; drives list order
}
```

A conversation **belongs to a destination**, and the frontend enforces it: opening
a real conversation under the wrong destination is a 404, not a redirect. If the
backend ever lets one move between destinations, say so.

---

## 5. The rules a signature does not show

This is the most useful section in this document. None of it is visible in a type.

### Empty vs null vs throw

The layer is consistent about this and the frontend depends on it:

| Situation | Contract |
|---|---|
| A collection with nothing in it | **`[]`**. Never `null`, never omitted. |
| A single record looked up by an id that does not exist | **`null`**, not a throw. `cancelAppointment`, `submitRequest`, `getCurrentResume`, `setCurrentVersion`, `getConversation`. |
| A single record that always exists | The record. `getStudent`, `getDegreeProgress`, `getProgramTimeline`. |
| A write that cannot proceed because the world changed | **Throw.** Exactly one case: `bookAppointment`. |

**`null` means "no such thing", and the caller renders a 404 or an empty state.**
It never means "an error happened". If Django cannot answer because it is broken,
that is an exception, not a `null`.

### `SlotUnavailableError` — the one throw

```ts
class SlotUnavailableError extends Error {
  constructor(message = "That time was just taken. Pick another.")
}
```

`bookAppointment` throws it in **two distinct situations, with different
messages**, and the distinction matters:

| Cause | Message |
|---|---|
| The slot id does not resolve to a published slot | `"That time is no longer listed."` |
| The slot resolves but is already claimed | `"That time was just taken. Pick another."` (the default) |

The frontend catches it in a form action and returns HTTP **409** with the
message **passed straight through to the student**. That is deliberate: only the
data layer knows which of the two happened, and flattening them would tell someone
"another student took it" about a slot that never existed. So **these strings are
user-facing copy**, unusually for this codebase, and changing them changes what a
student reads.

Anything that is not a `SlotUnavailableError` is re-thrown and becomes a 500. Do
not use this class for "the database is down".

**Availability is re-checked at booking time, not trusted from the request.** The
page the student is looking at may have been rendered before somebody else took the
slot. Keep that check.

### Taken slots are still returned

`getSlots` returns claimed slots with `available: false` rather than omitting them.
The UI renders them struck through and disabled, because "10:30 is gone" tells a
student the shape of an advisor's day. **Filtering them out server-side would make
a busy morning look like an advisor who does not work mornings.**

### `getEvents` filters by time, server-side

It keeps events where `end ?? start >= now` and sorts by `start`. So an all-day
event stays listed until it ends rather than vanishing at lunchtime. **Keep this
filter in the query.** It is the one place a clock read lives behind the seam, and
that is correct — it is still one server-side answer to "what time is it".

### `submitRequest` is idempotent

A request that is not a `"draft"` comes back **unchanged** rather than being
re-stamped or rejected. A double-submitted form must not move an approved request
back to `"submitted"`.

### Callers never receive a stored object

Every provider returns copies. A caller holding a result must never see it change
underneath them when something else mutates. This is trivially true over HTTP and
is called out only so nobody reintroduces a shared-reference cache.

The copies are currently **shallow**, which is a known and tested gap: pushing onto
a nested array on a returned object can reach the store. Over HTTP it stops
mattering.

### Ids are opaque strings, and their shape is load-bearing in one place

`slot-<advisorId>-<dayIndex>-<timeIndex>`, and `bookAppointment` **parses it** to
find the advisor (`slotId.startsWith(\`slot-${advisor.id}-\`)`). That is a mock
implementation detail; with a real database you would look the slot up by primary
key and the format stops mattering. **Mentioned so you do not preserve the format
believing the frontend needs it. It does not.** Nothing in the UI parses a slot id.

Everything else — `apt-001`, `req-000`, `res-003`, `conv-001` — is opaque to the
frontend and can be a UUID.

### Sort order is part of the contract

Six providers sort, and callers do not re-sort. Changing an order changes the UI
silently: `getAssignments` (due ascending), `getTasks` (done last, then due),
`getEvents` (start ascending), `getMyAppointments` (start ascending),
`getMyRequests` (drafts first, then newest submitted), `getResumeVersions` (newest
created), `getConversations` (newest updated).

---

## 6. The three id key spaces

The frontend keys browser-persisted state on three id spaces and **inventing a
fourth has already caused two real bugs here** — both of the same kind, both
invisible for weeks, both recorded in `BUGS.md`.

| Space | Keyed on | Used by |
|---|---|---|
| **Task id** | the task's own id | six of the seven override stores |
| **Calendar item id** | `asg-12`, `apt-3`, `task-7`, `todo-x`, `custom-…`, `evt-evt-3-1` | labels and urgent flags |
| **Raw `Event.id`** | `evt-3-1`, stored verbatim | ignores and joins |

The failure mode both times was one surface writing under a transformed key and
another reading under the untransformed one. Each surface was self-consistent and
neither could see the other, so round-trip tests passed throughout.

**The test for whether a new store needs a new space is: is this a fact about the
EVENT, or about the ROW?** A join and an ignore are facts about an event. A label
is a fact about a row — which is what lets a student label a booked appointment
they do not own.

**Why a backend engineer should care:** when these move server-side (§7), the
identity you key each table on is this decision, made permanent. Ask before
introducing a fourth.

---

## 7. Browser-only today, must move server-side

All of this lives in `localStorage` and is therefore per-browser, not per-student.
The moment there are real accounts it is wrong.

| What | Where now | Note |
|---|---|---|
| Task edits — done, titles, priorities, due dates, order, self-added tasks | 7 `localStorage` keys | **Overrides, not whole truth.** See below. |
| Task notes | its own key | Not an override of anything. |
| Ignored events | `thrive:ignored-events` | Keyed on raw `Event.id`. |
| Event joins ("count me in") | `thrive:event-joins` | Same key space, deliberately. |
| Calendar labels and urgent flags | `thrive:calendar-*` | Keyed on calendar item id. |
| The scratch to-do list | `thrive:quick-list` | Student-authored, no server equivalent. |
| Calendar filter preferences | `thrive:calendar-prefs` | Arguably stays local. |

### The store shape you have to preserve

**Persisted state records only what the student personally changed, keyed by id,
with "absent" meaning "never touched, use the source value".**

This is not a detail. A bare set of "done task ids" **cannot express "I unticked a
task that ships as done"** — reload and it silently re-ticks itself. A write that
matches the source value **forgets** the override rather than storing it, so the
store only ever holds genuine divergence.

If Django stores these as plain values rather than overrides, that capability is
lost and the bug comes back.

### Chat history cannot be local at all

Already a provider (`getConversations`) precisely because `localStorage` was never
an option: conversations are large, they grow without bound, and a student opening
the app on a second laptop would find an empty history **indistinguishable from
never having asked anything**. A history that is complete on one machine and empty
on another is not a smaller feature, it is a misleading one.

There is no chat store in the browser and none should be added.

---

## 8. Does not exist. Needs designing, not porting.

Nothing below has a frontend shape to copy. These are design conversations.

### Authentication and identity

**There is none.** No login, no session, no cookie, no per-student anything.
`getStudent()` returns one hardcoded record and every visitor is that student.

Two specific consequences:

- **The form actions have no auth check and are reachable by direct POST.** The
  frontend's two actions (`?/book`, `?/cancel`) validate their input and nothing
  else. A comment at each says a real deployment must check the session *inside*
  the function — putting the check in the UI leaves it open. Recorded as
  `MIGRATION.md` §9 defect 2.
- **`StudentConsent` is modelled and unenforced.** The flags exist on the type and
  nothing reads them before fetching. Deciding where consent is checked — provider
  boundary, query layer, or per-integration — is part of this work.

### Per-user isolation

The three mock stores (appointments, requests, resume) are **module-scope objects
shared by every visitor to the process, and wiped on restart.** This is graded
**BLOCKING** in `MIGRATION.md` §9 defect 1 and inherited deliberately: it is what
Django replaces.

Today that means two people using the deployed site book over each other and see
each other's appointments, and a serverless cold start silently empties everyone's
list. **This is the single most important thing the backend fixes.**

### Group projects

Scoped, not built, and the first surface that is **shared between people by
definition** rather than being one student's private view. Everything above is "one
student's data"; this is not, and none of the existing patterns cover it.

### A retrieval service behind Ask THRIVE

Three destinations exist as shells: Resources (program material), Course
Recommender, Career. The chat window renders saved conversations and answers a new
question with a fixed line saying it cannot answer yet.

**What is undesigned:** how a conversation is created and appended to. There is no
write provider, and the read shapes were built around fixtures rather than around
a real service's response. Streaming, citations and partial responses are all
unaddressed. Expect these two providers to change shape — they are the least
settled thing in this document.

---

## 9. Where this contradicts another doc

Checked against the code at `7d8b24e`:

- **"25 providers" appears in `MIGRATION.md` §2, `CONTEXT.md`, `README.md` and
  `CODEMAP.md`. There are 27.** `getConversations` and `getConversation` were added
  for Ask THRIVE. The number was right when written; the seam is allowed to widen.
- **`MIGRATION.md` §2 says `cancelAppointment` releases a slot by matching start
  times.** It does not, and has not since Phase 5 — it releases by `slotId`, which
  is why that field exists. The old behaviour is `MIGRATION.md` §9 defect 8, and
  §2 was written before the fix.
- **`MIGRATION.md` §2 calls `buildSlotsFor`'s availability "deterministic".** The
  ids and the hash are; `available` also depends on whether a slot is in the past,
  which reads the clock. Corrected in the code's own comment. Only matters for
  writing tests against it.
- **`MIGRATION.md` §9 defect 9 warns about a stale `DegreeProgress.expectedCompletion`.**
  That field has been removed. Read `ProgramTimeline.expectedFinishTerm`.

`MIGRATION.md` documents the **frozen Next.js prototype**, not this repo. Where it
disagrees with this file about the current tree, this file was checked.

---

## 10. Things I could not describe confidently

Stated rather than guessed:

- **How `relevantToGoal` should be scored.** The type says a boolean is computed
  behind the seam; the fixture sets it by hand. There is no rule to port.
- **What `Course.progress` measures.** 0-100 and documented as "completion of the
  course itself", but not whether that is time elapsed, assignments graded, or
  something the registrar supplies.
- **Whether `getSyllabi` should be per-course or bulk.** It returns all of them and
  has no caller, so no consumer has ever expressed a preference.
- **`CourseRequest.course` is a formatted string** (`"MGT 142 · Machine Learning"`)
  rather than a course id. That looks like it should be a relation, but the request
  can also name a term-wide action with no course at all, which is presumably why.
  Worth revisiting with the owner.
- **The `Advisor.location` / Zoom convention** described in §4. It works and it is
  not how you would design it.
- **The write shape for conversations**, per §8.
