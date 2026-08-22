# CHANGELOG

Dated session summaries, most recent first.

---

## 2026-08-21 (later) — Calendar chrome, an unreproducible bug, density, and the Key

**HEAD:** `3d38df1` · **640 tests · 213 interaction assertions · 51 layout targets ·
58 contrast assertions · six gates green · green in all seven timezones.** 116
commits, all pushed.

Four requests, four commits.

### `280cb2a` — the calendar page gets its gutter back

- `--container-wide` (96rem) **deleted**. `/calendar` had its own cap while every
  other route was on 80rem, which on a 1920px screen left the busiest page a 127px
  gutter against everyone else's 248px. Nothing else used the token.
- The eyebrow and the intro paragraph are gone; the page keeps its name. The view
  switcher moved onto the heading row.
- **The Key became a disclosure** rather than an 18rem column. Grid top 202 -> 169px
  and width 927 -> 1198px at 1512.
- This is the one change that makes something LESS discoverable. Paid for with a
  trigger that names the filter in words, a count whenever a filter is on, and the
  fact that nothing about reading the month depends on the legend.

### `e89c1a7` — "Your day" moves under the month, and the gate that lied

- **The reported bug does not reproduce.** All 42 cells drive the pane, in dev and
  in the build, both advisors, 1512/1280/900, in-month, trailing, and after paging.
- What DOES reproduce is the misreading, from two causes: the pane sat 270px above
  the grid that changes it (and off-screen at an 800px viewport height), and classes
  recur weekly so two Mondays show an identical row with only 11.25px of muted text
  distinguishing them. Order swapped; the date is now the pane's subject.
- **The assertion was the real defect.** It read "the first `<p>` in the pane" and
  checked only that its text changed -- never the list, and never an adjacent-month
  cell. See BUGS.md.

### `bd2c66a` — density, and the history rail

- **Neither suspect caused it.** The root is 93.75% at >=64rem and computes to 15px
  at both 1512 and 1920. `--spacing` at 0.25rem is a 3.75px step at that root,
  TIGHTER than stock Tailwind. The generosity was the step chosen per call site.
- Nav rail pitch 45 -> 39.38px; type unchanged at every step. Every compression
  scoped to `lg`+, and phone document heights are byte-identical before and after.
- The conversation rail became `.thrive-panel[data-tone="sunken"]` -- the nav rail's
  own treatment. Rows have a surface and a hairline at REST; the current one adds a
  2px navy stripe, same width on every row so the list does not shuffle sideways.

### `3d38df1` — the Key's streams are a column

- Eleven chips in four ragged rows -> eleven rows, dots in one column, `w-full` so
  the borders end together.
- Labels and the three view toggles moved BESIDE the streams, so the panel is the
  taller column (451px) rather than the sum. Internal scrolling was rejected: it
  would hide filters inside a panel that is already collapsed.
- The three toggles are stacked too. Judgement call, invited by the request.

### Still open

- **CONTEXT.md is four commits stale** and must be REGENERATED IN FULL, not patched.
  It still describes `--container-wide`, the Key as a column beside the grid, and
  "Your day" above the month.
- The Key panel is 451px at 1512 and 790px on a phone when open. Acceptable behind a
  disclosure; if it bites, columns for the streams list is the next lever.
- The history rail's new surface is the one change that reaches mobile (+6px on
  /ask at 390px). Deliberate: it was invisible there for the same reason.

---

## 2026-08-21 — Appointments, Ask THRIVE, three redesigns, and a Netlify deploy

**HEAD:** `81137b7` · **640 tests · 190 interaction assertions · 51 layout targets ·
six gates green · green in all seven timezones.** 110 commits, all pushed.

One long session covering two phases and four follow-on changes, three of which
partly reversed the one before. The reversals are recorded rather than tidied away,
because the reasons are the useful part.

### Phase 8 — `/appointments`

- The route is real: service cards, a day picker, the booking panel, "Your day",
  and the student's bookings.
- **Mutations are SvelteKit form actions**, the app's first POSTs. `load` re-runs
  after one, which is what makes a booking appear in "Your day" and the list with
  nothing to keep in sync by hand.
- MIGRATION §8.5's adjust-during-render **dissolved rather than porting**: with one
  owner for the day there is nothing to reconcile.
- The day picker went chips → month grid → day list → chips. See HANDOFF.

### Phase 9 — `/ask`

- Three destinations, saved history, a chat window with no brain, and 27 providers
  (up from 25). **Chat history cannot live in `localStorage`** — too large, and a
  second laptop would show an empty history indistinguishable from never having
  asked — so it is provider data from the start.
- The URL is the state: a redirect from `/ask`, the destination as a route segment,
  the conversation as a search param, and 404s for both kinds of nonsense.
- The destinations later moved into the NAV rail as a disclosure group, and the
  page kept a history rail.

### The four follow-on changes

1. **Booking flow measured and rearranged**, then reverted to the chip strip.
2. **Ask THRIVE's destinations into the nav rail**, `nav.ts` grew `children`.
3. **The page container**: 72rem → 96rem → 80rem plus a 40px gutter and a
   `/calendar`-only 96rem. Two knobs, because a gutter alone does not solve 2560px
   and a cap alone does not solve 1512px.
4. **The month grid on `/appointments` became clickable**, moving "Your day" only.

### Deployed

`@sveltejs/adapter-netlify` added; **`adapter-node` kept**, selected by
`ADAPTER=node`, because the two browser gates spawn a real server. `netlify.toml`
is committed at the repo root with `base = "frontend"`, so the deploy is
reproducible from a clone rather than from a dashboard.

### Known issues

- **The mock stores are process-global**, MIGRATION §9 defect 1, BLOCKING. On
  Netlify a cold start also wipes them, so a booking made yesterday is probably
  gone. Recorded in the README, because it looks like data loss and is not.
- **Form actions have no auth check** and are reachable by direct POST (§9 defect
  2).
- Ask THRIVE **has no brain** and says so.

### Next priorities

1. The real-phone pass, now four items.
2. `/assignments` — the same `TaskRow` with no `reorder` prop.
3. The retrieval service behind `/ask`, and the Django work the stores need.

---

## 2026-08-21 — session close: the last inert control

**HEAD:** `99fd968` · 563 tests · six gates green · green in all seven timezones ·
89 commits, all pushed.

### What changed

- **Home's "Add to calendar" is live.** `icsFromEvent` is a second mapper rather
  than a shared one — two genuinely different input shapes needing different
  fallbacks, with the one rule they share asserted on both. **No inert control is
  left anywhere in the app.**
- **The gate reads the `.ics` rather than catching the download** (92 → 97). The
  output is consumed by software, so the assertions are about content: one valid
  VCALENDAR, the right event, a real DTSTART, and a UID on the raw `Event.id`.
- **The README states a Node floor** (20+) instead of the version it happens to be
  developed on.
- CONTEXT, CODEMAP, CONVENTIONS, TESTING, setup_info, FINDINGS, HANDOFF updated.

### Known issues

None new. Teal and amber remain at their gamut ceiling; the real-phone list has
gained a third item.

### Next priorities

`/assignments`, then Appointments. The real-phone pass whenever a handset is to hand.

---

## 2026-08-21 — 7c follow-ons: Home's join, the dots, and the doc pass

**HEAD:** `e743232` · 6 commits · 558 tests · six gates green · green in all seven
timezones. `check:interaction` 84 → 92.

### What changed

- **Home's "count me in" is live**, inert since 6a because the join key space was
  unsettled. 7c settled it; this wires it. The register copy moved to
  `messages.common.events` now that two live surfaces share it.
- **The join round trip is gated**: join on the calendar, navigate to Home, the same
  event says so.
- **The month grid's dots**: 6px → 8px via a new `--thrive-cal-dot`, and five status
  tokens gained chroma at fixed lightness. **Size did more than colour.**
- **CONTEXT.md regenerated in full** after three calendar phases of drift.
- **No personal names in any doc** — CONVENTIONS rule 8. Eight replaced with roles.
- **README rewritten** for a cold arrival, around a guide to the eleven docs.

### Known issues

- **Teal and amber cannot be made more vivid** without moving lightness, which the
  contrast floor forbids. Recorded so it is not rediscovered.
- **Home's "Add to calendar" is still inert** — now the only one left.
- The agenda has no add form, and that is settled rather than pending.

### Next priorities

`/assignments`, then Appointments. The real-phone pass now has a second reason.

---

## 2026-08-21 — Phase 7c: the calendar's editing surfaces

**HEAD:** `5b636f6` · 8 commits · 558 tests (was 507) · six gates green · green in
all seven timezones. **The calendar is complete.**

### What changed

Three components, three supporting pure modules, one action, one primitive.

- **`ItemDetail`** — a dialog with everything about one item plus every edit
  control. Focus moves in, is trapped, and returns; Escape and an outside press
  dismiss; delete asks first, with the safe control in the destructive one's old
  position and holding focus.
- **`AddItemForm`** — a task, a to-do or a custom event, routed to three different
  stores. The routing lives in `calendarAdd.ts` so a gate can see it.
- **`DayEventsSection`** — "Happening, register". Join, leave, .ics, ignore.
- `calendarEvents.ts`, `calendarAdd.ts`, `ics.ts`, `actions/focusTrap.ts`,
  `ui/UnIgnoreButton.svelte`.
- `check:layout` extended to the week and agenda views (36 → 42 assertions).
- `check:interaction` extended to the calendar (60 → 84 assertions).

### The decision this phase was given

**`thrive:event-joins` keys on the raw `Event.id`**, matching the ignore store. It
was keyed on the calendar item id — the same defect fixed in the ignore store in
7a, in a second store, invisible because it had one consumer. Decided with that
consumer in front of us: one row offers join and ignore side by side, Home's
inert "count me in" already holds `event.id`, and a join is a fact about an event
rather than about a row on a day. Three key spaces still, not four. Old keys go
stale and are left; no migration.

### The 7a gap is closed

Every day in the month with anything on it now shows a figure equal to the rows
beneath it — 36 days checked in a browser, 14 of them with events, and again after
an add.

### PRs merged

None. Direct to `main`, as ever: `22f6a7d` `f6dd1a9` `0d98632` `d6c96c0` `caf61ab`
`af7fb53` `f74150f` `5b636f6`.

### Known issues

- **`ItemDetail` threw on close with focus in the label field.** Found and fixed
  the same session, by the interaction gate. A prop is a getter, and the parent
  nulls it before the subtree is torn down. See BUGS.
- **Focus did not return to the opener** after a pointer-opened dialog. Fixed.
- **`AddItemForm` and `DayEventsSection` are absent in agenda view**, matching the
  source: the agenda spans thirty days and has no single selected day to add to.
- **Home's "count me in" is still inert.** The key space is settled and wiring it
  is now a one-line change on each side, left to the phase that owns Home.
- **CONTEXT.md is owed.** §14 still describes 7c as pending. It is regenerated in
  full rather than patched, so it is a job of its own.

### Next priorities

CONTEXT.md; wiring Home's join button; the real-phone list (touch drag, the month
grid's 44px cells).

---

## 2026-08-21 — session close: CONTEXT regenerated after two phases

**HEAD:** `bac3fbf` · 15 commits this session · 507 tests · six gates green · green
in all seven timezones.

### What changed

Docs only. CONTEXT.md regenerated in full — read first, all 1,769 lines, because
regenerating a file that size from partial knowledge would drop standing decisions
from phases 1–6.

It gained **a new §14 for the calendar**, which is the second-largest surface in the
app and had no section at all. Gates → 15, standing decisions → 16, voice → 17,
loose ends → 18, timeline → 19, with every cross-reference re-checked.

setup_info.md: the stale test count, and **the timezone sweep documented for the
first time** — it has caught two real failures and had no entry in the "how to run
things" doc, which is how it went unrun against one spec for weeks.

### Known issues

Nine things the regeneration caught. Six were stale facts; **three were
forward-looking claims that had come true differently** and had quietly become false
assertions about the present — `nowMinutes()` described as the calendar's clock read
when the calendar declined it, the "next up" line described as `arriveAtRow`'s third
caller when it never became one, and the ignore store described as normalising
through `eventIdOf()` when the fix was that it normalises nothing. In FINDINGS,
because a patch is structurally unable to catch that class.

### Next priorities

7c: `ItemDetail`, `AddItemForm`, `DayEventsSection`, the `thrive:event-joins` key
space with its consumer on screen, and `check:layout` extended to the week and
agenda views.

---

## 2026-08-21 — 7b follow-on: the week breakpoint moves to 48rem

**507 tests · six gates green · green in all seven timezones.**

### What changed

`sm` → `md` on the week-to-agenda fallback. 40rem measured at **71px columns** —
clamped correctly and still reading as three short stacks rather than a phrase.
48rem gives **89px**, with about 75px of text per title, enough for whole words.

Re-measured at eight widths: 769px and 768px render seven columns, 767px and below
fall back to the agenda with its note. Zero horizontal overflow everywhere, titles
still capped at three lines, no console output.

The rule that came out of it, now in CONVENTIONS: **pick a breakpoint by measuring,
not by naming a size**, and the knob is always the breakpoint — a min-width puts
back the horizontal scroll the fallback exists to remove.

### Also settled

- `check:layout` extension to week and agenda: **approved for 7c.**
- Agenda rows naming their own date: **kept.** Improving on a source that is simply
  wrong beats porting the mistake — the second such case in two phases.
- All nine of 7b's absence decisions approved.

### Known issues

Unchanged: CONTEXT.md still not regenerated (after 7c, by decision), `check:layout`
still blind to two of three views until 7c, `thrive:event-joins` still queued.

---

## 2026-08-21 — Phase 7b: the other two views and the filter bar

**507 tests · six gates green · green in all seven timezones.**

`/calendar` now has all three views and a working filter. 7c is editing, the
detail dialog, the add form and the events section.

### What changed

- **`ViewSwitcher`** — month / week / agenda as a radiogroup, plus the
  agenda-only grouping select.
- **`WeekView`** — seven columns, compact rows, no checkboxes. No min-width and no
  horizontal scroll, because the fallback is what guarantees the room.
- **`AgendaView`** — a flat grouped list over 30 days, and the only view that can
  carry undated to-dos.
- **`KeyBar`** — the key and the filter, with streams and labels kept structurally
  apart.
- **`calendarViews.ts`** — `agendaRange`, `showsRowDate`, `undatedTodoItem`,
  `visibleUndatedTodos`. 20 tests.
- **`ItemRow`** gained `compact` and an optional `dateLabel`.
- **The 40rem week→agenda fallback**, in CSS. It did not exist in the Next source.

### Fixed while building

- **`line-clamp-3` was doing nothing** beside `block` — a 71px week column rendered
  a course title 140px tall, seven lines instead of three. Nothing warns about an
  unclamped clamp.
- **The agenda's rows now name their own date** when grouped by type or course. The
  prototype rendered all three groupings identically, so thirty days of rows each
  read "9:30 AM" with nothing saying which.
- **`urgentOnly` now hides undated to-dos**, which can never be urgent. It used to
  empty the page except that one section.
- **TESTING.md's coverage table was three specs short and three counts stale.** It
  sums to 507 across 23 rows now.

### Known issues

- Week columns are 71px at the 40rem breakpoint. Readable, tight; the breakpoint is
  the owner's call and is recorded with the measurement.
- **`check:layout` only ever visits `/calendar` in month view**, so week and agenda
  are unvisited by every gate. Covered by hand at five widths; recommended for a
  gate in 7c.
- **CONTEXT.md is still not regenerated**, by decision — after 7c.

### Next priorities

Phase 7c: `ItemDetail`, `AddItemForm`, `DayEventsSection`, and the
`thrive:event-joins` key space with its consumer finally on screen.

---

## 2026-08-21 — Phase 7a: the calendar's spine

**487 tests · six gates green · green in all seven timezones.**

`/calendar` renders for the first time: the month grid, the selected day, and that
day's items. Month view only — 7b brings the other two views and the filter bar,
7c brings editing and events.

### What changed

- **`buildScheduleData()` ported**, the gating piece since Phase 2. Five providers
  in one `Promise.all`; classes stay weekday RULES so the grid pages to any month
  without a round trip. `nowMinutesAt(now)` added beside it.
- **`/calendar/+page.server.ts`** — one load, one `new Date()`, three values off
  it: `todayKey`, `nowMinutes`, `nowISO`. Tasks fetched here and deliberately not
  merged here.
- **Eight components** under `lib/components/calendar/`: `CalendarView` (the only
  stateful node), `MiniCalendar`, `CalendarHeader`, `SquareGrid`, `DaySection`,
  `DayGroupToggle`, `ItemRow`.
- **`calendarDay.ts`** extracted out of two components, because logic in a
  `.svelte` file is logic no gate can see. 20 tests.
- **The ignore store's HIGH key-space defect fixed.** Canonical key is the raw
  `Event.id`; the store normalises nothing it is handed. Its defect-record test is
  replaced by a real cross-surface one.
- **MIGRATION §9 defect 10 built correctly:** `SquareGrid` uses `outline`, not
  `ring`, so there is no offset colour to get wrong on cream.
- **A pre-existing timezone bug in `reveal.spec.ts` fixed** — found by running the
  sweep, which had never been run against that file.

### Known issues

- A day's figure counts events that have no row until 7c. Deliberate; BUGS.md
  records why the two alternatives are worse.
- `MiniCalendar`'s keyboard grid has no gate. Verified by hand; see HANDOFF.
- Ignore keys written under the old shape are inert, so one ignored event
  reappears once.
- **CONTEXT.md is not regenerated** and its `updated-at` is behind.

### Answered after the report

All four closing questions came back and are settled in HANDOFF: CONTEXT.md is
regenerated **after 7c**, `thrive:event-joins` is handled **in 7c** with its only
consumer on screen, the day-figure gap **stands** pending the owner seeing it, and
375px joins touch drag on a real-phone list.

### Next priorities

Phase 7b: `ViewSwitcher`, `WeekView`, `AgendaView`, `KeyBar`.

---

## 2026-08-21 — session close: answers, and the road after Home

**HEAD:** `bfa0ac3` · 11 commits this session · 451 tests · six gates green.

Four open questions closed by the owner: `COLLAPSED_TASK_ROWS` stays at 4,
`/calendar` keeps its card link, `/classes` stays link-less for good, and
`Toast` having no caller is expected.

### Next priorities

1. **The calendar** — 15 components, the largest surface. `buildScheduleData()`
   is still unported and gates it.
2. **`/assignments`**, then **Appointments**.
3. **Ask THRIVE as a full page** — scoped, not built. A *second left rail* beside
   the nav rail holding Resources, Course Recommender and Career, plus a chat
   window and saved history. **Replaces the earlier tabs-on-top idea.** Chat
   history cannot live in `localStorage`.
4. **Group Projects** — scoped, not built. A fifth nav item, and the first
   surface that is not one student's private view: needs real accounts and a
   shared database.

### Known issues

Both scoped features move Django onto the critical path — neither can be demoed
on the mock layer at all.

---

## 2026-08-21 — copy-to-list follows the surface that shows it

**HEAD:** `5e6b3d1` · **451 tests** · check 0/0 over 389 files · build clean ·
contrast **58/58** · layout **36/36** · interaction **60/60**

The copy-to-quick-list control worked and persisted, but the quick list lives in
the floating To-do panel behind `FEATURES.floatingTodo`, so the task was copied
somewhere the student cannot see. Gated on that flag — visibility only, nothing
deleted, and flipping one word restores a byte-identical row.

**The control strip is right-anchored now (`ms-auto`).** Above `sm` it already
was; below `sm` it wrapped to its own line LEFT-aligned, so removing the leading
control slid the others 49px left — and expanding a card did the same in reverse.
A pre-existing shift that gating one control exposed. Edit now sits at x=244 on a
phone whether the flag is on or off.

**Measured, not claimed:** phone row heights and page height identical; on
desktop one of four rows is 20px shorter, because the content column gains 46px
and that row's chip line stops wrapping. Card bodies stay 300px.

### What broke

The gate assertion I wrote for this was **vacuous on the first attempt**. It
inferred the flag from the page by looking for a To-do launcher, and the selector
matched the copy button's own accessible name — so it read the thing it was
gating as proof the gate was open, and passed with the guard removed. The flag is
parsed from `features.ts` now.

### Known issues

- With the button hidden, `showToast` has no caller, so the mounted `Toast`
  cannot fire. Coherent (both return on the same flag) but unexercised outside
  its tests.

---

## 2026-08-21 — two follow-ons: honest disclosures, honest links

**HEAD:** `df72ad1` · 2 commits, both pushed · **451 tests, 20 files, all green**
· `svelte-check` 0/0 over 389 files · build clean · contrast **58/58** · layout
**36/36** · interaction **59/59**

### Each show-more control governs its own region

Both disclosures on the Tasks card declared `aria-controls="tasks-card-list"` —
the whole list, including the done group neither of them expands. Each announced
to a screen reader that it expands something it does not, and it had trapped the
interaction gate twice while 6b was being written, because "the control for the
open list" had to be disambiguated by document order.

`#tasks-open-list` and `#tasks-done-list` now exist, each named by exactly one
control. Two new assertions: no two controls claim the same region, and every
claimed region resolves.

### A card links out only when its destination is built

Three of Home's four cards pointed their "View all" at parked routes that render
a title and a note. `isBuiltRoute(href)` asks `primaryNav`, and `SectionCard`
withholds the link when the answer is no — so **building a route restores its
links with no further edit**, and no card carries its own opinion.

Lost their link: Tasks, My Classes, Upcoming Events. Today's classes keeps
`/calendar`.

`isKnownRoute` separates "parked on purpose" from "mistyped", because both fail
`isBuiltRoute` and only one of them should be silent. A dev warning covers the
other.

### Known issues

- Desktop is pixel-identical (bands 67/103px, page 1218px). On a phone the Tasks
  band is 22px shorter — its description regains the link's width and sets on one
  line instead of two. A horizontal reflow, not the button's height.
- `/calendar` keeps its card link while its own body is still a note. It is in
  `primaryNav`, and the rail already links there.

### Next priorities

The calendar. `/classes` is unlikely to be built at all; its route and card stay,
unlinked.

---

## 2026-08-21 — Phase 6b: task editing is live

**HEAD:** `5cdad70` · 4 commits, all pushed · **439 tests, 19 files, all green**
· `svelte-check` 0/0 over 388 files · build clean · contrast **58/58** · layout
**36/36** · interaction **55/55**

### What changed

Everything deferred from 6a. Ticking with undo, inline rename, `PriorityPicker`,
`TaskNotes`, `DueDateEditor`, copy to the quick list, drag and keyboard reorder,
and `AddTaskForm`. The persistence layer already existed from 3b, so this phase
wired the UI to stores that were already built and tested.

New pure module `taskBoard.ts` (the editing half of the Next `useTaskBoard`),
`homeGroups` gained the order overrides, `taskView` gained `rowPriorityLabel`,
and ~60 new strings went into `messages.ts`. `Toast.svelte` was built and mounted
in `AppShell` — its store had shipped in 3b with no consumer, and 6b's
copy-to-list is the first caller.

`+page.svelte` now resolves the task rows ONCE and hands the same array to the
stat pills and to the Tasks card, so an edited due date cannot leave a pill
counting the server's stale answer.

### The undo arrival, settled

One `tick()` is enough — but only because `undoTick` makes every state write,
including expanding the card, before calling `arriveAtRow`. The flush count is
not the mechanism; the ordering is. Measured both ways in a real browser: with
the expansion moved into an effect, the hidden-row case lands nowhere, marks
nothing, and logs **no warning in the production build**. Now a gate assertion,
which is the loud failure that was asked for.

### Bugs found and fixed

- **Every date converter threw a RangeError on a "Needs a date" row.** Latent in
  the Next source and made reachable by 6a surfacing those rows. Reproduced
  against the Next source before fixing.
- **`dragend` on a dropped row read a destroyed block's derived** —
  `derived_inert`, present in the production build with all six gates green.
  Found by dragging by hand; the card now owns drag cleanup.
- **Defect 3 nearly returned twice.** Measured at 375px mid-build: the title box
  was 90px, wrapping over three lines at six characters a line.

### Known issues

- The collapsed Tasks card now scrolls ~124px inside its fixed body: a desktop
  row is 61–81px rather than 54px, because five 44px controls cannot be shorter.
  The grid still cannot move. `COLLAPSED_TASK_ROWS` at 3 would fit — owner's call.
- Reordering is offered only when the card is expanded, since collapsed is a flat
  slice spanning groups and sort keys are read per group.

### Next priorities

`/assignments`, which renders the same `TaskRow` — the first consumer of the
`role="list"` contract the row now requires.

---

## 2026-08-21 — click only, an arrival cue, and check:interaction

**HEAD:** `aadfca9` · 6 commits, all pushed · **389 tests, 18 files, all green**
· `svelte-check` 0/0 over 374 files · build clean · contrast **58/58** · layout
**36/36** · interaction **37/37**.

### What changed

**Hover removed from the stat pill popovers. Click only.** Tried and rejected:
three pills in one row meant a cursor crossing it opened and closed panels nobody
asked for. `openedBy: 'pointer' | 'command' | null` existed only to reconcile the
two ways in, so it collapsed back to `open`. `hoverIntent.ts` deleted with its
only caller. `clickOutside` and `escapeKey` stay.

**The jump is visible.** `arriveAtRow` marks the revealed row with an indigo inset
ring, solid for most of 1200ms then faded. Indigo is the reserved "you are here"
colour; an outline is the one treatment that cannot move the layout, does not
contest the priority wash a task row already carries, and fits both row shapes
from one rule. The ring is declared and the animation only removes it, so
`prefers-reduced-motion` still gets a visible mark that still clears.

**`npm run check:interaction`** — 37 assertions in a real browser, and the first
gate in the repo that can press a button. Verified to fail three ways.

**`designSystem.spec.ts` now scans `.ts`** as well as markup for the treatment
vocabulary, because `.thrive-arrived` is applied from JavaScript.

**`arriveAtRow` promoted to the standard** way anything on Home reaches a row, and
moved to `$lib/arrive`. Splits "I know which row" from "something else has to find
it", and stops DOM code living in a `.svelte.ts` that declares no runes.
CONVENTIONS gains the rule and the two cases that are NOT arrivals. No behaviour
change.

**`arriveAtRow` warns in dev** when the row it was sent to is absent, naming the
id. Not a throw — a student never sees an exception over a wayfinding cue. No gate
covers the branch (the gate drives a production build), so it was verified by hand
against `vite dev`; the gate now fails on console warnings regardless, with a note
at the assertion saying what it cannot see.

**`CONTEXT.md` regenerated in full** at `d3621b9`, then patched in four spots for
the `arrive` split. Sections 5, 6, 7, 13, 14, 15 and 17 all moved.

### Known issues

- `/swatch` does not show the popover or the arrival ring. Left alone by decision:
  it is slated for deletion before Release 1.
- `check:interaction` covers one widget on one page, by decision. Component tests
  in general are still an open question.
- `CONTEXT.md` was patched rather than regenerated for the `arrive` split. Four
  spots, grep-verified, flagged in HANDOFF.

### Next priorities

1. Phase 6b — task editing.
2. Then the calendar, which needs `buildScheduleData()` ported.

---

## 2026-08-21 — the stat pill popovers, and a reveal channel

**HEAD:** `ae48473` · 3 commits, all pushed · **389 tests, 18 files, all green**
· `svelte-check` 0 errors / 0 warnings over 375 files · build clean · contrast
**58/58** · layout **36/36** · 27 browser assertions over the interaction.

### What changed

**The three stat pills on Home now open the list behind the number.** Click
always; hover also, on a device that has a cursor. Items jump to the task or the
event, expanding the card first if the row is collapsed behind "show more".

**A reveal channel, owned by the page.** `$lib/reveal.ts` (pure, tested) plus
`$lib/reveal.svelte.ts` (the channel, in page context). A pill REQUESTS a reveal;
each card decides whether the request is about one of its rows and sets its own
collapse state. No card's state is written from outside, and `ShowMore` is
untouched. Context rather than a module singleton, so collapse still resets on
navigation because of where the channel lives.

**`escapeKey` finally has a caller**, alongside two new siblings:
`clickOutside` (with an `alsoInside` list, because a disclosure's trigger is not
inside its panel but is inside its widget) and `hoverIntent` (which holds the one
`(hover: hover)` gate).

**Upcoming Events gained a show-more, reversing a deliberate decision.** The
events pill counts 21 events this week; the card showed the next four upcoming,
so 17 of the popover's items had no row on the page. Collapsed is still four,
expanded is the week, `/events` is still the rest.

**`weekEventIds` replaced by a `thisWeek` flag on each event row.** Two shapes of
one fact were travelling down; one flag answers both and cannot drift.

**A zero-count pill is not a control** — no button, no `aria-expanded`, nothing
to press.

### Known issues

- **`CONTEXT.md` is stale at `f8593b7`.** It is regenerated in full by rule, not
  patched, so it was left for a deliberate pass rather than half-updated.
- Home's phone height grew 2878 → 2949px: 44px touch targets on the pills plus
  the new footer band. Desktop is unchanged at 1238px.
- Nothing in the popover's interaction is covered by `npm test`, which does not
  render. The 27 browser assertions were a throwaway probe, not a gate.

### Next priorities

1. Regenerate `CONTEXT.md`.
2. Decide whether the browser probe becomes a real gate.
3. Phase 6b — task editing.

---

## 2026-08-21 — Phase 6a, Home; the navy repalette; the nav trim

**HEAD:** `f8593b7` · 10 commits, all pushed · **373 tests, 17 files, all green**
· `svelte-check` 0 errors over 368 files · build clean · contrast **58/58** ·
layout **36/36**.

> Date note: the previous entry and several `app.css` comments are stamped
> 2026-08-22, a day ahead of the real date. Commit hashes are the reliable
> ordering; the dates in this repo are ±1 day.

### What changed

**Design system — repaletted to the campus brand.** Primary moved from forest
green to **UC San Diego navy `#182b49`** (PMS 2767) with **UC San Diego Yellow
`#ffcd00`** (PMS 116) as an accent, both official values from
`brand.ucsd.edu/visual-brand/color`. Gold `#c69214` was measured at 2.79:1 and
rejected. Yellow is 1.50:1 on card, so it is decoration on light surfaces and a
real graphic only against navy (9.45:1) — enforced by three new ceilings rather
than a comment. One reserved colour changed value: `on-track` blue → teal
`#14706b`, because a blue status chip beside a navy button repeats the collision
that moved it off green in the first place.

**The two-face type rule, tightened** to "DM Sans for words, JetBrains Mono for
numbers only", expressed as `.thrive-numeric` and `.thrive-eyebrow`. Mono had
spread to eyebrows, switchers, chips and tags — a face used for a third of the
interface is not an accent.

**The contrast gate now parses `app.css`** instead of mirroring it by hand. That
weakness was load-bearing: 43 assertions were checking the green palette while
the app rendered navy.

**Navigation trimmed to four**: Home, Calendar, Appointments, Ask THRIVE. The
other seven plus Settings moved to a `parkedNav` list no surface renders. `/ask`
added as a placeholder route. The mobile More sheet was removed entirely.

**Phase 6a — Home is built.** `+page.server.ts` awaits six providers in one
`Promise.all` and calls `new Date()` once; every date is classified server-side.
Four cards in a 2×2 grid, ten new UI primitives, nine Home components, a
`messages.ts` module holding every user-facing string.

**The fit-on-one-screen behaviour.** Card bodies take a fixed height on desktop
and scroll inside, so expanding moves nothing; on mobile the cap comes off and
cards push down. Cap derived by driving a real browser, not by arithmetic.

**Two density passes.** Home's header block went 375px → 266px with nothing
removed (strip and greeting merged into one panel, the date onto the greeting's
line, pills and chips into one row). The top bar went 56px → 48px above `lg` via
a media override on `--thrive-topbar-height`, with controls stepping 44px touch →
36px pointer.

**Undated tasks are visible.** An unparseable due date now gets its own group,
first, headed "Needs a date".

### PRs merged

None. All 10 commits went direct to `main`, solo, no review gate.

### Known issues

- **Home fits a 1238px viewport, not 1052px.** The remaining 186px is card rows,
  not density. Decided: do NOT cut rows; "show more" exists for that.
- The three mock stores are still process-global (§9 defect 1, BLOCKING).
- Provider copies are still shallow.
- Upcoming Events scrolls at rest by design (`VISIBLE_EVENTS = 4`).

### Next priorities

Stat pill popovers, then **Phase 6b: task editing** (ticking, undo, rename,
priority, notes, due date, drag to reorder, add task), then the calendar,
appointments, and the Ask THRIVE page.

---

## 2026-08-22 — Phase 5, the data layer

**HEAD:** `0dcca16` · 4 commits, all pushed · **324 tests (277 pre-existing,
unmodified), 12 files, all green** · `svelte-check` 0 errors · build clean ·
contrast 43/43.

### What changed

- **All 25 providers** ported to `frontend/src/lib/data/providers.ts` with
  signatures verified identical to the Next source by mechanical diff, plus
  `SlotUnavailableError`. **Against the same mock fixtures**, not against
  Django — no HTTP client, no API layer, nothing invented against a backend
  that does not exist yet.
- **13 fixture modules** under `data/mock/`. Eight are byte-identical to the
  source; the other five differ only in comments, except `degree.ts`.
- **The three module-level stores** with their lazy seeding, their id
  generators, and the id-collision hazard now documented at the generator
  rather than in a migration doc.
- **`data/latency.ts`** — the 120ms delay behind `setMockLatencyMs`, which can
  be set to 0. Kept, not deleted: it exists so a route that forgot its loading
  state looks wrong in development instead of only in production.
- **`data/labels.ts`** — `requestTypeLabel` / `requestTypeHelp` moved onto the
  public side of the boundary.
- **`stubProviders.ts` deleted.** The root `+layout.server.ts` changed one
  import path and nothing else.
- **`providers.spec.ts`** — 47 tests.

### Four §9 defects fixed rather than reproduced

| # | Defect | Fix |
|---|---|---|
| 8 | `cancelAppointment` released a slot by matching start time | `Appointment.slotId`; the release is one exact delete |
| 11 | `degree/requests/page.tsx` imported a label map from `lib/data/mock/requests` | Both maps moved to `data/labels.ts` |
| 15 | Four providers returned fixtures by reference | All 25 return copies |
| 9 | `DegreeProgress.expectedCompletion` hardcoded "Spring 2027" vs a derived Fall 2027 | Field dropped from the type and the fixture |

### Known issues

- **§9 defect 1 (BLOCKING) is inherited intact.** The stores are process-global.
  Django is the fix; an `adapter-node` process has the same hazard.
- **Copies are shallow.** Pushing onto a returned version's nested `skills`
  array still reaches the store. Pinned by a test that says so.
- **§2 overstates `buildSlotsFor` determinism.** Availability folds in a clock
  read. Documented at the function.
- **`requestTypeHelp` has no consumer** anywhere in the Next tree.

### Next priorities

`buildScheduleData()` — the five providers it needs now exist. Then the route
`load` functions and the view models.

---

## 2026-08-21 — repo created, SvelteKit port through Phase 4

### What changed

- **`MIGRATION.md`** — inventoried the frozen Next prototype at `4e0a65b`. 1,449
  lines, nine sections: routes, all 25 providers, date handling, 75 components,
  the design system, 14 stores, all 83 tests, React-specific decisions, and ten
  known defects.
- **Repo created** — `rsm-msaad/thrive`, private. Monorepo layout: `frontend/`,
  `backend/` (empty), `scripts/`.
- **Phase 1** — SvelteKit scaffold (Svelte 5 runes, TS strict, `adapter-node`,
  Tailwind v4, Vitest) and the design system ported to `app.css`. Fonts
  self-hosted via `@fontsource`. `/swatch` built as a visual diff target.
- **Phase 2** — the pure logic and all 83 tests. `localDayKey` collapsed into
  `dayKeyOf(value: Date | string)`. `CONVENTIONS.md` written.
- **Phase 3a** — 73 tests for `format.ts`, which had none.
- **Phase 3a-fix** — input guards on `describeDue` and `formatClockTime`.
  `DueDescriptor` became a 4-state discriminated union.
- **Phase 3b** — the browser persistence layer ported to Svelte 5 runes. 102
  tests pinning four properties.
- **Phase 4** — app shell, navigation, root layout, 13 routes.
  `hydrateStores()` wired. Floating widgets gated behind `FEATURES`.

### Commits merged

13, all direct to `main`, no PRs (solo, no review gate yet):

```
93d921d chore: repo skeleton, the migration map, and the palette gate
dec84d4 feat: scaffold the SvelteKit frontend
1d7932b feat: port the design system from the Next app
8e5b395 feat: port the domain types and the pure calendar logic
336b555 test: port all 83 pure-logic tests
be4d545 docs: state the timestamp rule that the framework no longer enforces
4215885 test: cover format.ts, describeDue above all
adf11d0 fix: guard describeDue and formatClockTime against malformed input
4812f4b feat: port the browser persistence layer to Svelte 5 runes
89d4311 test: pin the four store properties, and record an ignore-store defect
83e18ce feat: nav config, feature flags, and the shell's supporting modules
33d7a72 feat: app shell, root layout, and the one store hydration point
b0f7c3b feat: a route for every nav destination
```

### Gates

| Gate | Result |
|---|---|
| `npm test` | **277 passed** (11 files) |
| `npm run check` | **302 files, 0 errors, 0 warnings** |
| `npm run build` | clean, `adapter-node` |
| `scripts/check-contrast.py` | **43/43** |
| Timezone sweep | 277 passed in 7 zones, UTC+14 → UTC−11 |

### Known issues

- **Ignore store key-space split.** Home and the calendar key it differently, so
  ignoring an event on one surface does not affect the other. Pre-existing in the
  prototype; found by a new cross-surface test. Recorded as a defect test, not
  fixed — the canonical key affects already-stored data.
- **An `urgency: "unknown"` row matches no group** in a list grouped by
  overdue/today/upcoming. Accepted: the discriminated union turns it into a
  compile error rather than a silent drop.
- **A parseable-but-wrong date still passes `describeDue`** — V8 rolls
  `"2026-02-30"` into March rather than rejecting it.
- **`formatShortDate` can still emit `"Invalid Date"`** — the last unguarded
  function in `format.ts`.
- **No year in `formatShortDate` / `fullLabel`**, and `countdownPhrase` counts to
  "13 months". Both parked as product decisions pending real screens.

### Next priorities

1. Phase 5 — the 25 data providers, against Django.
2. Shared primitives (`Button`, `Card`, `Tag`, …), built at the correct border
   weight rather than inheriting the prototype's 20 `border-2` call sites.
3. Decide the ignore store's canonical key, fix it, promote the defect tests.
4. Re-set Release 1 scope and dates against the rebuild.
