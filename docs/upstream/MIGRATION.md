# MIGRATION.md

A map of THRIVE as it exists at commit `4e0a65b`, written for a port to
SvelteKit (adapter-node, server `load` functions, Django backend arriving later).

This is a description of what the code does, not a plan and not a critique.
Where a claim could not be verified from the source it is marked **UNCERTAIN**.

**Read this first — three counts in the brief do not match the tree:**

| Brief said | Actually is | Where |
|---|---|---|
| 21 provider functions | **25 exported functions + 1 exported error class** | `src/lib/data/providers.ts` |
| 61 tests | **83 tests in 5 spec files** (verified by running `npm test`) | `src/lib/*.spec.ts` |
| `todayKey()` | Lives in **`src/lib/buildSchedule.ts`**, not `format.ts`. The `format.ts` sibling is `localDayKey(iso)`. | — |

Everything below uses the real numbers.

**Scale:** 137 source files, ~17,918 lines. 18 files under `src/app`, 75 under
`src/components`, 42 under `src/lib`. Next.js 16.3.0, React 19.2.8,
Tailwind v4, TypeScript strict, Vitest 3.2.7.

---

## 1. Route inventory

Next.js App Router. Every route is a `page.tsx` under `src/app`. There are
**no** `loading.tsx`, `error.tsx`, `not-found.tsx`, `template.tsx`, or
`route.ts` files anywhere, and no dynamic segments, route groups, or parallel
routes — the whole app is flat static paths.

### Root layout — `src/app/layout.tsx`

Server component. Loads DM Sans (400/500/700) and JetBrains Mono (400/500) via
`next/font/google`, exposing both as CSS variables rather than classes. Sets
`metadata` (title template `"%s · THRIVE"`) and `viewport`
(`themeColor: "#faf9f5"`, `colorScheme: "light"`). Wraps everything in
`AppShell`. Declares **`export const dynamic = "force-dynamic"`** — see §3.

Signature is `RootLayout({ children }: LayoutProps<"/">)`. `LayoutProps` is a
Next-generated global type from `.next/types`, which is why `npm run build`
must run before `tsc --noEmit`.

### Routes

| Path | File | Server/client | Renders | Status |
|---|---|---|---|---|
| `/` | `app/page.tsx` | `async` server component | `ProgramTimelineCompact`, greeting panel, `TaskStatPills`, then a 2-col grid of `TasksCard`, Today's classes, My Classes (`CourseCard`), `UpcomingEvents` | **Done.** The only fully-built dashboard. Awaits 6 providers in one `Promise.all`. |
| `/calendar` | `app/calendar/page.tsx` | `async` server component | header + `CalendarView` | **Done.** Largest surface in the app. Awaits `buildScheduleData()` and `getTasks()`; passes `todayKey()` down as a string. |
| `/assignments` | `app/assignments/page.tsx` | `async` server component | `DeadlinesList` + `CourseworkList` | **Done.** Awaits `getTasks`, `getAssignments`, `getCourses`. Builds `CourseworkRow[]` server-side with `describeDue`. |
| `/appointments` | `app/appointments/page.tsx` | `async` server component | `BookingArea` + `AppointmentList` | **Done.** Awaits `getAdvisors`, then `Promise.all` of per-advisor `getSlots`, `getMyAppointments`, `buildScheduleData`. Builds `ServiceView[]`/`SlotView[]`/`AppointmentView[]`/`DayOption[]` — every date already a string. |
| `/degree/requests` | `app/degree/requests/page.tsx` | `async` server component | `RequestsWorkspace` + `RequestList` | **Done.** Awaits `getRequestPrefill`, `getTssConnection`, `getMyRequests`. |
| `/career/resume` | `app/career/resume/page.tsx` | `async` server component | `ResumeWorkspace` + `SkillsPanel` | **Done.** Awaits `getResumeVersions`, `getSkills`, `getCourses`. |
| `/degree` | `app/degree/page.tsx` | `async` server component | `ProgramTimeline` (real) + **`PagePlaceholder`** + a link card to `/degree/requests` | **Partial.** Timeline and the requests entry point are real; the page *body* is the stub. |
| `/career` | `app/career/page.tsx` | `async` server component | **`PagePlaceholder`** + a link card to `/career/resume` | **Partial.** Only the resume entry point is real. |
| `/classes` | `app/classes/page.tsx` | sync server component | **`PagePlaceholder`** only | **Stub.** 9 lines. |
| `/syllabi` | `app/syllabi/page.tsx` | sync server component | **`PagePlaceholder`** only | **Stub.** 9 lines. |
| `/events` | `app/events/page.tsx` | sync server component | **`PagePlaceholder`** only | **Stub.** 9 lines. |
| `/resources` | `app/resources/page.tsx` | sync server component | **`PagePlaceholder`** only | **Stub.** 9 lines. `getResources()` exists and returns data; nothing renders it. |
| `/settings` | `app/settings/page.tsx` | sync server component | **`PagePlaceholder`** only | **Stub.** 9 lines. `StudentConsent` exists on the type; nothing renders it. |

**Returns `PagePlaceholder` and nothing else:** `/classes`, `/syllabi`,
`/events`, `/resources`, `/settings` — five routes, each a 9-line file with a
`metadata` export and a single `<PagePlaceholder href="…" />`.

**Returns `PagePlaceholder` alongside real content:** `/degree`, `/career`.

`PagePlaceholder` (`src/components/PagePlaceholder.tsx`) is a server component
that looks its own `href` up in `primaryNav`/`secondaryNav` from `lib/nav.ts`
and **throws** if there is no matching nav entry. It renders the nav item's
icon, label, description, and a fixed "This section is coming next." panel.
A port must keep the nav list as the single source for stub pages or the throw
becomes reachable.

### Server actions — 6 functions in 3 files

All three files are `"use server"`. All call `revalidatePath()` and return
result objects rather than throwing (a taken slot is an ordinary outcome).

| File | Exports |
|---|---|
| `app/appointments/actions.ts` | `bookAppointmentAction(slotId, reason)`, `cancelAppointmentAction(appointmentId)` → `BookingResult` |
| `app/degree/requests/actions.ts` | `submitRequestAction(input)` → `RequestResult`, `connectTssAction()` → `{ok: true}` |
| `app/career/resume/actions.ts` | `regenerateResumeAction()` → `RegenerateResult`, `restoreVersionAction(versionId)` → `{ok, error?}` |

`submitRequestAction` holds the only validation logic outside a component:
type present, course non-empty, reason ≥ 10 characters. It then calls
`createRequest` followed immediately by `submitRequest` — the draft/submit
split exists in the data layer but no UI uses it.

**No auth check exists in any of the six.** Only
`appointments/actions.ts:29` carries a comment saying so.

---

## 2. The data layer

`src/lib/data/` is the seam. Public entry is `src/lib/data/index.ts`, which
re-exports `./types` and `./providers` — the convention is *import from
`@/lib/data`, never deeper*. That convention is violated in exactly one place
(§9).

Every provider returns a `Promise` today and is designed to keep returning one
when its body becomes a Django call. All 25 route their result through:

```ts
const MOCK_LATENCY_MS = 120;
function resolveAfterDelay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_LATENCY_MS));
}
```

So **every provider carries a fixed 120 ms delay**. `getProgramTimeline`,
`getRequestPrefill`, `bookAppointment`, `createRequest`, `submitRequest` and
`generateNewVersion` await other providers internally, so their real latency is
a multiple of 120 ms.

### The 25 exported functions, with exact signatures

**Reads — no store, pure fixture pass-through (5)**

| # | Signature | Notes |
|---|---|---|
| 1 | `getStudent(): Promise<Student>` | Returns `mockStudent` **by reference**, not a copy. |
| 2 | `getCourses(): Promise<Course[]>` | `buildMockCourses()` — rebuilt per call, dates relative to now. |
| 3 | `getSyllabi(): Promise<Syllabus[]>` | `buildMockSyllabi()`. Called by no route. |
| 4 | `getDegreeProgress(): Promise<DegreeProgress>` | Returns `mockDegreeProgress` by reference. |
| 5 | `getResources(): Promise<ResourceLink[]>` | Returns `mockResources` by reference. Called by no route. |

**Reads — fixture plus shaping (4)**

| # | Signature | Shaping done behind the boundary |
|---|---|---|
| 6 | `getAssignments(): Promise<Assignment[]>` | Sorted `dueDate` ascending. |
| 7 | `getTasks(): Promise<Task[]>` | `done` sorts last, then `dueDate` ascending. |
| 8 | `getEvents(): Promise<Event[]>` | **Filters out anything finished:** keeps `Date.parse(event.end ?? event.start) >= Date.now()`, then sorts by `start`. An all-day event stays listed until its end. |
| 9 | `getProgramTimeline(): Promise<ProgramTimeline>` | `async`. Awaits `getStudent()`, returns `buildProgramTimeline(student.programStart, student.track)`. Fully derived — nothing about the finish line is stored. |

**Reads — module-level store (7)** — ⚠ all reset on restart

| # | Signature | Store |
|---|---|---|
| 10 | `getAdvisors(): Promise<Advisor[]>` | `mockAdvisors` const (not mutable), by reference. |
| 11 | `getSlots(advisorId: string): Promise<AppointmentSlot[]>` | **Reads `readStore().claimedSlotIds`.** Rebuilds slots from `buildSlotsFor()` each call and flips `available: false` on anything claimed. |
| 12 | `getMyAppointments(): Promise<Appointment[]>` | **Reads `readStore().appointments`.** Filters `status === "confirmed"`, sorts by start, returns shallow copies. |
| 13 | `getMyRequests(): Promise<CourseRequest[]>` | **Reads `readRequestStore()`.** Drafts float to top, then newest `submittedAt` first. Shallow copies. |
| 14 | `getTssConnection(): Promise<boolean>` | **Reads `readRequestStore().tssConnected`.** |
| 15 | `getResumeVersions(): Promise<ResumeVersion[]>` | **Reads `readResumeStore()`.** Newest `createdAt` first, shallow copies. |
| 16 | `getCurrentResume(): Promise<ResumeVersion \| null>` | **Reads `readResumeStore()`.** Finds `isCurrent`. Called by no route. |

**Reads — composite (2)**

| # | Signature | Notes |
|---|---|---|
| 17 | `getSkills(): Promise<Skill[]>` | Maps `mockSkills` to shallow copies. Module const, not a mutable store. |
| 18 | `getRequestPrefill(): Promise<CourseRequestPrefill>` | `async`. `Promise.all([getStudent(), getCourses(), getDegreeProgress()])`, then derives `currentUnits` by summing `course.units`. |

**Mutations — all write to a module-level store (7)** — ⚠ all reset on restart

| # | Signature | What it writes |
|---|---|---|
| 19 | `bookAppointment(slotId: string, reason: string): Promise<Appointment>` | `async`. Re-derives the advisor by `slotId.startsWith(\`slot-${advisor.id}-\`)`, re-checks availability, **throws `SlotUnavailableError`** if gone. Pushes to `store.appointments`, adds to `store.claimedSlotIds`. Returns a copy. |
| 20 | `cancelAppointment(appointmentId: string): Promise<Appointment \| null>` | `async`. Sets `status = "cancelled"` in place, then releases a claimed slot **by matching `slot.start === appointment.start`** (see §9). Returns a copy, or `null` for an unknown id. |
| 21 | `createRequest(input: CourseRequestInput): Promise<CourseRequest>` | `async`. Awaits `getRequestPrefill()`, pushes a `status: "draft"` record. |
| 22 | `submitRequest(requestId: string): Promise<CourseRequest \| null>` | `async`. Flips `draft → submitted`, stamps `submittedAt = new Date().toISOString()`. Idempotent: a non-draft is returned unchanged. `null` for unknown id. |
| 23 | `connectTss(): Promise<boolean>` | Sets `store.tssConnected = true`. Always resolves `true`. |
| 24 | `generateNewVersion(): Promise<{ version: ResumeVersion; diff: ResumeDiff }>` | `async`. Awaits `getStudent()` + `getCourses()`. Builds a template summary via a private `composeSummary()`, computes a `ResumeDiff` against the previous current version, carries `experience` forward untouched, clears `isCurrent` on all others, pushes. |
| 25 | `setCurrentVersion(versionId: string): Promise<ResumeVersion \| null>` | Rewrites `isCurrent` across all versions. History is never deleted. `null` for unknown id. |

**Plus one exported class:**

```ts
export class SlotUnavailableError extends Error {
  constructor(message = "That time was just taken. Pick another.")
}
```

Only `bookAppointment` throws it; only `bookAppointmentAction` catches it (and
re-throws anything else).

### The three module-level stores

All three live in `src/lib/data/mock/`, are plain `const` objects at module
scope, and are **shared by every visitor to the process** and **wiped on
restart or hot reload**. This is the seam that changes when Django lands.

| File | Store shape | Seeding | Id generator |
|---|---|---|---|
| `mock/appointments.ts` | `{ appointments: Appointment[]; claimedSlotIds: Set<string>; nextId: number }` | Starts **empty**. | `nextAppointmentId()` → `apt-001` |
| `mock/requests.ts` | `{ requests: CourseRequest[]; tssConnected: boolean; nextId: number; seeded: boolean }` | `seedOnce()` on first read — one approved historical request `req-000`. **Lazy on purpose:** its dates are relative to now, and module load may be hours earlier. | `nextRequestId()` → `req-001` |
| `mock/resume.ts` | `{ versions: ResumeVersion[]; nextId: number; seeded: boolean }` | Lazy on first read — three versions with increasing skill counts, `res-003` current. `nextId` starts at **4**. | `nextVersionId()` → `res-004` |

Note the id-collision hazard a port inherits: `nextRequestId()` starts at 1 and
the seed is already `req-000`, so the first created request is `req-001`. The
appointments store starts empty so `apt-001` is free.

`buildSlotsFor(advisorId)` regenerates the whole slot list on every call from
"today", with **deterministic** ids (`slot-<advisor>-<dayIndex>-<timeIndex>`)
and **deterministic** availability (`isTaken()` hashes
`advisorId.length * 7 + dayIndex * 3 + timeIndex * 5`, taken when `% 4 === 0`).
The comment is explicit that `Math.random()` here would desynchronise server
from client.

> **Correction, 2026-08-22 (Phase 5).** "Deterministic availability" above is
> wrong as written. The ids and `isTaken()` are pure, but the field is
> `available: !inThePast && !isTaken(...)`, and `inThePast` reads `Date.now()`.
> So the output is fully determined by `advisorId` only *at a fixed instant*:
> today's slots drop out one by one as the day passes, and the whole five-day
> window shifts at midnight. Verified against the source, which wins. The port
> documents this at the function and freezes the clock to test it. `bookingDays()` skips weekends and publishes
`BOOKING_WINDOW_DAYS = 5` business days. `SLOT_MINUTES = 30`.

### `src/lib/data/mock/relative-dates.ts` — the clock every fixture reads

Every fixture is dated relative to *now* so the demo never looks stale, and
these run **when a provider is called**, not at module load.

- `startOfToday(): Date` — local midnight
- `at(days, hour = 9, minute = 0): string` — ISO instant, negative reaches back
- `onDay(days): string` — `YYYY-MM-DD`, built from **local** parts (the comment
  states `toISOString()` would shift across the date line)
- `upcomingWeekday(dayOfWeek, {hour, minute, weeksAhead}): string` — strictly
  future; today counts as +7, not 0
- `SUN`…`SAT` weekday constants

### `src/lib/data/types.ts` — 465 lines, one file on purpose

**Dates are ISO-8601 strings, never `Date` objects**, because RSC prop
serialization does not carry `Date` cleanly. Two aliases document intent:
`ISODateTime` and `ISODate` (both `string`).

Unions: `Standing` (`onTrack|watch|needsHelp`), `Track` (`"11 month"|"17 month"`),
`Priority`, `TaskSource` (`class|career|admin|event`), `AssignmentStatus` (5),
`EventType` (`rady|ucsd|sandiego|club|career`), `PhaseId` (6),
`PhaseStatus`, `AdvisingService`, `MeetingMode`, `AppointmentStatus`,
`CourseRequestType` (4), `CourseRequestStatus` (4), `SkillSource`,
`ResourceCategory` (5).

Interfaces: `StudentConsent`, `Student`, `ProgramPhase`, `ProgramTimeline`,
`CourseMeeting`, `NextAssignment`, `Course`, `SyllabusGradeComponent`,
`Syllabus`, `Assignment`, `Subtask`, `Task`, `Event`, `DegreeGap`,
`DegreeProgress`, `Advisor`, `AppointmentSlot`, `Appointment`, `CourseRequest`,
`CourseRequestPrefill`, `CourseRequestInput`, `Skill`, `ResumeExperience`,
`ResumeCourse`, `ResumeVersion`, `ResumeDiff`, `ResourceLink`.

`EventType` being a closed union is load-bearing: `EVENT_CATEGORIES` in
`schedule.ts` is exactly that set, which is what makes `isEventCategory()` a
reliable guard for "can this be ignored".

### `src/lib/buildSchedule.ts` — server-only flattener

`buildScheduleData(): Promise<ScheduleData>` reads **five** providers
(`getCourses`, `getAssignments`, `getEvents`, `getMyAppointments`,
`getAdvisors`) and flattens them. Called from `/calendar` and `/appointments`.

- Recurring class meetings stay as **weekday rules** (`RecurringMeeting`:
  `dayOfWeek` + wall-clock `startTime` + pre-rendered `timeLabel`), expanded on
  the client so any month works without a round trip.
- Assignments → `asg-${id}`, appointments → `apt-${id}`, events → `evt-${id}`.
- An event with no distinct `end` (or `end === start`) becomes `allDay: true`
  with `timeLabel: "All day"` and `sortMinutes: 0`.
- Also exports `todayKey(): string` = `dayKeyOf(new Date())`.

**Not merged here:** tasks and quick-list to-dos. See §3 and §6.

---

## 3. Date and time handling

### The rule, as actually implemented

> Components never see a raw timestamp. Every date is classified and formatted
> on the server, then passed down as a string.

The stated reason (in `format.ts`, `types.ts`, and every page's inline comment):
a client computing "today" would disagree with the server during hydration in
another timezone, **and** the answer would freeze at last render.

The rule is implemented in three moves:

1. **`force-dynamic` in the root layout** makes every render request-scoped.
2. **Server-side classification** into value objects (`DueDescriptor`) and
   view models (`*View` types) whose date fields are already strings.
3. **A narrowed exception** for anything the student can edit, where the server
   still decides *what now is* and passes it down as `nowISO`.

### `describeDue(iso, now = new Date()): DueDescriptor`

`src/lib/format.ts:129`. Pure — takes `now` as an argument, which is what makes
the narrowed exception possible.

```ts
export interface DueDescriptor {
  urgency: "overdue" | "today" | "upcoming";
  label: string;      // "Overdue" | "Today" | "Tomorrow" | "Fri" | "Aug 11"
  countdown: string;  // "today" | "tomorrow" | "in 3 days" | "2 days ago"
  days: number;       // whole calendar days; negative once overdue
  fullLabel: string;  // "Was due Monday, Aug 11" / "Due today" / "Due tomorrow"
}
```

Branch order: `days < 0` → overdue; `days === 0` → today; `days === 1` →
tomorrow; `days < 7` → weekday short name; else `formatShortDate(iso)`.

Supporting private helpers in the same file:
- `calendarDaysBetween(from, to)` — zeroes both to local midnight before
  differencing by `86_400_000`, so it counts **calendar days**, not elapsed time.
- `countdownPhrase(days)` — words not signed numbers; switches to weeks past 14
  days, months past 60.

### `todayKey()`

**`src/lib/buildSchedule.ts:123`**, not `format.ts`. Returns
`dayKeyOf(new Date())` — a `YYYY-MM-DD` local day key, "decided once on the
server". Called at exactly two sites, both server pages:
`app/calendar/page.tsx:34` and `app/appointments/page.tsx:38`. It flows down as
a **string prop** through `CalendarView`, `MiniCalendar`, `WeekView`,
`BookingArea`, `MyDayPane`, and is compared with `===` rather than recomputed.

### The `*View` types — pre-formatted view models

Every one exists so its consumer never parses a timestamp.

| Type | File | Date fields, pre-formatted |
|---|---|---|
| `DayOption` | `components/appointments/types.ts:12` | `key` (`YYYY-MM-DD`, grouping only, never displayed), `weekday` `"Tue"`, `date` `"Aug 12"`, `relative` `"Today"`/`"Tomorrow"`/weekday |
| `SlotView` | `components/appointments/types.ts:23` | `dayKey`, `timeLabel` `"9:30 AM"`. Also carries `startISO`/`endISO` — **raw, but only for `.ics` export** |
| `AppointmentView` | `components/appointments/types.ts:36` | `whenLabel` `"Tue, Aug 12 at 2:00 PM"` — one string, no parts |
| `ServiceView` | `components/appointments/types.ts:47` | wraps `days: DayOption[]`, `slots: SlotView[]` |
| `RequestView` | `components/requests/RequestList.tsx:12` | `submittedLabel` `"Submitted Aug 12, 2026"` or `"Not submitted yet"` |
| `VersionView` | `components/resume/ResumeWorkspace.tsx:21` | `createdAtLabel` |
| `CourseworkRow` | `components/assignments/CourseworkList.tsx:32` | carries a whole `DueDescriptor` |
| `TaskWithDue` | `components/TasksCard.tsx:20` | `{ task: Task; due: DueDescriptor }` |
| `BoardRow` | `lib/taskBoard.ts:42` | structurally identical to `TaskWithDue`, declared separately so `lib` need not import from `components` |
| `ScheduleItem` | `lib/schedule.ts:119` | `timeLabel`, `sortMinutes`, `allDay`, plus optional raw `startISO`/`endISO` for `.ics` |

### Where `force-dynamic` matters

Declared **once**, at `src/app/layout.tsx:59`, and it covers every route.
It is load-bearing for three things:

1. **Home's greeting** — `greetingFor(now)` reads `date.getHours()` on the
   server. Prerendered, a deployed build insists it is whatever time of day it
   compiled at.
2. **Every mock fixture** — `relative-dates.ts` dates everything against
   `startOfToday()` at call time. Prerendered, the whole demo freezes and drifts
   into "everything is overdue".
3. **`getEvents()`** — filters on `Date.now()`, so a static render bakes in the
   build-time cutoff.

For the SvelteKit port this is the default: a server `load` function in a node
process is request-scoped already. There is no equivalent flag to set — but the
*inverse* is now the risk, since anything cached or prerendered breaks all three.

### Every place a date is classified or formatted

**Server-side classification (the sanctioned path):**

| Site | Call |
|---|---|
| `app/page.tsx:48-53` | `const now = new Date()`, `nowISO`, then `describeDue(task.dueDate, now)` per task |
| `app/page.tsx:68` | `isWithinDays(event.start, 7, now)` for the week-events pill |
| `app/page.tsx:85` | `meeting.dayOfWeek === now.getDay()` for today's classes |
| `app/page.tsx:105,161` | `formatLongDate(now)` |
| `app/page.tsx:108` | `greetingFor(now)` |
| `app/page.tsx:203` | `describeDue(course.nextAssignment.due, now)` |
| `app/page.tsx:219` | `eventDateBlock(event.start)` → `{month, day, time}` |
| `app/assignments/page.tsx:24-41` | `now`, `describeDue` for both tasks and assignments |
| `app/appointments/page.tsx:18-27` | private `relativeDayLabel(date, today)` |
| `app/appointments/page.tsx:38,40` | `todayKey()`, `new Date()` |
| `app/appointments/page.tsx:59-64,72` | `toLocaleDateString`, `formatTime`, `localDayKey` |
| `app/appointments/page.tsx:98-102` | `whenLabel` assembly |
| `app/degree/requests/page.tsx:25-29` | `new Date(request.submittedAt).toLocaleDateString` |
| `app/career/resume/page.tsx:38` | `new Date(version.createdAt).toLocaleDateString` |
| `lib/buildSchedule.ts:37-46` | private `timeOf(iso)` and `minutesFrom(iso)` |
| `lib/buildSchedule.ts:57` | `wallClockLabel(meeting.startTime)` |
| `lib/buildSchedule.ts:66,85,104` | `dayKeyOf(new Date(...))` per item |
| `lib/buildSchedule.ts:79` | all-day determination |
| `lib/buildSchedule.ts:123` | `todayKey()` |

**`src/lib/format.ts` — the formatting vocabulary (all pure):**
`greetingFor(date?)`, `formatLongDate(date?)`, `formatShortDate(iso)`,
`formatTime(iso)`, `initialsOf(name)`, `standingLabel` map,
`describeDue(iso, now?)`, `localDayKey(iso)`, `isToday(iso, now?)`,
`isWithinDays(iso, days, now?)`, `formatClockTime(hhmm)`,
`formatMeetingPattern(schedule)`, `eventDateBlock(iso)`.
`localDayKey` is explicitly built from **local parts** because
`toISOString().slice(0,10)` would shift an evening appointment a day back in
any timezone behind UTC.

**`src/lib/schedule.ts` — day-key arithmetic (all pure, client-safe):**
`toDayKey(y, m, d)`, `dayKeyOf(date)`, `fromDayKey(key)`, `addDays(key, n)`,
`minutesOf(hhmm)`, `wallClockLabel(hhmm)`, `monthGrid(year, month)` (42 cells,
Sunday-start), `weekGrid(dayKey)` (7 cells, Sunday-start).
`fromDayKey` passes parts to the `Date` constructor rather than parsing the
string, because `new Date("2026-08-17")` parses as UTC and lands on the 16th
behind UTC.

### Client-side clock reads — there are exactly two, both deliberate

1. **`nowMinutes()`** — `lib/calendarSources.ts:262`. Returns minutes past
   midnight. Called at exactly one site,
   `CalendarView.tsx:134`, inside a `useMemo`, and only when the selected day
   *is* today: `nextUpItem(dayItems, isToday ? nowMinutes() : 0)`. On any other
   day `0` is passed, which yields the first timed item. `nextUpItem` itself
   takes `nowMinutes` as a parameter and reads no clock, so it stays pure and
   testable.
2. **`matchesWide()`** — `components/floating/useFloatingGeometry.ts:251`. Not a
   clock, a `matchMedia` read, but the same hydration shape: it goes through
   `useSyncExternalStore` with a server snapshot of `false`.

### The narrowed exception — `lib/taskBoard.ts`

This is the one place the rule bends, and the file documents it at length. A
student can edit a due date, stored only in `localStorage`, so *something* has
to reclassify it without a round trip.

The resolution: **the server still decides what "now" is.** `app/page.tsx:49`
computes `nowISO = now.toISOString()` and passes it as a prop. `useTaskBoard`
does `new Date(nowISO)` and re-runs the pure `describeDue` against **that**
instant. The client never calls `new Date()` to ask what day it is.
`nowISO` also feeds `dateForGroup`, `fromDateInputValue`, and new-task creation.

### Rule violations found

Two, both minor, both in the same family — deriving a *display* string on the
client from a raw value rather than from a pre-formatted one:

1. **`CalendarView.tsx:117`** builds the day heading on the client:
   `fromDayKey(selectedKey).toLocaleDateString("en-US", {weekday, month, day})`.
   It is fed by the server's `todayKey` or a user click, and `fromDayKey` is
   timezone-safe, so it cannot disagree about *which* day — but the *locale
   string* is produced by the browser, not the server. Same pattern at
   `lib/schedule.ts:578` (`groupAgenda` day headings) and
   `MyDayPane`/`WeekView`, which both call `fromDayKey(...).toLocaleDateString`.
   Consequence is limited to locale/format differences, not date drift.
2. **`lib/calendarItems.ts:162-163`** — `customEventToItem` calls
   `new Date(year, month-1, day, hour, minute).toISOString()` on the client to
   build `startISO`/`endISO` for a student-created event. This is the client
   authoring an instant from local parts. It is only consumed by `.ics` export,
   and the event was authored in the browser's own timezone, so it is
   self-consistent — but it is a client-minted timestamp.

Also worth naming, though not a violation of the stated rule:
`taskToItem` (`calendarSources.ts:86-91`) and `todoToItem` call
`toLocaleTimeString` and `getHours()/getMinutes()` **on the client**, because
they run inside `useMergedSchedule`. This is by design (the source rows are
localStorage-only) but it means a task's `timeLabel` is browser-formatted while
an assignment's on the same row is server-formatted.

**UNCERTAIN:** whether the locale-string-on-client cases above ever produce a
visible mismatch. Proving it needs a browser run with a forced non-US locale or
a server/client timezone split; neither was done here, and there is no test
covering it.

---

## 4. Component inventory

75 files under `src/components`. 47 carry `"use client"`; the rest are server
components (which in the port become ordinary Svelte components — the
distinction disappears, but it tells you which ones already touch browser
state).

### shadcn / Radix wrappers — need `shadcn-svelte` or `bits-ui` equivalents

Nine files in `src/components/ui/`, generated by shadcn (`components.json`:
style `radix-nova`, `rsc: true`, base colour `neutral`, icon library `lucide`).

| File | Radix primitive | Actually imported by |
|---|---|---|
| `ui/avatar.tsx` (112 lines) | `Avatar` — Root/Image/Fallback, plus local `AvatarBadge`, `AvatarGroup` | `shell/TopBar.tsx`, `appointments/ServiceCard.tsx` |
| `ui/tooltip.tsx` (57) | `Tooltip` — Provider/Root/Trigger/Content | **nothing** |
| `ui/popover.tsx` (89) | `Popover` — Root/Trigger/Content, portalled | **nothing** |
| `ui/separator.tsx` (28) | `Separator` — Root | **nothing** |
| `ui/button.tsx` (67) | `Slot` + `cva` variants | **nothing** — the app uses its own `Button.tsx` |
| `ui/badge.tsx` (49) | `Slot` + `cva` variants | **nothing** |
| `ui/card.tsx` (103) | none (plain divs) — Card/Header/Title/Description/Action/Content/Footer | **nothing** — the app uses its own `Card.tsx` |
| `ui/input.tsx` (19) | none | **nothing** |
| `ui/skeleton.tsx` (13) | none | `SectionCard.tsx` (`SectionSkeleton`) |

**Only three of the nine are reachable from the app:** `avatar`, `skeleton`,
and — transitively — nothing else. `tooltip`, `popover`, `separator`,
`ui/button`, `ui/badge`, `ui/card`, `ui/input` are vendored and unused. The
port needs Svelte equivalents for `Avatar` (Radix behaviour: image with
fallback-on-error) and `Skeleton` (pure CSS) and can drop the rest unless they
are wanted for future work.

`radix-ui` and `class-variance-authority` are used **only** inside
`src/components/ui/`. `clsx` + `tailwind-merge` (via `lib/utils.ts:cn()`) are
used app-wide and have direct Svelte equivalents.

`lucide-react` is used everywhere, including as **data**: `lib/nav.ts` stores
`LucideIcon` components as values in `NavItem.icon`, and `PagePlaceholder`
pulls the icon out of the nav config. `lucide-svelte` exists, but note the port
must keep icons-as-values working (Svelte 5 renders a component from a
variable with `<svelte:component>` or, in newer syntax, directly).

### Shared primitives — ours

| Component | Purpose |
|---|---|
| `Button.tsx` | The one button. `ButtonVariant = primary\|secondary\|ghost\|danger`, `ButtonSize = sm\|md`. Also exports `IconButton`. Every variant draws `border-2`. |
| `Card.tsx` | The one card. `CardTone = raised\|flat\|inset` — **all three currently map to the same `.thrive-panel` class**. Also `CardHeader`. Padding scale `none\|sm\|md\|lg`. |
| `Tag.tsx` | **Every chip in the app.** `TagTone` = neutral, quiet, primary, on-track, watch, needs-help, urgent, civic, later (9). Solid fills, white text, all pairings measured ≥4.5:1. |
| `StatusChip.tsx` | Exports the `standingTone` map (the only place a `Standing` becomes a tone) plus `StatusChip` and `InfoChip`. |
| `StatusBadge.tsx` | `Standing` as dot + word, via `Tag`. |
| `DueChip.tsx` | A `DueDescriptor` as a `Tag`. `urgencyTone`: overdue→urgent, today→watch, upcoming→**quiet** (no fill). |
| `Countdown.tsx` | The relative timer beside a due date. Renders `due.countdown`, coloured only at the extremes. |
| `EmptyState.tsx` | The one empty state. Optional icon, message, action. Never a dashed outline. |
| `SectionCard.tsx` | Home dashboard sections (title, description, optional "View all"). Also exports `SectionSkeleton` and `SectionEmpty`. |
| `SectionHeading.tsx` | **Every calendar section heading.** Mono eyebrow prefix + bold sans title + mono count + optional action slot. Polymorphic `as` prop (defaults `h2`). |
| `Callout.tsx` | Inline note inside a panel. Bold label + muted prose on sunken. Deliberately carries no colour and no icon. |
| `ProgressBar.tsx` | `ProgressTone = primary \| Standing`. Clamps 0-100. Requires an accessible `label`. |
| `StatPill.tsx` | `StatTone = urgent\|watch\|primary\|calm`. `calm` is the zero state. |
| `Toast.tsx` | The app-wide confirmation line. `role="status"`, **mounted always**, only its text changes. |
| `PagePlaceholder.tsx` | Stub-route body, driven by `lib/nav.ts`. Throws on an unknown href. |

### Home dashboard

| Component | Purpose |
|---|---|
| `TasksCard.tsx` (257) | Home's Tasks list. Drag-and-drop between groups, keyboard reorder, a live region, `AddTaskForm`, `UndoBar`. Exports the `TaskWithDue` type. |
| `TaskStatPills.tsx` | Home's three counts (overdue / due today / events this week). **Client so the counts see the student's own ticks and ignores.** |
| `CourseCard.tsx` | One course: code, title, instructor, schedule pattern, progress, standing, next due, optional `nudge` callout tinted by standing. |
| `UpcomingEvents.tsx` (113) | Home's events card. **Client so it can read the ignore store.** Filters ignored *first*, then slices to `VISIBLE = 4`, so the next event moves up. Home has no un-ignore path by design. |
| `EventRow.tsx` | One event row: date block, title, location, origin tag (`typeTone`/`typeLabel` per `EventType`), relevance badge, ignore button. |
| `timeline/ProgramTimeline.tsx` (263) | Exports `ProgramTimeline` (full stepper, `/degree`) and `ProgramTimelineCompact` (strip, `/`). Every state carries a non-colour cue: tick for complete, "You are here" for current, recessed fill + tag for optional. |

### Task editing — shared by `/` and `/assignments`

| Component | Purpose |
|---|---|
| `TaskRow.tsx` (376) | **The task row, used identically on both surfaces.** Checkbox, strike-through, title inline-edit, `DueDateEditor`, `PriorityPicker`, `TaskNotes` toggle, copy-to-quick-list, drag handle, keyboard reorder. |
| `AddTaskForm.tsx` (154) | Quick add, collapsed to one button. Title is the only required field. |
| `DueDateEditor.tsx` (160) | The due chip as a button opening a native `<input type="date">` plus three shortcuts. Also exports `GROUP_LABELS`. |
| `PriorityPicker.tsx` | Three radios (not a select). Deliberately uncoloured by its own value. |
| `TaskNotes.tsx` | One task's note panel. Draft held locally, committed on blur and on close — not per keystroke. |
| `UndoBar.tsx` | The way back from a tick. Fixed at the top of the list, not following the row. Deliberately **not** a live region. |
| `IgnoreButton.tsx` (120) | Exports `IgnoreButton`, `UnIgnoreButton`, `IgnoreUndoBar`. Deliberately low emphasis: no border, muted ink, `min-h-11`, weight set at the call site. |

### Calendar — 15 components, the largest surface

| Component | Purpose |
|---|---|
| `CalendarView.tsx` (316) | **The only stateful node.** Owns `selectedKey`, `monthKey`, `detail`. Applies `filterSchedule` once and hands the filtered data to every child. |
| `CalendarHeader.tsx` | The day's summary: big day figure, mono breakdown, "next up" line, `SquareGrid` strip. |
| `ViewSwitcher.tsx` | month / week / agenda as a `radiogroup`, plus the agenda-only grouping select. |
| `KeyBar.tsx` (204) | The key *and* the filter. Two dimensions kept separate: **streams** (fixed, `legendOrder`) and **labels** (open-ended, `allLabels(data)`), plus done / urgent-only / ignored toggles. |
| `MiniCalendar.tsx` (353) | Month grid. Up to 3 category dots per day and a `+n` overflow. Keyboard grid navigation via a `gridRef`. |
| `SquareGrid.tsx` | A day's tickable items as small squares — empty / done / next-ringed. Exports `SquareCell`, `SquareGroup`. |
| `WeekView.tsx` | Seven columns. Time stacked **above** title with `line-clamp-3`. Not rendered below `40rem` — the parent falls back to agenda. |
| `AgendaView.tsx` (131) | Flat grouped list over a 30-day range. **The only view that can carry undated to-dos.** |
| `DaySection.tsx` | One titled group on the selected day. Count is `done/tickable`, falling back to a bare total. |
| `DayGroupToggle.tsx` | Arrange the selected day by `type` (default) or `time`. |
| `ItemRow.tsx` (162) | One item, in the shape every view renders it. Mono tabular time, sans title, real checkbox on tickable rows. |
| `ItemDetail.tsx` (211) | Dialog with everything about one item plus every edit control (label, urgent, delete). A dialog, not an expanding row. |
| `AddItemForm.tsx` (220) | Add a task, a to-do, or a custom event — three kinds routing to **three different stores**. |
| `DayEventsSection.tsx` (231) | "Happening, register". Its own section because opting in is a different act from ticking off. Join / leave / `.ics` / ignore. |

### Appointments

| Component | Purpose |
|---|---|
| `appointments/types.ts` | View models only — `DayOption`, `SlotView`, `AppointmentView`, `ServiceView`. |
| `BookingArea.tsx` | Owns `activeId` and `selectedDayKey`, feeding both panes so picking a day moves them together. |
| `BookingPanel.tsx` (384) | Advisor availability: day picker, mode filter, slot chips, reason field (`REASON_MAX = 200`), confirmation, `.ics`. Uses adjust-during-render to follow the calendar. |
| `MyDayPane.tsx` | The student's own day beside the availability. **Classes and appointments only** — an assignment due at 11:59pm does not block a 2pm meeting. |
| `ServiceCard.tsx` | One advisor as a card. Uses `ui/avatar`. |
| `AppointmentList.tsx` | Booked appointments with cancel, via `useTransition`. |

### Requests, resume, assignments

| Component | Purpose |
|---|---|
| `requests/RequestsWorkspace.tsx` | Owns the two shared bits of state: form open, record linked. |
| `requests/NewRequestForm.tsx` (364) | The four request types with per-type help, course, reason. |
| `requests/RequestList.tsx` (126) | Requests with an expandable prefill snapshot. Exports `RequestView`. |
| `requests/RequestStatusChip.tsx` | `CourseRequestStatus` → `Tag`. Draft stays neutral. |
| `requests/TssConnectCard.tsx` | Represents linking to TSS. Copy states plainly that nothing is linked. |
| `resume/ResumeWorkspace.tsx` (335) | Version history, regenerate, restore, diff display, download. Exports `VersionView`. |
| `resume/ResumePreview.tsx` (135) | The resume as a document. Skills grouped by source. |
| `resume/SkillsPanel.tsx` | "Skills you are building" — every row names its origin course. Exports `SkillWithOrigin`. |
| `assignments/DeadlinesList.tsx` (146) | Every deadline grouped by how soon. Renders the same `TaskRow` as Home. |
| `assignments/CourseworkList.tsx` | The registrar's records as a table — deliberately not tickable. Exports `CourseworkRow`. |

### Shell, floating panels, assistant

| Component | Purpose |
|---|---|
| `shell/AppShell.tsx` | **`async` server component.** Awaits `getStudent()`. Skip link, `SideRail`, `TopBar`, main region, `BottomNav`, and both floating widgets. |
| `shell/SideRail.tsx` | Desktop rail from `primaryNav` + `secondaryNav`. `usePathname()`. |
| `shell/BottomNav.tsx` (169) | Mobile bar. Four fixed slots (`/`, `/calendar`, `/classes`, `/assignments`); the rest behind a "More" sheet. `usePathname()`. |
| `shell/TopBar.tsx` | Sticky header: identity left, bell + avatar right. Server component. |
| `floating/useFloatingGeometry.ts` (270) | Drag, resize (8 grips), dock, the 72px snap. Exports `HANDLES`, `Dir`, `FloatingBounds`, `FloatingGeometry`, `useFloatingGeometry`. |
| `floating/FloatingChrome.tsx` (140) | Exports `ResizeHandles`, `DockButtons`, `floatingPanelClasses`. Handles are `aria-hidden` — pointer-only, and keyboard resizing is named in-code as a real gap. |
| `assistant/AssistantWidget.tsx` | Launcher + panel mount for Ask THRIVE. |
| `assistant/AssistantPanel.tsx` (160) | The floating panel. **Modal while floating** (scrim, focus trap, `aria-modal`), releases both when docked. |
| `assistant/AssistantConversation.tsx` (135) | Placeholder conversation. **Has no brain** — replies with a fixed line saying it cannot answer yet. |
| `quicklist/QuickListWidget.tsx` (487) | The floating quick list — launcher, panel, rows, add, due, note, delete, clear-done. **Never modal.** |

---

## 5. Design system

Everything lives in **`src/app/globals.css`** (683 lines). It is the single
source of truth; the repo rule is *never hardcode a colour, size, radius, or
duration in a component*.

Three imports at the top: `tailwindcss`, `tw-animate-css`,
`shadcn/tailwind.css`.

### Architecture — three layers

1. **`:root`** — raw `--thrive-*` tokens
2. **`:root`** — shadcn semantic vars (`--background`, `--primary`, `--border`,
   …) **remapped onto layer 1**. This is why vendored shadcn primitives come out
   in THRIVE's palette with no patching.
3. **`@theme inline`** — exposes both as Tailwind v4 utilities

A port must preserve all three layers if it keeps any shadcn-derived components,
and layer 2 specifically if it adopts `shadcn-svelte`.

### Direction

**Soft cream, hairline, mono-accent** — adopted 2026-08-15, a deliberate
reversal of the 08-12 bordered direction. The structural devices are
whitespace, type hierarchy, and a row that fills on hover — *not* borders.

### The 1.5px control boundary vs the 1px decorative hairline

This is the single most important convention in the file and the CSS states it
as non-negotiable.

**Decorative hairlines — 1px, and they mean nothing:**

```css
--thrive-hairline: #e6e3dc;       /* 1.22:1 — panel edges, dividers */
--thrive-hairline-soft: #efece6;  /* 1.12:1 — inner dividers */
```

Neither clears any WCAG threshold and neither needs to. The rule, replacing the
older "a border below ~3:1 is not a border":

> Hairlines are decorative. If removing a border would make the layout
> ambiguous, the layout is wrong, not the border.

`--thrive-border`, `--thrive-border-strong`, and `--thrive-stroke` were
**deleted** in this pass.

**The one exception — control boundaries, 1.5px:**

```css
--thrive-control-line: var(--thrive-faint);   /* #85868c */
--thrive-control-stroke: 1.5px;
```

Checkbox, radio, input, select, and the resize grips owe **3:1 under WCAG
1.4.11**, because the boundary is the only thing marking where the control is.
They draw in `--thrive-control-line` at 1.5px and **never** in
`--thrive-hairline`.

`--thrive-faint` is `#85868c`, and the value is chosen so misuse fails a test:
it clears 3:1 (3.45 cream / 3.63 card / 3.16 sunken) and stops short of 4.5, so
putting *words* in it fails a contrast check rather than quietly shipping. It
was darkened from a spec'd `#8a8b91`, which landed at 2.96 on sunken — and
sunken is the row hover fill, so a checkbox on a hovered row sat under the bar.

The only consumers of the 1.5px stroke are `.thrive-checkbox`
(`border: var(--thrive-control-stroke) solid var(--thrive-control-line)`) and
`--input` in layer 2. `.thrive-panel[data-emphasis="strong"]` also borrows
`--thrive-control-line`, but at 1px — it is the one visible *decorative* line
in the system.

**Port note:** the distinction is carried by *two different tokens at two
different widths*, and the Tailwind aliases blur it — `border-line` is the
decorative hairline while `border-line-strong` is the control boundary, both of
which draw 1px unless the call site says otherwise. Getting this wrong is
silent: the layout looks fine and the accessibility guarantee is gone.

### Surfaces

```css
--thrive-bg: #faf9f5;       /* cream page */
--thrive-surface: #ffffff;  /* panels */
--thrive-sunken: #f1efea;   /* recessed wells, AND the row hover fill,
                               AND the de-emphasis fill */
```

`sunken` doing triple duty is why the `faint`-on-sunken ratio matters.

### Ink — four steps, only the first three may carry text

| Token | Value | On cream |
|---|---|---|
| `--thrive-ink` | `#17181c` | 16.8:1 — headings |
| `--thrive-body` | `#3a3b42` | 10.6:1 — body copy |
| `--thrive-muted` | `#6b6c72` | 4.97:1 — **all** secondary and metadata text (4.55:1 on sunken, the floor) |
| `--thrive-faint` | `#85868c` | 3.45:1 — **decorative text and control boundaries only** |

### Reserved colours — meaning enforced by convention

| Token | Value | Reserved for |
|---|---|---|
| `--thrive-indigo` | `#4c5bd4` | **"You are here" and nothing else.** Four sites: `CalendarHeader` today chip + next-up time, `SquareGrid` next-item ring, `WeekView` today. |
| `--thrive-urgent` | `#b8462f` | Overdue and genuinely urgent only. Reserved harder than the rest. |
| `--thrive-on-track` | `#3d6fb0` | Status only. Moved off green this pass — green now means "an action". |
| `--thrive-watch` | `#8f6220` | Status only. |
| `--thrive-needs-help` | `#6a5fb0` | Status only. |
| `--thrive-civic` | `#8a5f8f` | Categorical only, never status. |
| `--thrive-later` | `#64748b` | Categorical / neutral priority only. |

Sanctioned exception: `lib/schedule.ts` needs one dot per category (11
categories), each **paired with a written label** in the legend and in the day
list, so no meaning rests on hue alone.

Action accent: `--thrive-primary: #3f6b4f` (forest green, 6.13:1 on white — safe
for text *and* solid fills), plus `-hover`, `-active`, `-soft`, `--thrive-mint`,
`--thrive-on-mint`.

Soft tints are all derived with `color-mix(in oklab, <base> N%, white)` so they
cannot drift from the base hue: `on-track-soft` 9%, `watch-soft` 10%,
`needs-help-soft` 9%, `urgent-soft` 9%, `civic-soft` 9%, `later-soft` 9%,
`indigo-soft` 8%.

### No shadows

```css
--thrive-shadow-card: none;
--thrive-shadow-lifted: none;
```

**There is no drop shadow anywhere in THRIVE**, and no blurred replacement. A
white card on cream with a hairline is the entire elevation system. Nothing
floats. The two token names survive only so old references do not break — see
"dead" below.

### Type

**DM Sans for what a person wrote. JetBrains Mono for machine truth** —
numerals, counts and fractions, IDs and task numbers, compact dates, status
eyebrows, and any label that is a system value. **Prose never goes in mono.**

Both faces are injected by `next/font` in `layout.tsx` as CSS variables
(`--font-dm-sans`, `--font-jetbrains-mono`) and then referenced from
`--font-sans` / `--font-mono` in `globals.css`, keeping fonts inside the token
system. **Only 400/500/700 of DM Sans and 400/500 of JetBrains Mono are
loaded.**

Scale — size, line-height, and tracking only:

| Utility | Size | Line-height | Tracking |
|---|---|---|---|
| `text-3xs` | 0.75rem / 12 | 1rem / 16 | — |
| `text-2xs` | 0.8125rem / 13 | 1.125rem / 18 | — |
| `text-xs` | 0.875rem / 14 | 1.25rem / 20 | — |
| `text-sm` | **1rem / 16 — body default** | 1.4375rem / 23 | — |
| `text-base` | 1.125rem / 18 | 1.5625rem / 25 | — |
| `text-lg` | 1.375rem / 22 | 1.75rem / 28 | — (lost it this pass) |
| `text-xl` | 1.6875rem / 27 | 2.0625rem / 33 | -0.025em |
| `text-2xl` | 2.125rem / 34 | 2.4375rem / 39 | -0.03em |
| `text-3xl` | **2.5rem / 40 — page titles only** | 2.75rem / 44 | -0.035em |

**Weight is NOT in the scale** (reversed 08-15). Set it at the call site or you
get 400. The intended three-weight rule is 400 prose / 500 row titles and
emphasis / 700 page and section headings.

**`font-semibold` must never be used** — 600 is not loaded, so it synthesises.
Verified: **0 occurrences** in the tree. The rule is currently respected.

**Responsive type — one rule, load-bearing:**

```css
@media (width < 40rem) { html { font-size: 106.25%; } }
```

In `@layer base`. It nudges the **root**, which scales type, spacing, *and* the
shell's rem-based heights together by the same 6.25%, so proportions never
change and no component needs a breakpoint. Deleting this one rule reverts it.

### Spacing and radii

`--spacing: 0.25rem` (4px base step). Radii were all moved **up** this pass
because tight corners read as unfinished once the stroke is gone:

`--radius-xs` 4 (small chips) · `--radius-sm` 6 (controls, glyph buttons) ·
`--radius-md` 8 (inline) · `--radius-lg` 10 (rows) · `--radius-xl` 16 (cards
and panels) · `--radius-pill` 999px. Checkboxes are a hardcoded 5px inside
`.thrive-checkbox`. `--radius: 1rem` in layer 2 for shadcn.

### Motion

`--thrive-motion-fast: 120ms` · `-base: 160ms` · `-slow: 260ms` ·
`--thrive-ease-standard: cubic-bezier(0.2, 0.8, 0.3, 1)` (decelerates, never
overshoots) · `--thrive-ease-pop: cubic-bezier(0.2, 1.4, 0.4, 1)`.

**`ease-pop` is the single sanctioned overshoot in the system**, used only for
the tick landing in a checkbox. Usage convention at call sites is
`duration-(--motion-base) ease-standard`.

A global `prefers-reduced-motion: reduce` block collapses every animation and
transition to `0.01ms` — state changes still land, they just land instantly.

### Layout constants

`--thrive-rail-width: 15rem` · `--thrive-topbar-height: 3.5rem` ·
`--thrive-bottomnav-height: 3.75rem`, exposed as `spacing-rail`,
`spacing-topbar`, `spacing-bottomnav`.

### Light-only, by decision

```css
@custom-variant dark (&:is(.dark *));
```

`dark:` is pinned to a class **nothing ever applies**, which keeps the handful
of `dark:` rules inside vendored shadcn primitives inert without editing
vendored files. `color-scheme: light` is set on `html` and
`viewport.colorScheme = "light"` in the layout, so a machine set to dark does
not get auto-darkened scrollbars and native widgets on a warm-white page.

**Port note:** if the Svelte port drops shadcn's vendored CSS, this custom
variant becomes unnecessary — but `color-scheme: light` must stay or native
form controls invert.

### `@layer base` rules a port must carry

- `* { @apply border-hairline; }` — **any border that gets drawn is a hairline
  by default.** Components opt into something stronger.
- `html` — `font-sans`, `-webkit-font-smoothing: antialiased`,
  `text-rendering: optimizeLegibility`, `color-scheme: light`
- `button, a, label, [role="button"], input, select, textarea` —
  `touch-action: manipulation` (kills the 300ms double-tap-zoom delay) and a
  palette-derived `-webkit-tap-highlight-color`
- `body` — `bg-background text-foreground text-sm`
- `h1..h4` — `text-ink` + `text-wrap: balance`
- `time, [data-tabular]` — `font-variant-numeric: tabular-nums`, so a row does
  not reflow as "in 3 days" becomes "in 10 days"
- `:focus-visible` — **one** treatment app-wide: 2px primary outline, 2px
  offset, `--radius-sm`

### CSS components — `@layer components`

These are real CSS classes driven by data attributes, not Tailwind strings.
They must be ported as CSS, not as utility soup.

| Class | Behaviour |
|---|---|
| `.thrive-panel` | 1px hairline, `--radius-xl`, white surface, `padding: 1.25rem`. Variants `[data-tone="sunken"]`, `[data-tone="paper"]`, `[data-emphasis="strong"]` (control-line border), `[data-flush="true"]` (transparent border). Used in **31 files**. |
| `.thrive-row` | Transparent at rest, `sunken` on hover, `--radius-lg`, transitions background + opacity. `[data-done="true"]` → `opacity: 0.62`. Used in **5 files**. |
| `.thrive-checkbox` | The load-bearing control. `appearance: none`, 17×17px, 1.5px control-line border, 5px radius, `::after` tick that scales in with `ease-pop`, `:checked` fills primary. Used in 4 calendar files. |
| `.thrive-strike` | Strike-through drawn as a `scaleX` pseudo-element (not `line-through`) so completing a task reads as an action. 1.5px. Animates `transform`, **not `width`** — deliberately, to stay off the layout path. Used in `TaskRow` and `QuickListWidget`. |
| `.thrive-priority-label` | Mono eyebrow carrying priority as a word. |

**Important `.thrive-panel` gotcha:** padding is set in the components layer, so
**a Tailwind utility on the element wins** (utilities layer beats components
layer). Many panels carry an explicit `p-3` and keep the tighter padding. A
port that reimplements `.thrive-panel` as a Svelte component prop rather than a
CSS class will change padding on every one of those call sites.

### `@layer utilities`

- `@keyframes thrive-rise` + `.animate-rise` — a short fade-and-rise so
  content swapped in place reads as a transition rather than a flicker. Used in
  `Toast.tsx` and `CalendarView.tsx` (keyed on `selectedKey` so it replays per
  day change).
- `.skip-link:not(:focus-visible)` → `sr-only`; `.skip-link:focus-visible` gets
  an explicit `border-line-strong` because `shadow-card` is now `none` and it
  would otherwise be a white box on cream with no edge. Used in `AppShell.tsx`.

### Dead or unused, verified by grep

| Thing | Status |
|---|---|
| `.thrive-priority-label` | **Dead. 0 usages in any `.tsx`.** Defined for the sweep; nothing calls it. Priority currently reads only from `taskView.ts` text labels. |
| `--shadow-card` / `--shadow-lifted` (and the `shadow-card`/`shadow-lifted` utilities) | **Dead. 0 usages in any `.tsx`.** The CSS comment says "six components still ask for them" — that is now stale; the sweep already removed the call sites. Both resolve to `none` regardless. |
| `.thrive-row[data-priority]` | The `data-priority` attribute is still emitted (`TaskRow.tsx`, `QuickListWidget.tsx`) but **draws nothing** — priority-by-colour was removed and the hook was left in place. Not an information loss: every row also states its priority in text. |
| `Card.tsx` tones `raised`/`flat`/`inset` | All three map to the identical string `"thrive-panel"`. The API distinguishes three tones; the output does not. |
| `ui/tooltip`, `ui/popover`, `ui/separator`, `ui/button`, `ui/badge`, `ui/card`, `ui/input` | Vendored, imported by nothing. |
| `border-2` | **Not dead — 20+ call sites still draw 2px** in a much lighter colour, left over from the bordered direction. `Button.tsx:20` puts it on every button variant. This is the unfinished sweep named in `HANDOFF.md`. |

### The palette's regression test

**`scripts/check-contrast.py`** — 43 assertions, and the repo rule is that it is
updated in the *same commit* as any token change. Three of the 43 are
**ceilings**, asserting `faint` stays *below* 4.5:1 on all three surfaces, so
putting words in `faint` fails a check rather than shipping.

Run during this inventory: **43/43 pass.** A port should carry this script
across unchanged — it is pure Python reading hex values and needs nothing from
Next.

---

## 6. State and stores

There is **no React Context anywhere** (`createContext`/`useContext`: 0
occurrences) and no state library. All shared state is either a server prop or
a `useSyncExternalStore`-backed module singleton.

### The one persistence mechanism — `lib/overrideStore.ts`

```ts
createOverrideStore<T>(key: string): OverrideStore<T>
// { useValues(): Readonly<Record<string, T>>; set(id, value|undefined): void;
//   read(): Readonly<Record<string, T>> }
```

`localStorage` + `useSyncExternalStore`. Every store built on it holds
**overrides keyed by id, never the whole truth** — the providers stay
authoritative and this layer records only what the student personally changed.
That distinction is load-bearing: a bare "set of done task ids" cannot express
*"I unticked a task that ships as done"*, so it would silently re-tick on
reload. `undefined` means "never touched, use the source value".

Three properties a port must reproduce exactly:

1. **`getServerSnapshot()` returns a frozen shared `EMPTY` object.** Server
   render and first client render both see "no overrides"; real values land on
   the render *after* mount. **Nothing built on this may be read during a server
   render.**
2. **Corrupt input cannot take the page down.** `read()` rejects anything that
   is not a non-array object, and both `JSON.parse` and
   `localStorage.setItem` are inside `try/catch` (quota, private mode).
3. **A write that matches the source value forgets the override** rather than
   storing it — the store only ever holds genuine divergence.

For SvelteKit this maps onto a custom store with a `subscribe`, but the
server-snapshot behaviour is the part that changes shape: SSR in a node process
has no `localStorage` either, so the "empty on the server, real after mount"
ordering still has to be built deliberately.

### Persisted stores — 14 `localStorage` keys

| Key | Module | Holds | Type |
|---|---|---|---|
| `thrive:task-done` | `userEdits.ts` | Done overrides per task id | `boolean` |
| `thrive:event-joins` | `userEdits.ts` | "Count me in" per **calendar item id** | `true` |
| `thrive:task-titles` | `userEdits.ts` | Rewritten titles | `string` |
| `thrive:task-priority` | `userEdits.ts` | Reset priorities | `Priority` |
| `thrive:task-due` | `userEdits.ts` | Moved due dates, **full ISO instant** not a day | `string` |
| `thrive:task-order` | `userEdits.ts` | Sparse sort key within a group | `number` |
| `thrive:task-added` | `userEdits.ts` | **Whole tasks the student created** — not overrides, these have no source row | `Task` |
| `thrive:task-notes` | `taskNotes.ts` | Free-text notes per task. **Its own hand-rolled store**, not an override store — notes are not an override of anything | `string` |
| `thrive:quicklist` | `quickList.ts` | The quick-list items themselves | `QuickItem` |
| `thrive:item-labels` | `calendarItems.ts` | Free-text label per **calendar item id** | `string` |
| `thrive:item-urgent` | `calendarItems.ts` | Urgent flag per calendar item id | `true` |
| `thrive:custom-events` | `calendarItems.ts` | Student-created calendar events | `CustomEvent` |
| `thrive:ignored-events` | `ignoredEvents.ts` | Dismissed events, keyed on **raw `Event.id`** | `true` |
| `thrive:calendar-prefs` | `calendarPrefs.ts` | All calendar UI prefs under the single key `"value"` | `CalendarPrefs` |
| `thrive:assistant` | `assistantPanel.ts` | Ask THRIVE panel geometry, under the single key `"panel"` | `PanelState` |
| `thrive:quicklist-panel` | `quickList.ts` | Quick-list panel geometry | `PanelState` |

(16 rows, 14 distinct mechanisms — `calendarPrefs` and the two panel stores use
the override store with one fixed key rather than one key per id.)

**Two different keying schemes, deliberately:**

- `thrive:task-*` are keyed by **task id** — the thing the student owns.
- `thrive:item-labels` / `thrive:item-urgent` are keyed by **calendar item id**
  (`asg-12`, `apt-3`, `task-7`, `todo-x`), which is what lets a student flag an
  *assignment* urgent or label a *booked appointment* — rows they do not own and
  which have nowhere on the server to record it.
- `thrive:ignored-events` is keyed by **raw `Event.id`**, normalised through
  `eventIdOf()`, because Home holds `event.id` (`evt-3-1`) while `buildSchedule`
  prefixes it again (`evt-evt-3-1`). One store, two surfaces, one key space.

### Non-persisted module singletons

| Module | Holds | Persists? |
|---|---|---|
| `lib/toast.ts` | **One** transient confirmation line + its 3000ms timer. A single slot, not a queue — two in quick succession replace rather than stack. | **No, by design.** "A confirmation that survives a reload has stopped being a confirmation." |

### Derived hooks — no state of their own

| Hook | File | What it does |
|---|---|---|
| `useTaskToggle()` | `userEdits.ts:200` | Done state + a 6000ms single-slot undo, shared by Home and `/assignments` so they cannot drift. Holds `undo` in `useState` and the timer in `useRef`. |
| `useIgnoreEvents()` | `useIgnoreUndo.ts:47` | Mirrors the above for ignores. Same 6000ms, same single slot — a second dismissal **replaces** the first. Un-ignoring deliberately raises no undo strip. |
| `useTaskBoard(items, nowISO)` | `taskBoard.ts:121` | The whole Tasks list resolved: merges added tasks, applies title/priority/due overrides, reclassifies moved dates against `nowISO`, groups overdue/today/upcoming (`WEEK = 7`), orders within a group, exposes `reorder`, `moveToGroup`, `setDue`, `add`. |
| `useMergedSchedule(server, serverTasks)` | `calendarSources.ts:152` | Reads **nine** stores and folds tasks, to-dos and custom events onto the server's `ScheduleData`. Returns `{data, undatedTodos}`. |
| `useCalendarPrefs()` | `calendarPrefs.ts:130` | `useMemo(() => normalisePrefs(stored), [stored])`. **The memo is load-bearing** — `normalisePrefs` builds a fresh object, so without it every render produced a new `prefs.hidden` array and every downstream `useMemo` (the schedule filter, over 42 grid cells) recomputed. |
| `useFloatingGeometry(ref, state, onChange, bounds)` | `floating/useFloatingGeometry.ts:76` | Drag/resize/dock. Holds `dragging`/`resizing` in `useState`, drag and resize origins in `useRef`, and reads the `(min-width: 40rem)` media query through `useSyncExternalStore` with a server snapshot of `false`. |
| `useTaskNote(taskId)` | `taskNotes.ts:98` | One note plus a memoised setter. |

`normalisePrefs` merges over `DEFAULT_PREFS` field by field with type guards —
a half-written value or a field a previous build never wrote cannot break the
page. **This function has caught four separate new-field omissions** and has 11
tests of its own. `DEFAULT_PREFS.showDone` is **`true` on the calendar**, unlike
everywhere else, because hiding done items made a ticked task vanish under the
cursor and made the header's "0 of 2 done" denominator shrink as you worked.

### Component-local state — every `useState` in the tree

| File | State |
|---|---|
| `appointments/BookingPanel.tsx` | `dayKey`, `mode`, `slotId`, `reason`, `error`, `confirmed`, `seenExternal`, + `useTransition` (8) |
| `calendar/AddItemForm.tsx` | `open`, `kind`, `title`, `time`, `label`, `urgent` (+`useId`) |
| `requests/NewRequestForm.tsx` | `type`, `course`, `reason`, `error`, `done`, + `useTransition` |
| `AddTaskForm.tsx` | `open`, `title`, `dueDay`, `label`, `priority` (+`useId`) |
| `resume/ResumeWorkspace.tsx` | `viewingId`, `diff`, `attachedTo`, `busy`, + `useTransition` |
| `quicklist/QuickListWidget.tsx` | `draft` (panel), `expanded` + `note` (per row) |
| `calendar/CalendarView.tsx` | `selectedKey`, `monthKey`, `detail` |
| `TasksCard.tsx` | `drag`, `dropTarget`, `announcement` (+ a live-region timer ref) |
| `TaskRow.tsx` | `noteOpen`, `editOpen`, `draft` (+ title input ref, `useId`) |
| `requests/RequestsWorkspace.tsx` | `showForm`, `isConnected` |
| `assistant/AssistantConversation.tsx` | `messages`, `draft` (+ `nextId` ref) |
| `appointments/BookingArea.tsx` | `activeId`, `selectedDayKey` |
| `appointments/AppointmentList.tsx` | `pendingId`, `error`, + `useTransition` |
| `shell/BottomNav.tsx` | `moreOpen` |
| `requests/RequestList.tsx` | `openId` |
| `calendar/ItemDetail.tsx` | `label` (draft) |
| `TaskNotes.tsx` | `draft` (+ a `latest` ref holding `{draft, onSave}`) |
| `DueDateEditor.tsx` | `open` |

**None of this is persisted.** Every one of these resets on navigation.

`useMemo` appears in `CalendarView` (7), `DeadlinesList` (2),
`BookingPanel` (2), `calendarSources` (1), `calendarPrefs` (1), `taskBoard` (2).
`useEffect` appears in only 6 files, and — per the repo's React Compiler lint
rule — **never to call `setState`**. `useTaskToggle` and `useIgnoreEvents` both
use `useEffect` for timer *cleanup only*, with the timer armed from the event
handler.

`useTransition` (5 files) is React's pending-state primitive around server
actions. There is **no** `useOptimistic` and **no** `useActionState` anywhere.

---

## 7. Tests

**5 spec files, 83 tests, all passing.** Vitest 3.2.7, `environment: "node"`,
**no jsdom**, so nothing renders. Coverage is the pure logic under `src/lib`
and nothing else.

```
 ✓ src/lib/calendarItems.spec.ts    (9 tests)   3ms
 ✓ src/lib/ignoredEvents.spec.ts   (21 tests)  13ms
 ✓ src/lib/calendarPrefs.spec.ts   (11 tests)   4ms
 ✓ src/lib/schedule.spec.ts        (24 tests)  38ms
 ✓ src/lib/calendarSources.spec.ts (18 tests)  24ms

 Test Files  5 passed (5)
      Tests  83 passed (83)
```

**All 83 test pure logic. Zero test React rendering. Zero need rewriting for
behaviour — they need only an import-path and runner change.** Vitest works in
SvelteKit unchanged, so the realistic port cost here is near zero.

`vitest.config.ts` re-declares the `@/` alias because **Vitest does not read
`tsconfig` paths** — without it every `@/lib/...` import in a spec fails to
resolve. The port needs the equivalent alias in its Vite config.

### `schedule.spec.ts` — 24 tests, grid arithmetic and grouping

| Suite | Tests | Covers |
|---|---|---|
| `isVisible` | 3 | hides a switched-off category; hides done unless `showDone`; **never hides an untickable item via `showDone`** |
| `filterSchedule` | 3 | drops `recurring` when `class` hidden; keeps it otherwise; filters `dated` by the same rule as `isVisible` |
| `nextUpItem` | 6 | first item at or after now; **includes an item starting exactly now**; null once the day is over; null on an empty day; skips done; skips all-day |
| `groupAgenda` | 5 | groups by day and drops empty days; **expands recurring classes into the range**; groups by category in legend order not insertion order; groups by course with everything courseless in one bucket, last; no groups for an empty range |
| `groupDayItems` | 4 | orders by kind of obligation not time or legend order; drops empty groups; **excludes events**; nothing for an empty day |
| `weekGrid` | 3 | seven days starting Sunday; no shift when already Sunday; crosses a month boundary without drifting |

### `calendarSources.spec.ts` — 18 tests, the merge

| Suite | Tests | Covers |
|---|---|---|
| `taskToItem` | 6 | **lands on the local day, not the UTC one**; never all-day; carries done/priority/course; prefixed id; null on an unparseable date; uses the `task` category |
| `todoToItem` | 6 | all-day (the picker never offers a time); local day; prefixed id; carries done; null on unparseable; null when undated |
| the attached source row | 6 | a task row carries its `Task`; **carries a task the server has never seen**; a to-do row carries its `QuickItem`; `isTickable` true for both and false for anything else; counts tickables separately from total; **is not fooled by a `done` flag with no source row** |

That last suite is the regression net for the bug in §9 — it asserts the
*mechanism* (an attached object), not just the symptom.

### `ignoredEvents.spec.ts` — 21 tests, the largest suite

| Suite | Tests | Covers |
|---|---|---|
| `eventIdOf` | 3 | strips the calendar prefix; leaves a raw id alone so double-passing is safe; both surfaces key identically |
| `canIgnore` | 4 | allows all five opt-in origins; **refuses everything the student is committed to**; refuses the student's own items; **covers every category in the legend, so nothing is unclassified** |
| `isEventIgnored` | 2 | matches given either a raw or a calendar item id; false for anything absent |
| `filterSchedule` + ignores | 5 | hides by default; reveals with `showIgnored`; **NEVER hides a class even if its id collides**; **NEVER hides an assignment or a task**; drops the row from `ScheduleData` so every consumer agrees |
| month dots and `+n` | 5 | counts five categories and shows `+n`; loses the dot for an ignored event; **shrinks the `+n` rather than still counting hidden events**; no dot when every event is ignored; **still shows the class dot** on such a day |
| undo position | 2 | removes the middle row and closes the gap; **puts it back between A and C, not at the end** |

### `calendarPrefs.spec.ts` — 11 tests, defaults and migration

Defaults for nothing stored · **defaults to showing everything, not hiding
everything** · keeps a valid stored value · `showIgnored` defaults false ·
repairs a non-array `hiddenLabels` and a non-boolean `urgentOnly` · **day
arrangement defaults to `type`, not `time`** · repairs a non-array `hidden` ·
repairs a non-boolean `showDone` · falls back to `month` for an unknown view ·
falls back to `day` for an unknown `groupBy` · **fills in a field a previous
build never wrote**.

This suite's stated purpose is exactly the migration case: its input is
whatever happens to be in a browser's `localStorage`.

### `calendarItems.spec.ts` — 9 tests

`customEventToItem` (6): maps a timed event onto its day · treats a missing
time as all-day rather than midnight · carries label/urgent/custom marker ·
prefixes the id · **rejects a malformed day key instead of guessing** ·
**rejects a date that does not exist (`2026-02-31`) rather than rolling it
forward into March**.

urgent and label filtering (3): `urgentOnly` keeps only flagged items · hides
an item whose label is switched off · **never hides an unlabelled item via a
label filter**.

### What is NOT covered

No component tests and no jsdom environment. No route tests. Nothing covering
the appointments, requests, or resume flows. Nothing covering
`lib/format.ts` (including `describeDue` — the most-used pure function in the
app), `lib/taskView.ts`, `lib/taskBoard.ts`, `lib/data/mock/program.ts`
(`buildProgramTimeline` is pure and fully parameterised including the clock,
and has no test), `lib/ics.ts`, or any provider.

**Playwright is deliberately not a dependency.** It has been used twice, both
times from a scratch directory outside the repo.

---

## 8. React-specific code needing a real decision

Ordered roughly by how much thinking each needs, not by size.

### 1. `useSyncExternalStore` — the whole persistence layer

Six modules use it: `overrideStore.ts`, `taskNotes.ts`, `toast.ts`,
`calendarPrefs.ts`, `calendarSources.ts`, `floating/useFloatingGeometry.ts`.

Svelte stores are a natural fit for the subscribe/snapshot shape, but the
**three-snapshot contract has no direct equivalent**: React distinguishes
`getSnapshot()` (client) from `getServerSnapshot()` (SSR), and the whole
hydration story rests on the server one returning a frozen shared `EMPTY`.
Svelte has no separate server-snapshot hook — the decision is *where* the
"empty until mounted" gate lives (a `browser` guard, an `onMount` hydration
pass, or a `$effect`), and that choice determines whether the first paint
flashes un-personalised content the way React's currently does.

The **referential stability** requirement is also React-specific:
`useSyncExternalStore` must hand back the *same object* between renders or
downstream `useMemo`s bust. Svelte's reactivity is fine-grained, so this
constraint mostly evaporates — but `useCalendarPrefs`'s memo exists *only*
because of it, and porting it mechanically would be cargo-culting.

### 2. The Server Component / Client Component split

47 of 75 components are `"use client"`; `AppShell` is an `async` **server**
component that awaits a provider mid-tree. SvelteKit has no equivalent
boundary — everything is a component, and data comes from `load`. So this is
not a translation, it is a re-architecture decision:

- `AppShell` awaiting `getStudent()` inside the component tree has to become a
  root `+layout.server.ts` `load`.
- The pages that currently `Promise.all` several providers become
  `+page.server.ts` `load` functions — a clean mapping.
- **But** the split is currently doing real work: it is *why* dates are
  classified server-side, and it is what forces `nowISO` to be passed as a prop
  rather than read. Collapsing the boundary removes the compiler-enforced
  reason for the discipline in §3. The rule then has to be held by convention.

### 3. Server actions → form actions

Six actions across three files. `revalidatePath()` has a SvelteKit analogue in
`invalidate`/`invalidateAll` plus the automatic rerun of `load` after a form
action, but the shapes differ:

- Actions here are **called imperatively** from `useTransition` inside a click
  handler, not submitted from a `<form>`. SvelteKit form actions are
  form-first; `use:enhance` covers most of it, but `cancelAppointmentAction(id)`
  and `restoreVersionAction(versionId)` are per-row buttons with no form.
- The **return-errors-as-values** convention (`{ok: false, error}`) maps well
  onto SvelteKit's `fail()`.
- `SlotUnavailableError` is thrown across the action boundary and caught inside
  it — that part is portable.

### 4. `useTransition` (5 sites)

React's concurrent pending-state primitive. There is no Svelte equivalent
because there is no concurrent renderer; each site becomes a plain
`let pending = true/false` around an `await`. Mechanical, but it is 5 sites and
the *semantics* differ (React keeps the old UI interactive during the
transition; a boolean does not).

### 5. Adjust-during-render (`BookingPanel.tsx:93-104`)

```ts
const [seenExternal, setSeenExternal] = useState(selectedDayKey);
if (selectedDayKey !== seenExternal) {
  setSeenExternal(selectedDayKey);
  if (/* the new day is bookable */) { setDayKey(selectedDayKey); setSlotId(null); }
}
```

This is a **React-specific idiom** — setting state during render to derive from
a changed prop, used because the repo's lint hook bans `setState` inside
effects (React Compiler rule) and because an effect would paint the wrong day
first. Svelte has no render phase to adjust during. It becomes either a
`$derived` (if the value is genuinely derived) or a `$effect` with a guard (if
the reset of `slotId` is a real side effect). **Deciding which is a semantics
question, not a syntax one** — the current code deliberately does *both*
(derive `dayKey`, and clear `slotId` as a side effect).

### 6. `React.RefObject` passed into a hook

`useFloatingGeometry(panelRef, …)` takes the ref from the caller rather than
creating it, and the doc comment explains why: returning it would put a ref
inside an object read every render, which the React Compiler treats as a ref
access during render. That entire constraint is React-only. Svelte's
`bind:this` removes the problem — and with it, the reason the hook has this
shape at all.

### 7. Focus management, modality, and portals

`AssistantPanel` traps focus and sets `aria-modal` **only while floating**,
releasing both when docked. `ItemDetail` is a dialog with a `closeRef`.
`BottomNav`'s "More" sheet manages focus back to `moreButtonRef`. `MiniCalendar`
implements keyboard grid navigation through `gridRef` and
`focusDay('[data-day="…"]')` DOM queries.

None of this uses `createPortal` (0 occurrences) — the panels are positioned
with `fixed` inside the normal tree. That is *good* news for the port, but the
focus-trap logic is hand-rolled React and has to be rewritten as Svelte
actions, not translated.

### 8. Icons as data

`lib/nav.ts` stores `LucideIcon` **component references as values** in a plain
array, and `PagePlaceholder`/`SideRail`/`BottomNav` pull `const Icon = item.icon`
and render `<Icon />`. Polymorphic component-from-variable is idiomatic React
and needs the Svelte 5 equivalent decided once, since three components depend
on it.

### 9. Polymorphic `as` prop

`SectionHeading` takes `as: Tag = "h2"` and renders `<Tag>`. Used across the
calendar at `h2` and `h3`. Svelte has no direct equivalent for an arbitrary
element tag from a prop — it needs either a small `{#if}` ladder or
`<svelte:element this={as}>`.

### 10. `cva` + `tailwind-merge`

`class-variance-authority` appears only in `ui/button.tsx` and `ui/badge.tsx`,
both unused — so it can be dropped. `cn()` (`clsx` + `tailwind-merge`) is used
app-wide and has a straight port, but `tailwind-merge`'s conflict resolution is
relied on wherever a component takes a `className` override (which is most of
the primitives).

### 11. `next/font`, `next/link`, `next/navigation`

`next/font/google` in `layout.tsx` self-hosts both faces at build time and hands
back CSS variables that `globals.css` consumes. The port has to reproduce
*self-hosting with `display: swap` and pinned weights*, not just link Google
Fonts — otherwise the token system's `--font-sans`/`--font-mono` indirection
breaks. `next/link` (8 files) → `<a>`. `usePathname()` (`SideRail`,
`BottomNav`) → `$page.url.pathname`. `useRouter()` (`BookingArea`) →
`goto`/`invalidate`.

### 12. `metadata` / `viewport` exports

Every real route exports a `metadata` object, and the layout exports both
`metadata` (with a `%s · THRIVE` title template) and `viewport`. SvelteKit has
no declarative equivalent — this becomes `<svelte:head>` per route, and the
title template has to be reimplemented by hand.

---

## 9. Known defects

`REPORT.md` is present and was written at an earlier commit (`47ef0fc`; HEAD is
now `4e0a65b`). **Two of its four "new bugs" have since been fixed.** Verified
each against the current tree rather than taking the report at face value.

### Fixed since REPORT.md — do not port the old shape

| Defect | Status | Evidence |
|---|---|---|
| **Ticking a self-added task on the calendar silently did nothing.** `tickItem` resolved a row by slicing a prefix off `item.id` and searching `serverTasks`; tasks in `addedStore` and the agenda's synthetic undated to-dos were never found, so the guard returned, the checkbox appeared to tick, and it reverted on the next render. | **FIXED.** | `lib/tickItem.ts` now dispatches on the attached `item.task` / `item.quickItem`. `calendarSources.ts` attaches the resolved row at merge time. 6 tests in `calendarSources.spec.ts` cover it. |
| **`DaySection` count conflated tickable and total** — rendered `1/3` for one done task and two classes. | **FIXED.** | `DaySection.tsx:36-56` counts `tickables` and falls back to a bare total when nothing is tickable. |

**The lesson both encode, and the one rule to carry into the port:**
*never resolve a row by parsing its id.* Attach the resolved source object at
merge time. The id-parsing version failed silently — no error, no log, just a
checkbox that ticked and reverted.

### Still open — must NOT be reproduced

**1. Module-level server stores are shared by every visitor. — BLOCKING**
The three stores in `lib/data/mock/` are process-global. Several students
testing at once book over each other and see each other's appointments,
requests and resume versions. Everything resets on restart or hot reload.
`BUGS.md` graded this `ACCEPTED` when the only user was the author and
re-graded it **BLOCKING** on 2026-08-19 ahead of a control group.
*Port note:* the Django backend is the fix. But an adapter-node process has the
same module-scope hazard, so any interim mock in the port inherits the bug
verbatim.

**2. No auth on any server action. — HIGH**
All six actions in `src/app/*/actions.ts` are reachable by direct POST, not only
through the UI. Only `appointments/actions.ts:29` carries a comment saying so —
`BUGS.md`'s claim that all three files are commented is **wrong**, and
`REPORT.md` already corrected it. Deploying behind Tailscale narrows who can
reach them but does not close it.
*Port note:* SvelteKit form actions have exactly the same property.

**3. The Home Tasks card collapses at 375px. — HIGH, "the worst thing in the app"**
Every task title wraps to roughly one character per line, making Home ~7,700
CSS px tall. **Pre-existing, not restyle damage** — verified by stashing and
re-measuring (7,801px before, 8,256px after). Isolated to `TaskRow`; everything
below the Tasks card lays out correctly at that width.

**4. Twelve of thirteen page titles render at weight 400. — LOW**
Weight was taken out of the type scale on 08-15 and the `<h1>`s were never
updated. Verified: only `app/calendar/page.tsx:27` carries `font-bold`.
`app/page.tsx`, `career/resume`, `appointments`, `assignments`,
`degree/requests`, and `PagePlaceholder` (which serves 7 routes) all render 400.

**5. The "N" avatar overlaps the nav. — MEDIUM**
"Settings" in the desktop rail and "Home" in the mobile bottom bar, on **every**
route at **both** widths.

**6. Floating launchers cover page content. — MEDIUM**
The To-do and Ask THRIVE launchers overlap the second "Book" button on
`/appointments` and the right edge of cards on `/degree` at 375px.

**7. Empty states read as large grey slabs. — LOW**
A consequence of deleting the border as a structural device. Cosmetic.

**8. `cancelAppointment` releases a slot by matching start time. — LOW**
`providers.ts:252-260` iterates `claimedSlotIds` and releases the first slot
where `slot.start === appointment.start`, because slot ids are regenerated per
request. Correct with one advisor per service; **wrong the moment an advisor
publishes two simultaneous slots**, where it would release the wrong one.

**9. Stale `DegreeProgress.expectedCompletion`. — LOW**
Declared at `types.ts:286`, hardcoded `"Spring 2027"` at `mock/degree.ts:11`,
while `buildProgramTimeline` derives Fall 2027 for the same student. Verified
**rendered nowhere**, so nothing contradicts on screen. Prefer the timeline's
`expectedFinishTerm`; do not carry the field.

**10. `SquareGrid` ring offset assumes a white background. — LOW, visual**
`calendar/SquareGrid.tsx:75` uses `ring-offset-1` without setting
`ring-offset-color`. Tailwind's default is white. Correct today because the grid
only ever renders inside a white `.thrive-panel`; it will draw a white halo the
moment it sits on the cream page or a sunken fill.

**11. Provider boundary violation. — LOW now, a build break later**
`app/degree/requests/page.tsx:8` does
`import { requestTypeLabel } from "@/lib/data/mock/requests"` — reaching past
`@/lib/data` into a mock module. It is the **only** such import in the tree
(the other `lib/data/mock` matches are all comments). `requestTypeLabel` and
`requestTypeHelp` are presentation maps that live in a fixtures file; when the
mock modules are deleted for Django, this breaks the build.

### Found while reading, not in REPORT.md or BUGS.md

**12. `eventIdOf()` is not actually the single normaliser it is documented to be.**
`lib/ignoredEvents.ts:50` defines `eventIdOf()` and both CODEMAP and the
module's own doc comment call it *the* one place the `evt-` prefix is stripped.
Two other sites strip it inline instead:
- `lib/schedule.ts:442` — `item.id.replace(/^evt-/, "")` inside `isVisible`
- `lib/useIgnoreUndo.ts:62` — `eventId.replace(/^evt-/, "")` inside `isIgnored`

The regex and `eventIdOf`'s `startsWith`+`slice` are functionally equivalent for
a single prefix today, so there is **no live bug**. `schedule.ts` plausibly does
it inline to stay server-safe (importing `ignoredEvents.ts`, a `"use client"`
module, would poison it) — but `useIgnoreUndo.ts` already imports from
`ignoredEvents.ts` two lines above, so that one has no such excuse. This is
exactly the shape of the bug in defect 1: three copies of an id rule, and the
docs asserting there is one.

**13. `thrive:event-joins` is keyed on the calendar item id, not the raw `Event.id`.**
`DayEventsSection.tsx:148,159` calls `setEventJoined(item.id, …)` with the
calendar's id (`evt-evt-3-1`), whereas the ignore store deliberately normalises
to the raw `Event.id` for exactly this reason. Today the join store has **one
consumer**, so there is no disagreement — but if Home ever grows a "count me
in" button it will hold `event.id` (`evt-3-1`) and write to a different key,
producing the same two-stores-one-name bug the ignore store was refactored to
avoid.

**14. Custom event ids are double-prefixed.**
`calendarItems.ts:93` mints `custom-${createdAt}`, and
`customEventToItem:154` then builds the calendar item id as
`custom-${event.id}` — so item ids read `custom-custom-1755…`.
`deleteCustomEvent` correctly clears `custom-${id}` to match, so the label and
urgent overrides are cleaned up properly. Cosmetic and internally consistent;
noted because it is the same double-prefix pattern that caused the `evt-evt-`
confusion.

**15. `getStudent`, `getDegreeProgress`, `getAdvisors` and `getResources` return
fixtures by reference, not copies.** The store-backed providers all
`.map(x => ({...x}))` and the file's own comment says a caller "should never see
it change underneath them". These four do not. Nothing mutates them today, so
there is no live bug — but the boundary's stated contract is not uniformly
enforced.

**16. Three providers are dead code:** `getSyllabi()`, `getResources()`, and
`getCurrentResume()` are exported and implemented but called from no route or
component. `getSyllabi` backs a stub route (`/syllabi`); `getResources` backs a
stub route (`/resources`) and is named in `REPORT.md` as blocking the Resource
Navigator; `getCurrentResume` is superseded by `getResumeVersions().find(isCurrent)`,
which is what `career/page.tsx:12` and `ResumeWorkspace` actually do.

**17. `AssistantConversation` has no brain — by decision, not omission.**
It replies with a fixed line saying it cannot answer yet. The doc comment states
the rule: a placeholder that mimics a real answer teaches the student to trust
something that is not there. Carry the honesty, not just the component.

**18. Keyboard resizing of floating panels does not exist.**
`FloatingChrome.tsx` marks all eight resize grips `aria-hidden` and the comment
names this explicitly: *"keyboard resizing is a real gap, not a decision."*
Size is a preference and "Centre" restores the default, so nothing is
unreachable — but the gap is real and known.

### Documentation drift found during this inventory

Flagged because a port will read these files and be misled.

- **`CODEMAP.md`** says **83 tests** (correct) but the brief said 61; it also
  says **"12 read providers + 7 mutating"** = 19, and omits `getProgramTimeline`,
  `getMyAppointments`, `getRequestPrefill`, `getMyRequests`, `getTssConnection`,
  `getCurrentResume`. The real count is **25 functions + 1 class**.
- **`CODEMAP.md`** locates `todayKey()` alongside `describeDue()` under
  `format.ts`. It is in `buildSchedule.ts`.
- **`globals.css:151`** says of `--shadow-card`/`--shadow-lifted` that "six
  components still ask for them". **Zero do** — the sweep already removed them.
- **`globals.css:40`** says control boundaries "draw in `--thrive-faint`". True
  in effect (`--thrive-control-line: var(--thrive-faint)`), but the token a call
  site should name is `--thrive-control-line`.
- **`BUGS.md`** claims the no-auth issue is "marked with comments in all three
  action files". Only one of three has the comment.
- **`REPORT.md`** describes 4 spec files / 54 tests and two bugs that are now
  fixed. It is a snapshot of `47ef0fc`, not of HEAD.

---

## Appendix: commands and verification

Run during this inventory:

```
npm test                           → 5 files, 83 tests, all pass, 411ms
python3 scripts/check-contrast.py   → 43/43 pass
```

**Not run:** `npm run build`, `npx tsc --noEmit`, `npm run lint`. All three
write to disk (`.next/`, `tsconfig.tsbuildinfo`) and the brief restricted writes
to `MIGRATION.md`. Type-correctness and lint-cleanliness at HEAD are therefore
**unverified here**; `REPORT.md` §6 recorded all three clean at `47ef0fc`.

Every other claim in this document was read directly out of the source at
`4e0a65b`.
