<!-- built-at: 81137b7 -->
<!-- updated: 2026-08-21 -->

# CODEMAP

Navigation map for the THRIVE rebuild. Read this before opening files.

**Built:** 2026-08-21, refreshed at `81137b7` — after Phases 8 and 9, the two
appointments redesigns, the Ask THRIVE rework, the page-width pass, and the
Netlify deploy.
**Size:** 179 files under `frontend/src` — ~30,755 lines, 22,458 source / 8,297 test.

> The `built-at` comment above is machine-read by the codemap staleness hook.
> Keep it as the first line, in that exact `<!-- built-at: <hash> -->` form.

---

## Read these first

| File | Why |
|---|---|
| `CONTEXT.md` | The snapshot. What this is, where the port has got to, every standing decision. |
| `MIGRATION.md` | The spec. The frozen Next prototype, inventoried in nine sections. |
| `CONVENTIONS.md` | Eight rules the tooling does not enforce. Review is the enforcement. |
| `HANDOFF.md` | The diary. What happened last session and what is still open. |

---

## The one rule that explains most of the code

**Components never see a raw timestamp.** Dates are classified and formatted in
a `load` function and passed down as strings. In Next the `"use client"`
boundary enforced this at compile time; SvelteKit has no such wall, so it is now
convention. `CONVENTIONS.md` says what to grep a diff for.

This is why `describeDue()` keeps its `now` parameter, why `nowISO` is a prop,
and why the `*View` types exist.

---

## Entry points

| Path | What it is |
|---|---|
| `frontend/src/routes/+layout.server.ts` | Root load. The only place `getStudent()` is called. |
| `frontend/src/routes/+layout.svelte` | Imports `app.css`, mounts the shell, and is **the one place `hydrateStores()` runs**. |
| `frontend/src/app.css` | **Design tokens. Single source of truth.** Start here for any styling question. The layout ones are `--container-page` / `--container-wide` / `--container-measure` / `--thrive-page-gutter-x` — four separate questions, never solved with each other. |
| `frontend/src/app.html` | Document shell. Carries the light-only meta tags. |
| `frontend/vite.config.ts` | **Adapter CHOICE** (netlify by default, node under `ADAPTER=node`), runes mode, and the Vitest projects. **There is no `svelte.config.js`.** |
| `netlify.toml` | At the REPO ROOT, because that is where Netlify reads it and the only place `base = "frontend"` can be declared. |

---

## The pure layer — `frontend/src/lib/`

No framework surface, and all of it under test. Mostly ported in Phase 2;
`buildSchedule`'s body and `calendarDay` landed in 7a, `calendarViews` in 7b, and
`calendarEvents` / `calendarAdd` / `ics` in 7c.

| File | Role |
|---|---|
| `data/` | **The provider boundary.** Its own section below. Import from `$lib/data`, never deeper. |
| `format.ts` | Server-side formatting. `describeDue()` is the important one — returns a 4-state discriminated union. |
| `schedule.ts` | **The calendar's vocabulary.** Category maps, the three category sets and their guards, grid arithmetic, `filterSchedule`/`isVisible` (the one filter), grouping, `nextUpItem`. Read this first for anything calendar-shaped. |
| `buildSchedule.ts` | **The server half of the calendar's data.** `buildScheduleData()` reads five providers and returns two shapes: dated rows, and classes as weekday RULES so the grid pages to any month without a round trip. Plus `todayKey()` and `nowMinutesAt(now)`. `load` functions only. |
| `calendarDay.ts` | **The selected day's arithmetic**, extracted out of the components in 7a so a gate can see it: `sortDayItems`, `arrangeDay`, `squareGroupsFor`, `dayCountParts`, and the `SquareCell`/`SquareGroup` shapes. |
| `calendarViews.ts` | Its 7b sibling, for questions about a VIEW rather than a day: `agendaRange` (thirty days, anchored on today), `showsRowDate`, `undatedTodoItem`, `visibleUndatedTodos`. |
| `calendarSources.ts` | `taskToItem`, `todoToItem`, `mergedSchedule()`, `nowMinutes()`. **`nowMinutes()` still has no consumer** — the calendar takes its "next up" clock from the server; see `routes/calendar/+page.server.ts`. |
| `calendarItems.ts` | Custom events, labels, urgent. Keyed by **calendar item id**. `labelFor`/`urgentFor` are the ONE resolution rule, shared by the merge and the dialog. |
| `calendarEvents.ts` | **The calendar's event boundary.** `dayEventRows` sheds the `evt-` prefix once and hands the raw `Event.id` back with each row, for the join AND ignore stores. `DayEventsSection`'s only arithmetic. |
| `calendarAdd.ts` | **Three kinds, three stores.** `addCalendarItem` is the whole of `AddItemForm` that can be wrong invisibly, so it lives out here where a gate can see it. |
| `ics.ts` | The `.ics` export. `buildIcs` is pure and takes its `DTSTAMP` instant as an argument; `downloadIcs` reads the clock at the boundary. `icsFromItem` is one mapper for both callers. |
| `availability.ts` | **What an advisor has open, as arithmetic.** Two count maps (open, and published-at-all — the pair is what tells "full" from "not a working day"), the ordered day keys, the soonest bookable day, and one day's slots by mode. Clock-free, and it takes no "today" at all any more. |
| `appointmentsView.ts` | The booking surface's view models, `REASON_MAX`, `toBookingDayViews` (the chips) and `toAppointmentView` — **the ONE mapper** the load function and the booking action share. |
| `ask.ts` | **Ask THRIVE's vocabulary and its only date arithmetic.** `ASK_DESTINATIONS` (one list, like `nav.ts`), the route guard, `relativeDayLabel`, the view models, `showsDayLabel`. |
| `calendarPrefs.ts` | `normalisePrefs` + the persisted store. |
| `ignoredEvents.ts` | `eventIdOf()`, `canIgnore()`, and the store. Keyed on **raw `Event.id`**, and it now normalises **nothing** it is handed — the calendar sheds its own prefix at its boundary. That was the HIGH defect fixed in 7a. |
| `tickItem.ts` | `tickItem()` and `isTickable()`. Dispatches on the **attached source row**, never by parsing an id. |
| `quickList.ts` | The scratch list: `QuickItem` plus its store and panel store. |
| `reveal.ts` | **"Show me the row behind this number", as arithmetic.** `planReveal` is the one question a card asks. Read this before touching the popovers. |
| `arrive.ts` | **`arriveAtRow` — the ONE way any surface moves a student to a row.** Focus, scroll, and the arrival mark. Awaits one `tick()` and **warns in dev** when the row is not there. Never hand-roll a `scrollIntoView`; see CONVENTIONS. |
| `nav.ts` | **One TREE drives the rail, the bottom bar, and every stub page.** `children` nests Ask THRIVE's three subjects; `flattenNav` is what keeps `allNav` and `isBuiltRoute` DERIVED rather than maintained beside it, so a child cannot exist in the rail and be missing from the lookup. Originally: **one list drives the rail, the bottom bar, and every stub page** — and now whether a card links out at all. `isBuiltRoute` asks `primaryNav`; `isKnownRoute` separates "parked on purpose" from "typo". |
| `features.ts` | `FEATURES` — both floating widgets off. **`floatingTodo` also gates the task row's copy-to-list control**, since the quick list is the only place a copy is visible. |
| `title.ts` | `pageTitle()` — Next's `"%s · THRIVE"` template. |
| `utils.ts` | `cn()`. Survives for the `class`-override case only. |

---

## The data layer — `frontend/src/lib/data/`

**This is the seam.** 3,551 lines. Ported in Phase 5 against the same mock
fixtures the Next app uses — there is no HTTP client and no Django here. Django
replaces the provider *bodies* later; the signatures are the contract and do not
move.

| File | Role |
|---|---|
| `index.ts` | **The only public entry.** Re-exports `types`, `providers`, `labels` and nothing else. |
| `types.ts` | Every domain type. One file, on purpose. Dates are ISO **strings**, never `Date`. |
| `providers.ts` | **The 25 functions + `SlotUnavailableError`.** Every one returns a Promise. Every one returns copies. |
| `labels.ts` | `requestTypeLabel`, `requestTypeHelp`. Public because they are labels for a closed union, not mock data. |
| `latency.ts` | `resolveAfterDelay` + `setMockLatencyMs`. **Private.** The 120ms exists to surface missing loading states. |
| `mock/relative-dates.ts` | **The clock every fixture reads.** `at`, `onDay`, `upcomingWeekday`, `startOfToday`, `SUN`–`SAT`. |
| `mock/appointments.ts` | Advisors, `buildSlotsFor`, and **store 1** (appointments + claimed slots). |
| `mock/requests.ts` | **Store 2.** Lazy `seedOnce` — one approved `req-000`. |
| `mock/resume.ts` | Skills, resume courses, experience, and **store 3**. Lazy seed, `nextId` starts at 4. |
| `mock/program.ts` | `buildProgramTimeline` — pure, fully parameterised including `now`. The finish line is derived. |
| `mock/{student,courses,assignments,tasks,events,syllabi,degree,resources}.ts` | Pure fixtures. Byte-identical to the Next source except `degree.ts`. |

### Three things to know before touching it

1. **`mock/` and `latency.ts` are not exported from `index.ts`.** A component
   that needs something from either has found a gap in the provider surface.
   Widen the surface; do not reach through it. The Next tree violated this
   exactly once (MIGRATION.md §9 defect 11) and it is fixed here, not carried.
2. **The three stores are module-scope objects**, shared by every visitor and
   wiped on restart. MIGRATION.md §9 defect 1, graded **BLOCKING**. Inherited
   deliberately; Django is the fix. Tests get isolation via `vi.resetModules()`,
   not via a production reset hook.
3. **Nothing here is random.** Slot availability and the events calendar are
   hashed, not sampled — `Math.random()` would desynchronise server from client.
   A test scans the whole directory to keep it that way.

---

## Home — `frontend/src/routes/+page.server.ts` + `lib/components/home/`

The dashboard, and the only editable surface. Read Phase 6b's entry in HANDOFF
before changing it. (`/calendar` is built too, as of 7a — its own section below.)

| File | Role |
|---|---|
| `routes/+page.server.ts` | **Six providers in one `Promise.all`, and the only `new Date()` on this page.** Every date is classified and formatted here. |
| `routes/+page.svelte` | Owns the reveal channel **and** calls `resolveRows` ONCE, feeding the same array to the stat pills and to the Tasks card so they cannot disagree. |
| `home/HomeHeader.svelte` | One panel holding the strip and the greeting. Exists to save a panel's padding and a stack gap. |
| `home/ProgramTimelineCompact.svelte` | The program strip. Bare, not a panel. |
| `home/GreetingPanel.svelte` | Greeting, standing sentence, and ONE row of pills + chips. |
| `home/TaskStatPills.svelte` | The three counts, and the three lists behind them. **Reads the stores**, so the counts see the student's own ticks and ignores. Each pill's number IS `items.length` of the list it opens. |
| `home/TasksCard.svelte` | **Flat when collapsed, grouped when expanded.** The one real design decision in 6a. Owns ticking, undo, drag/keyboard reorder, and the add form. Reordering is offered **only when expanded** — see its doc comment. Also answers the reveal channel by writing its own collapse state, never anyone else's. |
| `home/TaskRow.svelte` | One task, fully editable. Tick, rename, priority, note, due chip, copy-to-list (behind `FEATURES.floatingTodo`), move. The control strip is **right-anchored**, so a conditional control appears at its leading edge and nothing already on screen moves. **Controls wrap to their own line below `sm`**, and the title takes a line of its own — both halves of the 375px fix. |
| `home/UndoBar.svelte` | The way back from a tick. Fixed at the top of the list, deliberately **not** a live region. |
| `home/AddTaskForm.svelte` | Quick add, collapsed to one button. Title is the only required field. |
| `home/DueDateEditor.svelte` | The due chip as a button opening a native date input plus three shortcuts. Uses `clickOutside` + `escapeKey`. |
| `home/PriorityPicker.svelte` | Three radios, not a select. Deliberately uncoloured by its own value. |
| `home/TaskNotes.svelte` | One task's note. Draft local, committed on blur, on close, and on destroy — never per keystroke. |
| `home/TodaysClasses.svelte` · `MyClasses.svelte` · `CourseCard.svelte` | Today's meetings; the course list; one course. |
| `home/UpcomingEvents.svelte` · `EventRow.svelte` | **Filters ignored FIRST, then slices to four.** The order is the behaviour. Collapsed is four, **expanded is this week** — see the doc comment for the contradiction that forced it. |

### The pure layer behind it

| File | Role |
|---|---|
| `messages.ts` | **Every user-facing string.** Values are functions, not templates. Extract into this as each surface is built. |
| `homeView.ts` | View models. Every date field is already a formatted string. |
| `homeGroups.ts` | Grouping, counting and ordering. `unknown` is a real group, FIRST. The read-only half of the Next `useTaskBoard`. |
| `taskBoard.ts` | **The editing half.** `resolveRows` (edits over provider truth, reclassified), the date arithmetic, `reorderedIds`. `DatedGroupKey` makes "you cannot drop into Needs a date" a type error. |
| `collapse.ts` | The fit-on-one-screen rule as arithmetic, shared by four cards. |
| `cardLayout.ts` | The collapsed row COUNTS. The height cap is CSS — see `app.css`. |
| `taskView.ts` | `rowPriorityOf`, `taskLabels`. Deadline outranks stated priority. |
| `tones.ts` | Every place a meaning becomes a colour. |
| `programStrip.ts` | `abbreviateTerm`, `phaseStatusWord`. |
| `ignoreUndo.svelte.ts` | Ignore + six-second undo. Keys on **raw `Event.id`**, never a stripped prefix. |
| `reveal.svelte.ts` | **The reveal channel**, created by `+page.svelte` and passed down through context. Carries an intent, one slot at a time, with a nonce. The channel only — arriving is `$lib/arrive`. |

---

## The calendar — `routes/calendar/` + `lib/components/calendar/`

**Complete.** 7a built the spine, 7b added the other two views and the filter bar,
7c added the three editing surfaces.

| File | Role |
|---|---|
| `routes/calendar/+page.server.ts` | `buildScheduleData` + `getTasks` in one `Promise.all`, and **the only `new Date()` on this page** — `todayKey`, `nowMinutes` and `nowISO` all come off it. Tasks are fetched here and deliberately **not merged** here. |
| `routes/calendar/+page.svelte` | A header and one mount point. No reveal channel: the calendar has no collapsed rows for anything to ask about. |
| `calendar/CalendarView.svelte` | **The only stateful node.** Owns `selectedKey`, `monthKey`, `detail`. Merges, then applies `filterSchedule` **once**, and hands the filtered data to every child. |
| `calendar/MiniCalendar.svelte` | The month grid. Up to 3 category dots per day plus `+n`, a roving tabindex, arrows / Home / End / PageUp / PageDown. **The two client-side date formats CONVENTIONS accepts by name live here.** |
| `calendar/CalendarHeader.svelte` | The day's summary: big figure, breakdown, `n of m done`, the "next up" line, and the square strip. |
| `calendar/SquareGrid.svelte` | A day's items as squares. Re-exports `SquareCell`/`SquareGroup` from `calendarDay`. **Uses `outline`, not `ring`** — MIGRATION §9 defect 10 built correctly. |
| `calendar/DaySection.svelte` | One titled group. **Its count is `done/TICKABLE`**, bare total when nothing is tickable. That was a fixed bug; the doc comment says so. |
| `calendar/DayGroupToggle.svelte` | Arrange the day by type (default) or time. Writes `dayGroupBy`. |
| `calendar/ViewSwitcher.svelte` | month / week / agenda as a `radiogroup`, plus the **agenda-only** grouping select. |
| `calendar/WeekView.svelte` | Seven columns, compact rows, **no checkboxes**. Not rendered below `48rem` — see rule 4 below. No min-width and no horizontal scroll, deliberately. |
| `calendar/AgendaView.svelte` | A flat grouped list over 30 days. **The only view that can carry undated to-dos**, which is why it exists. Rows name their own date when the grouping is not by day. |
| `calendar/KeyBar.svelte` | The key AND the filter. **Two dimensions that never merge** — see rule 3 below. |
| `calendar/ItemRow.svelte` | One item in the shape every view renders it. Numeric tabular time, sans title, a real checkbox on tickable rows, and the details control — which **focuses itself before opening**, so the dialog has somewhere definite to put focus back. Never in the week column. |
| `calendar/ItemDetail.svelte` | **The dialog.** Everything about one item plus label, urgent and delete. Focus in / trapped / returned, Escape and outside-press dismissal, a two-step delete. **Latches its row at mount** — see the gotcha below. |
| `calendar/AddItemForm.svelte` | Add a task, a to-do or a custom event. Markup only; the routing is `calendarAdd.ts`. |
| `calendar/DayEventsSection.svelte` | "Happening, register". Join, leave, `.ics`, ignore. Its own section because opting in is a different act from ticking off. |

### Three things to know before touching it

1. **`filterSchedule` is applied in exactly one place.** A dot on a day with no
   row beneath it is structurally impossible, not something to remember. A new
   consumer gets the filtered `ScheduleData`; it does not filter again.
2. **Ticking dispatches on the attached source row**, never on a parsed id.
   `mergedSchedule` puts the resolved `Task` / `QuickItem` on the item and
   `tickItem` reads it. `isTickable` asks the same question the checkbox does.
3. **`KeyBar`'s two dimensions never merge.** STREAMS are a fixed list in
   `legendOrder`; LABELS are open-ended, from `allLabels` on the UNFILTERED merge.
   Separate headings, separate lists, separate prefs fields (`hidden` /
   `hiddenLabels`), separate helpers (`toggleCategory` / `toggleLabel`). Nothing
   iterates a merged array, so an edit cannot flatten them by accident. The labels
   coming from the unfiltered merge is load-bearing: filtered, hiding a label would
   remove its own chip and there would be no way back.
4. **The week fallback is CSS at `48rem`, and the Next source never had it.** Two
   media-gated wrappers, not a `matchMedia` read — a viewport question CSS can
   answer belongs in CSS, and a JS read would have to guess during SSR. Boundary
   measured at 768px (week, 89px columns) / 767px (agenda + a note saying why).
   **48rem rather than the 40rem the Next comment names**, because 40rem measured
   at 71px and read as three short stacks. The knob is the breakpoint, never a
   min-width.
5. **The header's figure and the rows beneath it agree, as of 7c.** For two phases
   a day could read "5" above three rows, because the figure counts events and
   nothing rendered them. `DayEventsSection` closed that, and `check:interaction`
   walks every day in the month with anything on it and asserts the two match.
6. **`eventIdOf` is called in exactly one place in the calendar**, `calendarEvents.ts`.
   Both event-scoped stores — joins and ignores — key on the raw `Event.id`, so one
   row must never hold two ids for one event. See CONVENTIONS.

---

## Appointments — `routes/appointments/` + `lib/components/appointments/`

**Built in Phase 8, then redesigned twice and reverted to the original shape.**
Read the HANDOFF entry before changing it — the day picker has been a chip strip,
a month grid, a day list, and a chip strip again, and the reasons matter.

| File | Role |
|---|---|
| `routes/appointments/+page.server.ts` | **The load AND the app's only two form actions.** One `new Date()`; today and tomorrow come off it. `book` catches `SlotUnavailableError` into a 409; `cancel` returns 404 for an id no longer on file. |
| `routes/appointments/+page.svelte` | Header, `BookingArea`, and the student's bookings. |
| `appointments/BookingArea.svelte` | **The only stateful node**, and it owns TWO days: `bookingDay` (the chips and the times) and `browseDay` ("Your day"). See below. |
| `appointments/ServiceCard.svelte` | One advisor. The open count is why it is more than a name. Carries `data-service`, the hook both browser gates use. |
| `appointments/BookingPanel.svelte` | The whole form: the chip strip, meeting type, times, reason, confirm, and the confirmation it becomes. |
| `appointments/MyDayPane.svelte` | Classes and appointments only, and it SAYS so. Reads `browseDay`. |
| `appointments/MonthBrowser.svelte` | The clickable month under "Your day". `MiniCalendar`, unmodified. |
| `appointments/AppointmentList.svelte` | One cancel form per row, so it works with no JavaScript. |

### Four things to know before touching it

1. **TWO days, and the coupling runs ONE WAY.** A chip moves both (seeing what a
   slot collides with is why "Your day" exists); the month grid moves only
   `browseDay` (looking at next Thursday is not changing your mind about Tuesday).
   The gate asserts the negative half — after a grid click the pressed chip and the
   rendered times are byte-identical.
2. **The window IS the fixture.** `bookingDays()` publishes 5 business days and the
   strip shows those five. There is no separate one-month rule any more; it existed
   only while a month grid could show days the fixture had not published.
3. **`publishedByDay` beside `availabilityByDay`** is what tells a fully-booked
   Tuesday from a Saturday. Both have an open count of zero.
4. **`ORIGIN` is required by the NODE build** — these are the app's only POSTs, and
   without it every one is a 403. Not needed on Netlify. See `setup_info.md`.

---

## Ask THRIVE — `routes/ask/` + `lib/components/ask/`

**Built in Phase 9**, then the destinations moved into the navigation rail and the
page got a history rail. New design, not a port — the Next tree has no equivalent.

| File | Role |
|---|---|
| `routes/ask/+page.server.ts` | A 307 to a destination. `/ask` has no page of its own. |
| `routes/ask/+layout.server.ts` | The history, loaded ONCE for the section so switching destination does not rebuild it. |
| `routes/ask/+layout.svelte` | The `h1`, the mobile destination band, the history rail, and a slot. |
| `routes/ask/[destination]/+page.server.ts` | Validates the slug (404, never a redirect) and resolves `?c=` — including 404ing a real conversation opened under the WRONG destination. |
| `routes/ask/[destination]/+page.svelte` | A mount point, keyed on the conversation so an unsent question cannot appear under another title. |
| `ask/AskHistory.svelte` | **The history rail.** A column above `xl`, a horizontal strip below it. One tree, CSS only. |
| `ask/DestinationTabs.svelte` | The three destinations for widths with no nav rail. `lg:hidden`, driven by the SAME `primaryNav` children. |
| `ask/ChatWindow.svelte` | The log, the per-destination empty state, and the composer. |

### Four things to know before touching it

1. **The destinations are in `nav.ts`, as `children` of the `/ask` item.** The rail
   renders them as a disclosure; `flattenNav` is what keeps `allNav` and
   `isBuiltRoute` derived from the tree rather than maintained beside it.
2. **There is no chat store, deliberately.** Conversations come from providers. A
   sent message lives in component state and is gone on navigation, and the page
   says so BEFORE you type. `check:interaction` asserts sending writes no
   `localStorage` key.
3. **`--thrive-chat-height` is what makes the LOG the scroller**, and `flex-1` on
   the panel is gated on `xl` — in a column it would govern height instead and
   silently beat the token. That shipped once; a SKIP caught it.
4. **The phone gets one rail.** The nav rail is `hidden lg:flex`; the history rail
   flips to a strip below `xl`.

---

## The shared primitives — `lib/components/ui/`

`Tag` · `Button` · `ProgressBar` · `EmptyState` · `SectionCard` · `ShowMore` ·
`StatPill` · `StatPopover` · `StatusBadge` · `DueChip` · `IgnoreButton` ·
`UnIgnoreButton` · `IgnoreUndoBar` · `Toast`

`UnIgnoreButton` is `IgnoreButton`'s twin down to the last utility, because they
share a slot and swap on one boolean. Only the calendar has one: Home is a
recommendation feed and dismissing there is permanent by design.

`Toast` is the app-wide confirmation line, mounted once in `AppShell`. It had no
consumer until 6b's copy-to-list, which is why it is new here and the store is not.

`StatPill` has two shapes and one look: given `items` it is a **button owning a
popover**, given none it is a plain chip. A zero count gets the chip, on purpose.

`StatPopover` opens on **click only**. It tracked *why* it was open
(`'pointer' | 'command' | null`) while it also opened on hover, and it had to —
with one boolean, pressing the pill did nothing at all. Hover was then rejected
outright and that state went with it. See FINDINGS.

`SectionCard` is the one to understand: three bands — header, capped body,
pinned footer. It also **withholds its "View all" when the destination is a parked
route**, so no card can send a student to a placeholder; the header row carries a
`min-h-11` floor so the band cannot shrink when the link is absent. The footer sits OUTSIDE the scroll area because the show-more
control must not scroll away with the content it controls.

---

## The gates

| Command | What it proves |
|---|---|
| `npm test` | **640 tests.** Pure logic and source scans. Nothing renders. |
| `npm run check:interaction` | **190 assertions** in a real browser: the popovers, 6b's editing, 7c's calendar, the booking surface (including a two-page double-booking RACE), Ask THRIVE, the nav disclosure, and the page measure. **The only gate that can press a button**, and the only one that measures a layout. Fails on a console warning too — but it drives the PRODUCTION build, so it cannot see `arriveAtRow`'s dev-only warn. **Builds its own adapter-node server first**, so it cannot measure a stale one. |
| `npm run check` | Types agree. **Does NOT prove the page renders** — see BUGS.md. |
| `npm run build` | It compiles. |
| `python3 scripts/check-contrast.py` | 58 assertions. **Parses `app.css`**, so tokens cannot drift from their checks. |
| `npm run check:layout` | **17 targets x 3 viewports** in a real browser (**builds its own adapter-node server first**): the page cannot scroll further than it paints. The calendar counts three times — its view is a persisted preference, not a URL. Skips if no browser. |

---

## The persistence layer

**`.svelte.ts` means the file declares runes.** Svelte only processes them
there; a plain `.ts` with `$state` is silently inert.

| File | Role |
|---|---|
| `overrideStore.svelte.ts` | **The one mechanism.** `createOverrideStore<T>(key)` + `hydrateStores()`. |
| `userEdits.svelte.ts` | 7 keys — done, joins, titles, priorities, dues, order, added — plus `taskToggle` and its one app-wide undo slot. |
| `taskNotes.svelte.ts` | Its own store. Notes are not an override of anything. |
| `toast.svelte.ts` | One transient slot, 3000ms, not persisted. |
| `floatingPanel.ts` | `createPanelStore(key)` — geometry for a floating panel. |
| `assistantPanel.ts` | That store's Ask THRIVE instance. |
| `testing/fakeStorage.ts` | **Test-only.** A `localStorage` stand-in, so the suite stays in Node with no jsdom. |

Four properties and three key spaces: see `CONTEXT.md` §8.

---

## The shell — `frontend/src/lib/components/`

| File | Role |
|---|---|
| `shell/AppShell.svelte` | The persistent frame. Skip link, rail, header, `main`, bottom bar, gated widget mount points. |
| `shell/SideRail.svelte` | Desktop rail, hidden below `lg`. One recursive `railLink` snippet, so a nav item and its CHILD render through the same code. An item with `children` is a **disclosure**: the link navigates, a separate button carries `aria-expanded`/`aria-controls`, and collapsing REMOVES the children from the DOM. |
| `shell/BottomNav.svelte` | Mobile bar. Four fixed slots + a More sheet. |
| `shell/TopBar.svelte` | Sticky header. Identity left, bell and avatar right. |
| `PagePlaceholder.svelte` | Body for unbuilt routes. **Throws** on an href absent from `nav.ts`. |
| `SectionHeading.svelte` | Mono eyebrow + bold title + mono count. `as` → `<svelte:element>`. Ported, no call sites yet. |
| `Avatar.svelte` | Image with an initials fallback. Hand-rolled; shadcn-svelte is later. |
| `actions/escapeKey.ts` | Svelte action. Escape-to-dismiss, scoped to the element's lifetime. **Callers: `StatPopover`, `DueDateEditor`, `ItemDetail`.** |
| `actions/clickOutside.ts` | Its sibling. Capture-phase `pointerdown`, with an `alsoInside` list for the trigger that opened the thing. **Callers: `StatPopover`, `DueDateEditor`, `ItemDetail`.** |
| `actions/focusTrap.ts` | The third. Move focus in, keep it in, put it back — one action because they are one contract. Queries the focusable set LIVE on every Tab, since a dialog's controls can change while it is up. **Caller: `ItemDetail`.** |

---

## Routes — `frontend/src/routes/`

15 route files. **Four destinations are built**, six are `PagePlaceholder`, one is the swatch.

**One route is settled as never-to-be-built:** `/classes` keeps its route and its
Home card but will not be built (owner) — the card IS the feature.

| Route | State |
|---|---|
| `/` | **Built.** The dashboard, and editable. |
| `/calendar` | **Built and complete (7a–7c).** Three views, the filter bar, the detail dialog, the add form, and the day's events. |
| `/appointments` | **Built.** Service cards, a chip strip day picker, the booking panel, "Your day", and a clickable month beneath it. **The app's only form actions.** |
| `/ask` · `/ask/[destination]` | **Built.** A history rail, a chat window with no brain, and three destinations that live in the NAV rail as a disclosure group. `/ask` redirects to a destination. |
| `/classes` `/syllabi` `/events` `/resources` `/settings` `/assignments` | `PagePlaceholder` |
| `/degree` `/career` | Placeholder body. Both are *partial* in the prototype and need providers. |
| `/swatch` | **Throwaway.** Every token, type step, border weight, both faces. Delete before Release 1. |

---

## Tests — 640, 29 files

`npm test`. Vitest, **Node environment, no jsdom**, so nothing renders.

**Which is why the popovers' interaction has no test.** Nothing in the suite can
press a button, and the one real bug in that feature was invisible to all five
gates. It was found by driving the built page in Playwright by hand. See the note
in TESTING.md.

It is also why Phase 7a **extracted `calendarDay.ts` out of two components**:
logic left in a `.svelte` file is logic no gate can see.

| Spec | Holds down |
|---|---|
| `format.spec.ts` (92) | `describeDue` across every branch, field and boundary; both private helpers via their public surfaces; both DST transitions |
| `providers.spec.ts` (47) | The provider boundary: **27** providers, copies out, no randomness, the three stores |
| `ask.spec.ts` (32) | The destination guard including near misses; `relativeDayLabel` across month, year and leap boundaries and at both ends of a day; the view models carrying NO raw instant; `showsDayLabel`; and the conversation providers' copies, order and nulls |
| `availability.spec.ts` (20) | The two count maps and **the pair they form** — a Saturday and a fully-booked Tuesday are both zero open, and only `publishedByDay` separates them; `orderedDayKeys` across a year boundary; `firstBookableDay` skipping a full first day |
| `appointmentsActions.spec.ts` (13) | The throw becoming a VALUE: both 409 sentences, the 400 and the 404, the truncation the markup cannot be trusted for, and cancel releasing the slot it was booked against |
| `taskBoard.spec.ts` (43) | `resolveRows` identity and reclassification, the date converters including every unparseable-date path, `reorderedIds` |
| `calendarStores.spec.ts` (42) | Prefs, quick list, annotations, `tickItem`, the three key spaces, and **the cross-surface ignore test** |
| `schedule.spec.ts` (27) | Grid arithmetic, filtering, grouping, the collapsed `dayKeyOf` |
| `userEdits.spec.ts` (28) | Property 4 one setter at a time, added tasks, the undo slot, the join store keying on exactly what it is handed |
| `calendarAdd.spec.ts` (18) | Each kind in its own store **and in neither other**; day and time per kind; the annotations on the item id; what it refuses |
| `ics.spec.ts` (18) | CRLF, UTC stamps, the four escaped characters, the stamp as an argument, a row with no instant, and **both mappers against the one rule they share** |
| `calendarEvents.spec.ts` (8) | The prefix shed once; **the stored key, read as a literal**; the same key as the ignore store from the same row; the cross-surface read |
| `ignoredEvents.spec.ts` (22) | Id normalisation **and what it mangles**, eligibility, month-dot arithmetic |
| `overrideStore.spec.ts` (21) | All four store properties |
| `calendarDay.spec.ts` (20) | The day's arithmetic: the re-sort across two slices, `DAY_GROUPS` order, squares that never mark a class done, "1 class" not "1 classes" |
| `calendarViews.spec.ts` (20) | The agenda's 30-day range across month, year and leap boundaries; when a row names its own date; the attached source row on an undated to-do; urgent-only emptying that section |
| `homeGroups.spec.ts` (19) | Grouping, counting, ordering; `unknown` first |
| `calendarSources.spec.ts` (18) | The mappers, and that each item carries its source row |
| `reveal.spec.ts` (16) | `planReveal` at the boundaries; the reveal path against the list `TasksCard` really builds; the event prefix argument |
| `taskView.spec.ts` (15) | `rowPriorityOf`, `taskLabels`; deadline outranking stated priority |
| `buildSchedule.spec.ts` (13) | Classes stay weekday rules; every dated row's `dayKey` agrees with its own `startISO`; the `evt-evt-` double prefix; nothing the server built is tickable |
| `collapse.spec.ts` (13) | The fit-on-one-screen arithmetic |
| `taskNotes.spec.ts` (13) | Hydration, corrupt input, forget-on-empty |
| `nav.spec.ts` (21) | The two lists disjoint and duplicate-free; **`flattenNav` and the children**; `isBuiltRoute` exact rather than prefix and true for a nested destination; `isKnownRoute` separating parked from mistyped |
| `calendarPrefs.spec.ts` (11) | Defaults and migration |
| `calendarItems.spec.ts` (16) | Custom-event mapping and its attached source row, `labelFor`/`urgentFor`, label and urgent filtering |
| `toast.spec.ts` (6) | The single slot and its clock |
| `programStrip.spec.ts` (5) | `abbreviateTerm`, `phaseStatusWord` |
| `designSystem.spec.ts` (4) | No hex, no font names, no undefined `.thrive-*`, over a corpus proved non-empty |

**Two tests are defect records**, named as such, pinning current behaviour rather
than desired behaviour. There were three; the ignore store's was **replaced by a
real cross-surface test in 7a** when the defect was fixed. See `BUGS.md`.

---

## Gotchas

**This SvelteKit version has no `svelte.config.js`.** Adapter and compiler
options are in `vite.config.ts`.

**`$state` in a plain `.ts` file does nothing.** It must be `.svelte.ts`.

**`hydrateStores()` runs in exactly one place** — the root layout's `$effect`.
Do not add a second path.

**Nothing in the store layer may be read during server rendering.** There is no
`localStorage` in a node process, so it will be empty rather than wrong — but a
component that assumes personalised data on first paint will be wrong.

**`border-line-strong` is a colour, not a width.** The 1.5px control stroke is
`--thrive-control-stroke` and the alias does not bring it along.

**`font-semibold` synthesises.** Only 400/500/700 load.

**Never resolve a row by parsing its id.** `calendarSources` attaches the
resolved `Task` / `QuickItem`; `tickItem` dispatches on that. The id-parsing
version failed silently for self-added tasks and undated to-dos.

**`eventIdOf` is ambiguous by construction** — the raw `Event.id` is itself
`evt-`-prefixed, so the function cannot tell a raw id from a calendar item id.
**Its input is a calendar item id and nothing else.** The store normalises nothing
it is handed; the calendar sheds its own prefix at its boundary. Calling it on a
raw id does not normalise, it mangles — that was the HIGH defect fixed in 7a, and
BUGS.md records both halves.

**A control with two ways in has more states than it has booleans.** `StatPopover`
had to record which input opened it while hover and click both existed, or they
undid each other. Hover is gone and so is that state — but the lesson is why
`check:interaction` asserts hover has NOT come back.

**`.thrive-arrived` is applied from TypeScript, not markup.** It is the reason
`designSystem.spec.ts` now scans `.ts` as well as `.svelte` for the treatment
vocabulary.

**Asking is not doing.** `$lib/arrive` is "I know which row"; `$lib/reveal.svelte`
is "something else has to find it". Two modules on purpose, and only the second
declares runes.

**`arriveAtRow`'s one `tick()` is enough only if you make it enough.** Settled in
6b: write EVERY state change — including expanding the card — before calling it.
The flush count is not the mechanism; the ordering is. A caller that unticks and
then lets an effect expand the card arrives at a row that does not exist yet, and
fails with no warning in production. `TasksCard.undoTick` is the worked example.

**A date that will not parse throws on the way out.** `new Date('nope').getHours()`
is NaN and the resulting Invalid Date raises on `toISOString()`. Every converter in
`taskBoard.ts` guards it, because "Needs a date" exists precisely so a student can
fix such a row.

**A handler on a row that a drop destroys reads a dead derived.** `dragend` after
a cross-group drop fires on a torn-down `{#each}` block; reading a prop there is
Svelte's `derived_inert`. The CARD owns drag cleanup, via a document listener that
lives exactly as long as the drag.

**`ShowMore` carries `aria-expanded` too.** Anything querying
`button[aria-expanded="true"]` to find an open popover will match an expanded
card's own control. Query `.thrive-popover` instead.

**A prop's declared type does not survive the parent revoking it.** A Svelte 5
prop is a GETTER over the parent's state. `ItemDetail` declares `item:
ScheduleItem`; the parent nulls `detail` on close and the `{#if}` tears the subtree
down a tick later, so any handler that fires DURING teardown — a blur, most
obviously — reads null off a non-nullable type. It threw. `ItemDetail` latches its
row at mount; where a prop really does change, guard the handler instead. See
FINDINGS and BUGS.

**Both event-scoped stores key on the raw `Event.id`.** Joins and ignores. The
calendar sheds its `evt-` prefix in `calendarEvents.ts` and nowhere else, so a row
never holds two ids for one event. Settled in 7c with the consumer in front of us;
the item-id shape was MIGRATION §9 defect 13.

**There are TWO adapters and an env var picks one.** `npm run build` is Netlify,
`npm run build:node` is a Node server into `build-node/`, which is what the two
browser gates spawn. Nothing about the app differs — nothing is prerendered, so
every route is server-rendered per request either way. See `vite.config.ts`.

**`flex-1` is a width in a row and a HEIGHT in a column**, where it silently beats
an `h-` beside it. Moving a panel between the two changes what it constrains.

**A form action needs `ORIGIN` or it 403s.** `adapter-node` cannot know its own
public URL, and SvelteKit's CSRF check compares a POST's `Origin` against the
guess. `npm run dev` is unaffected, so booking works in dev and only the build
fails. Both browser gates now set it. See `setup_info.md`.

**A scrollable region must be focusable, and Svelte's a11y rule disagrees.** axe's
`scrollable-region-focusable` requires `tabindex="0"` on the chat log;
`a11y_no_noninteractive_tabindex` objects to it on `role="log"`. The tabindex
wins, suppressed at that one site with the reason written down — without it a long
conversation is mouse-only.

**A gate that can pass for the wrong reason is worse than no gate.** The
clear-on-switch check typed a question that was word for word one of the Course
Recommender's example questions, so it matched the empty state rather than the
message and went red against correct code.

**The old Next repo is read-only.** `~/Desktop/Test 1/Thrive-msba-brain`.

---

## Commands

```bash
cd frontend
npm run dev -- --open      # dev server, :5173
npm run build              # production build
npm run build:node         # the same app as a Node server, into build-node/
ORIGIN=http://localhost:3000 node build-node/index.js   # run that, :3000
npm run check              # svelte-check
npm test                   # vitest run — 640 tests

python3 scripts/check-contrast.py    # 58 assertions: 42 pairs, 6 ceilings, 10 structural
npm run check:layout                 # 17 targets x 3 viewports, in a real browser
npm run check:interaction            # 190 assertions: the popovers, task editing, the calendar,
                                     #   booking, Ask THRIVE, and the page measure
```

If a page looks stale locally, something is holding the port:
`lsof -ti:3000 | xargs kill -9`.
