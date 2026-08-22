# TESTING

**Last verified:** 2026-08-21 at `3d38df1`. **640 tests, 29 files, all
passing. 213 interaction assertions, 51 layout targets, 58 contrast assertions.** Verified green in all seven timezones of the sweep below — and in 7a
the sweep **caught a real failure**, which is recorded there.

```bash
cd frontend
npm test           # vitest run
npm run test:unit  # watch
npm run check      # svelte-check
```

Plus two gates that are tests in everything but name:

```bash
python3 scripts/check-contrast.py    # 58 assertions: 42 pairs, 6 ceilings, 10 structural
npm run check:layout                 # 14 targets x 3 viewports, in a real browser
npm run check:interaction            # 97 assertions: popovers, task editing, calendar, Home
```

`check-contrast.py` PARSES `app.css` rather than mirroring it, so a token edited
there is checked there. `check:layout` needs a browser and skips loudly (exit 0)
when it cannot find one — see the note below.

---

## 2026-08-21 (later) — 190 -> 213 interaction assertions

Four requests added 23, and **one of them replaced a check that could not fail**:
`check('the calendar is allowed more width than the rest', true, '<prose>')`. A
literal `true` with a sentence for a reason is a line in the count and nothing else.
It is now a comparison of two routes' measured gutters.

The other lesson is in BUGS.md and is worth repeating here because it is a TESTING
failure rather than a code one: the appointments grid assertion read *the first
`<p>` in the pane* and checked only that its text changed. It never looked at the
list the student actually reads, and it only ever clicked cells inside the displayed
month -- so the adjacent-month path was untested while being green. It now walks
both groups of cells until the pane's ROWS change, and reads the date by a
`[data-my-day-date]` hook rather than by position.

New this pass, by area:

| Area | Assertions | What they hold |
|---|---|---|
| The calendar's Key as a disclosure | 6 | shut on arrival and absent from the DOM, names the filter in words, opens from the keyboard, both dimensions survive, 44px trigger on a phone |
| The Key's streams as a column | 4 | one line per stream, one dot x-position across all 11, still a checked control, 44px row on a phone |
| Appointments: control before result | 2 | the pane is below the month, and grid-top to pane-bottom fits one screen |
| Appointments: the coupling | 10 | the pane's ROWS move for both an in-month and an adjacent-month cell, and the chips hold on every click of the walk |
| The history rail as a region | 5 | a surface distinct from the page, a panel edge, rows that look clickable at rest, a current marker that is not hue alone, and a stripe that does not shift the list |

`check:layout` needed no change for any of it. It measures each route's scroll
height against its painted height rather than hardcoding either, so a height change
is simply the new truth -- which is the property that makes it survive a density
pass. 51/51 throughout.

---

## Phase 7c — three new spec files, and both browser gates widened

`ics.spec.ts` (13), `calendarAdd.spec.ts` (18), `calendarEvents.spec.ts` (8), plus
new cases in `calendarItems.spec.ts`, `calendarStores.spec.ts` and
`userEdits.spec.ts`. 507 → 558.

### The one that is written against a known failure mode

`calendarEvents.spec.ts` deliberately **never round-trips**. Phase 7a's ignore-store
defect survived two passing tests because a normaliser applied on both sides makes a
store perfectly self-consistent about a key nothing else uses. So each case here
either

- reads the literal string back out of the fake `localStorage` and compares it to a
  hard-coded key, or
- writes through the path ONE surface really uses and reads through the path the
  OTHER really uses.

**Not sharing a transformation is the property that catches a key-space split.**
Verified to fail: reinstating the bug (`eventId = item.id`) turns 7 cases red. A
round trip written over the same pair of functions stays green.

### Absence as well as presence

`calendarAdd.spec.ts` asserts, for each of the three kinds, that its store gained a
key AND that the other two localStorage keys were never created. "The task store
gained a key" stays green if the write went to all three. One case does three adds
in a row, because a case that starts from empty cannot notice a stray write on the
second call.

### What is still browser-only, and now actually covered

`check:interaction` gained 24 assertions (60 → 84), and they are the ones that
**cannot** be written as unit tests here — Vitest runs in Node with no jsdom, so
there is no `document.activeElement`, no layout, and no unmount to blur during:

| Claim | Why only a browser can see it |
|---|---|
| the day figure equals the rows beneath it | a count of DOM nodes against a rendered number |
| focus moves into the dialog, and onto CLOSE | there is no focus model in Node |
| Tab and Shift+Tab are trapped | needs real key events against a live tab order |
| focus returns to the opener | the opener is a DOM node, and pointer focus is browser-specific |
| delete asks first | a statement about two presses |
| joining moves the fraction | a store write reflected in rendered text |

**It found two real bugs on its first run** — a TypeError on every close with focus
in the label field, and focus not returning after a pointer-opened dialog. Both are
in BUGS.md. Neither was visible to 553 unit tests, `svelte-check`, the build, the
contrast gate or the layout gate.

### `check:layout` covers the week and agenda views

The calendar's view is a persisted preference rather than a URL, so `/calendar`
only ever measured the month grid. The gate now writes `thrive:calendar-prefs`
before measuring and removes it when a target names none, so a view cannot leak
forward into the next route. 36 → 42 assertions. The agenda measures 15,528px on a
phone, which is what the gate is for.

---

## Setup

**Vitest, Node environment, no jsdom.** Nothing renders. Configured as
`usages:unit` only, matching the prototype where all 83 tests were pure logic
and rendering was deliberately never tested.

The `@lib` alias comes from the `sveltekit()` plugin in `vite.config.ts`, which
the Vitest project extends. **Runes work in `.svelte.ts` under the Node env** —
smoke-tested before the store layer was written, since the whole phase depended
on it.

`src/lib/testing/fakeStorage.ts` is a `localStorage` stand-in. It exists because
the store layer decides "am I in a browser" by asking whether `localStorage`
*exists*, not via `$app/environment` — so a fake is all it takes to exercise the
entire persistence layer without jsdom. It covers the server case (uninstall
it), the quota case (`failWrites()`), assertions on what was persisted
(`dump()`), and storage that **throws on property access**.

Module singletons need `vi.resetModules()` + `await import()` per test. **Do not
mix that with static imports of the same module in one file** — the static import
is a different instance. That is why store tests live in their own spec files
rather than being appended to the pure-logic ones.

---

## Coverage

| Spec | Tests | Covers |
|---|---|---|
| `providers.spec.ts` | 47 | The four provider properties (Promise-returning, copies-not-references, deterministic generation, fixtures relative to now), the public surface of `$lib/data` including what must **not** leak, and every store behaviour: booking claims, double-book throws, cancel releases only its own slot, `submitRequest` idempotence, unknown ids returning null |
| `collapse.spec.ts` | 13 | The fit-on-one-screen rule at its boundaries: exactly-at-the-limit produces no control, one-over holds back one, a zero limit means show-none (the done group), a negative limit clamps rather than slicing from the end, and `visible` is never the caller's array |
| `homeGroups.spec.ts` | 19 | Home's grouping: the four groups in order with `unknown` first, "this week" held to a week, done pulled out, a student's override outranking the fixture BOTH ways, and an unparseable date landing in its own group rather than vanishing. Plus ordering (6b): the student's own keys, an explicit placement outranking an implicit one, reordering inside the dateless group, and a stale key for a row that is gone |
| `nav.spec.ts` | 12 | The nav lists disjoint and duplicate-free, and the two questions a card asks them: `isBuiltRoute` (exact, never a prefix — a prefix match would call `/calendar/2026` built and send someone to a 404) and `isKnownRoute`, which exists only to separate "parked on purpose" from "mistyped". Written to survive a route being BUILT: the relationship is pinned, not today's four hrefs |
| `taskBoard.spec.ts` | 43 | The editing half. `resolveRows` returning an untouched row BY REFERENCE (so an open note panel is not torn down by a sibling's tick), reclassifying only when the date moved, created tasks described against the same instant; the date converters in LOCAL time with a full round-trip; **every path through a due date that will not parse**, each of which threw a RangeError before this existed; `reorderedIds` and the drop-below-me off-by-one; and `isDatedGroup` pinning "Needs a date" as a source, never a destination |
| `taskView.spec.ts` | 15 | `rowPriorityOf` (deadline outranks stated priority; done strips the tint), `taskLabels` (two-label cap, course code over source word, Done replaces rather than joins), and the tone maps — including that `standingTone` never lands on `primary` |
| `programStrip.spec.ts` | 5 | `abbreviateTerm` on all four seasons, an unexpected shape passed through unchanged, and every phase status having a spoken form |
| `designSystem.spec.ts` | 4 | The two rules nothing else enforces: no hardcoded colour in a component, no component naming a font, every `.thrive-*` class in the known vocabulary |
| `format.spec.ts` | 89 | `describeDue` across all four branches with every field asserted; the boundaries rather than the middles (day 0/−1, 1/2, 6/7, exact midnight, ±1s across a rollover); `calendarDaysBetween` and `countdownPhrase` through their public surfaces; both DST transitions; month, year and leap-day spans; both countdown thresholds from both directions; every other exported helper |
| `calendarStores.spec.ts` | 37 | Calendar prefs store, quick list, labels/urgent/custom events, ignored events, `tickItem` writing back through the attached row, and **the three key spaces staying separate** |
| `buildSchedule.spec.ts` | 13 | The server half: classes staying weekday RULES rather than being expanded, every dated row's `dayKey` agreeing with its own `startISO`, an event all-day in all three fields or none, the `evt-evt-` double prefix recovered by `eventIdOf`, and nothing the server built claiming to be tickable |
| `calendarDay.spec.ts` | 20 | The selected day: the re-sort across two filtered slices (two sorted lists joined end to end are not sorted), `DAY_GROUPS` order rather than time order, squares that never mark a class done, and "1 class" not "1 classes" |
| `calendarViews.spec.ts` | 20 | The views: the agenda's 30-day range across month, year and leap boundaries and with no duplicates; when a row must name its own date; the source row attached to an undated to-do, asserted as the MECHANISM; and urgent-only emptying that section because none of them can be urgent |
| `schedule.spec.ts` | 27 | Grid arithmetic, `isVisible`/`filterSchedule`, `nextUpItem`, `groupAgenda`, `groupDayItems`, `weekGrid`, and the collapsed `dayKeyOf` agreeing across both signatures |
| `userEdits.spec.ts` | 27 | Property 4 one setter at a time, `isTaskDone`, `applyTaskEdits`, added tasks, `removeAddedTask` cleanup, `reorderWithin`, the undo slot and its clock |
| `overrideStore.spec.ts` | 21 | All four store properties, including corrupt input in five shapes and a failing write |
| `ignoredEvents.spec.ts` | 22 | Id normalisation **and what it mangles**, eligibility across every legend category, the never-hide-an-obligation guard, month-dot and `+n` arithmetic, undo restoring position |
| `calendarSources.spec.ts` | 18 | `taskToItem`/`todoToItem`, and that every tickable row carries its source object |
| `taskNotes.spec.ts` | 13 | Hydration gate, corrupt input, forget-on-empty, merge-not-replace |
| `calendarPrefs.spec.ts` | 11 | Defaults and migration. Has caught four separate new-field omissions in its life |
| `calendarItems.spec.ts` | 9 | Custom-event mapping, rejecting malformed and non-existent dates, label/urgent filtering |
| `toast.spec.ts` | 6 | The single slot, its 3000ms clock, and that it persists nothing |
| `reveal.spec.ts` | 16 | `planReveal` at the boundaries (last row of the slice vs first row past it; not-found kept distinct from found-and-visible; a zero limit); the reveal path run against the list `TasksCard` really builds, so an undated row pushing the overdue task past the cap is asserted rather than imagined; that no overdue or due-today task can be filtered out of the card's list; and `expandedEventLimit`'s prefix argument, including that a quiet week never loses rows |

### The interaction gate

`npm run check:interaction` · `scripts/check-interaction.mjs` · 97 assertions.

**Why it exists.** The other five gates were ALL green on a version of the stat
pill popovers where pressing a pill did nothing at all. Hover had already opened
the panel, so the click found it open and closed it again. None of the other five
can press a button.

It has since earned the point twice more. A `derived_inert` warning shipped in the
production build with all six gates green, because nothing dragged a row; and the
undo arrival's silent no-op is invisible to everything else in the repo.

**What it covers.** Opening and closing; the pill's number matching the length of
the list it opens; focus moving into the list; Arrow, Home and End; Escape and
click-outside with focus returning to the pill; the reveal, including a card
expanding to show a hidden row; the arrival mark appearing, being unique, and
clearing itself; reduced motion; the inert zero-count pill; and the clamped panel
at 375px.

**And one absence.** `hovering a pill does NOT open its popover`. Hover was built,
rejected and removed, and reintroducing it is the only route back to the original
bug — so it is asserted rather than assumed. The check is non-vacuous: the gate
first asserts the driving browser reports `(hover: hover)`, or "hover did nothing"
would pass on a browser that cannot hover at all.

**What 6b added** (18 assertions). A row being really tickable — ENABLED, not
merely present, since 6a rendered these disabled on purpose and "a checkbox
exists" would have passed against the read-only card. Then the tick counting, the
undo offer standing, the undo strip **not** being a live region of its own, the
undo arrival, **the undo arrival when the row is hidden and the card must expand**,
a drag between groups, a rename committing on blur, and the grid still not moving
with every editor in the tree.

The hidden-row arrival is the one that earns its place. One `tick()` suffices only
because `undoTick` writes everything — including the expansion — before calling
`arriveAtRow`; move that into an effect and the arrival lands nowhere, marks
nothing, and logs **no warning in production**. It is indistinguishable from a
successful arrival at a row that was already on screen, and this assertion is the
only thing anywhere that can tell them apart.

**Verified to fail**, each broken on purpose: hover reintroduced (6 red, the
original bug reproduced), the arrival mark not applied (4), never cleared (2), the
undo expansion moved into an effect (1, and no console warning), `onblur` removed
(2), a `dragend` put back on the row (1, `derived_inert`).

**The limitation, stated:** its closing "nothing threw or warned" assertion reads
like a blanket guarantee over the page and is really a guarantee over the gestures
the script performs. When a feature adds a gesture, the gate has to make it.

**And one vacuous check, caught and fixed.** `copy-to-list appears exactly when the
quick list does` first inferred `FEATURES.floatingTodo` from the page by looking for
a To-do launcher — but the selector matched the copy button's own accessible name,
"Copy X to your to-do list". It read the thing it was gating as proof the gate was
open, and passed both with the guard and without it. **The flag is parsed from
`features.ts` now**, the way `check-contrast.py` parses `app.css`: an assertion's
expected value cannot be derived from the thing under test. Worth knowing because
nothing but re-running it with the guard removed would have revealed it.

**It reads its inputs from the source of truth.** The arrival dwell comes from
`--thrive-arrival-duration` on the running page, not from a copy in the script, so
retuning the token cannot leave the gate passing against the old value. Same
principle as `check-contrast.py` parsing `app.css`.

**It knows no fixture ids.** The task ids it ticks to force a zero count are
discovered by choosing the popover's own items and reading where focus landed. A
gate that hardcodes `tsk-001` starts failing the day the fixture is edited, which
teaches everyone to ignore it.

**Verified to fail**, three ways, by breaking each thing on purpose:

| Break | Red |
|---|---|
| Hover reintroduced on the wrapper | 6, including "clicking a pill opens its popover" — the original bug, reproduced |
| The arrival mark never applied | 4 |
| The arrival mark never cleared | 2 |

**It reports SKIP, not PASS,** for the "a hidden row makes its card expand" check
when the fixture has no target past a collapsed slice. Degrading silently to a
weaker assertion is how a gate stops meaning anything. Today's fixture proves it
(8 → 25 rows), but a quieter one would not.

**It fails on console warnings, not only throws** — and the note at that assertion
says what it cannot see. `arriveAtRow` warns in development when the row it was
sent to is absent, and that warning is behind `import.meta.env.DEV` while this gate
drives the production build, so the branch is compiled out. Stated at the check
rather than left implied, because an assertion that looks like it covers something
it cannot is worse than no assertion. That branch was verified by hand against
`vite dev`: a normal arrival warns about nothing, a row with its id removed warns
exactly once and names the id.

**Skips loudly and exits 0** with no chromium, same as the layout gate.

### The layout gate

`npm run check:layout` drives the built page in a real browser and asserts, for
every route at three viewports, that the furthest the page can scroll is no
further than the lowest thing it paints.

**Why it is not a Vitest test.** It needs a real layout engine. Vitest runs in
Node with no jsdom here by standing decision, and jsdom would not help: it does
no layout and reports every height as zero. A gate built on a model inherits the
model's blind spots, which is precisely how this bug survived —
`documentElement.scrollHeight` reported 1275px while nothing rendered below
1238px, so any assertion built on it would have been green on a broken page.

**It does not use `scrollHeight`.** It scrolls the page and reads where it landed.

**It skips rather than fails when there is no browser.** `playwright-core` ships
none. A gate that fails for reasons unrelated to the code gets ignored, and an
ignored gate is worse than no gate because it looks like coverage. It also finds
a cached chromium from a different playwright version by hand.

**Verified to fail on the bug it was written for** before being trusted:
commenting out `contain: paint` gives `/ desktop  renders 1238  scrolls to 1275
FAIL  37px of empty scroll` and exit 1.

### What is still not tested

**Rendering.** No component is mounted anywhere in the suite. The design-system
guards and the layout gate scan source and drive a browser respectively; between
them there is a real gap — a component can render the wrong content with correct
types, correct classes, and no page-level overflow. Phase 6b's editing behaviour
is the first thing that will genuinely want a rendered assertion, and it is worth
deciding then whether jsdom or Playwright covers it.

### The calendar's gate blind spot, named

**`check:layout` only ever visits `/calendar` in its DEFAULT view.** The gate opens
each route with an empty `localStorage`, so `normalisePrefs` returns
`view: 'month'` and **the week and agenda views are unvisited by every gate.**

That matters most for the agenda: over a 30-day range it is 13,764px tall on a
phone, and a long list is exactly where a "does the document scroll further than it
paints" gate earns its keep.

Covered by hand in 7b instead, at 375 / 640 / 700 / 767 / 768 / 769 / 900 / 1330px
across all three views: zero horizontal overflow everywhere, and nothing scrolls
past what it paints. **Approved for 7c** — deferred out of 7b because the surface
the gate would guard was still being built, not because the gap is acceptable.

### The calendar, and why `check:interaction` did NOT grow

Phase 7a's answer to "nothing renders" was **to move the decisions out of the
components** rather than to widen the browser gate. `calendarDay.ts` exists for
that reason alone: `sortDayItems`, `arrangeDay`, `squareGroupsFor` and
`dayCountParts` were all inline in `CalendarView` or `CalendarHeader`, where no
gate could see them, and each has a branch that has been got wrong once already
(the two-slice concatenation, the tickable denominator, "1 classes").

`check:interaction` stays scoped to Home, as instructed, and **nothing in 7a
proved it needed extending**. What that gate can uniquely do is press a button,
and the calendar's two button-shaped behaviours this phase — ticking a row, and
arranging the day by type or time — are both thin wrappers over logic that is now
unit-tested: `tickItem` dispatching on an attached source row is covered in
`calendarStores.spec.ts`, and `arrangeDay` in `calendarDay.spec.ts`.

**What is genuinely uncovered is `MiniCalendar`'s keyboard grid** — 42 cells, a
roving tabindex, and six key bindings that no unit test can press. It was verified
by hand against the production build instead, and the results are recorded in
HANDOFF: arrows in all four directions with focus and selection agreeing, Home and
End landing six days apart, PageDown/PageUp moving the month while focus survives
the swap **and the document does not scroll**, six ArrowUps pulling the view back a
month, a trailing cell click pulling the view forward, and no console output.

That is the honest state: a by-hand verification, not a gate. If the grid grows a
second keyboard behaviour, this is the first thing in the calendar that should
argue for extending the interaction gate.

**7b did not change that answer.** Its four new components put their decisions in
`calendarViews.ts` where the suite can see them, and what is left is again
browser-only: the 48rem boundary, the week columns' measured width, the focus ring
that `sr-only` inputs make necessary, and whether a filter chip really removes a
month dot. All driven by hand, all recorded in HANDOFF with numbers.

One reading from that pass is worth carrying: **wait past the longest transition
on an element before reading a computed style.** `transition-colors` includes
`outline-color`, so a probe that reads a focus ring the instant focus lands
measures the fade, not the colour. It nearly produced a fix for a bug that did not
exist. See FINDINGS.

### Testing the provider layer

**Properties, not fixture contents.** The fixtures are demo data and will be
deleted when Django lands, so asserting on them would be writing tests with a
known expiry date. `providers.spec.ts` asserts the four things that have to
survive the swap, and the store behaviours that have gone wrong before.

**Isolation comes from the test side.** The three stores are module-scope
objects, so under one registry a test that books an appointment changes what the
next test sees and the suite starts passing on file order. Each test calls
`vi.resetModules()` and re-imports. A `resetStores()` export would have been
more convenient and would have put a test-only function in the production
surface, where it would still be sitting long after Django made the stores
irrelevant.

**Freeze `Date` only.** `vi.useFakeTimers({ toFake: ["Date"] })` — because
`resolveAfterDelay` needs a real `setTimeout` to resolve. Faking all timers
deadlocks every provider call. Latency goes to 0 through `setMockLatencyMs`,
which is the whole reason that knob exists.

**One test asserts on source text.** The `Math.random()` scan reads the data
directory through `import.meta.glob(..., { query: "?raw" })` — not `node:fs`,
because this repo has no `@types/node` and `npm run check` is a gate. It strips
comments first: both hash functions carry a comment naming `Math.random()` as
the thing they avoid, and a guard that forced those comments out would be
deleting the explanation to satisfy the check. It also asserts the stripped
corpus still contains both hash functions, so it cannot pass vacuously.

### What the suite is actually good at

**The four store properties**, each pinned because breaking it fails *silently*:
an override that quietly comes back, or quietly does not. Property 1's test —
that an explicit `false` is a different thing from an absent key — is the one
that encodes why this is an override map and not a set of ids.

**Boundaries over middles.** `describeDue` is tested at day 6 vs day 7, exact
midnight, and one second either side of a rollover, not just "overdue" and
"upcoming".

**Calendar days vs elapsed hours.** A 23:00→01:00 pair is two hours apart and
**one calendar day**. An elapsed-time rewrite would floor it to zero and call a
tomorrow deadline "today". That single assertion is the most load-bearing in the
suite.

**Timezone independence, proven not assumed.** The whole suite passes in seven
zones from UTC+14 to UTC−11, including Australia/Lord_Howe's 30-minute DST
offset:

```bash
for tz in UTC America/Los_Angeles Asia/Tokyo Pacific/Kiritimati \
          Pacific/Midway Australia/Lord_Howe Asia/Kathmandu; do
  TZ=$tz npx vitest --run
done
```

Every fixture instant is built from **local parts** and only then serialised.
Run this sweep after touching anything date-shaped — it caught a
timezone-dependent assertion in a test written this session.

#### It caught a second one in Phase 7a, and this is the useful part

`reveal.spec.ts` had **`NOW` as `new Date("2026-08-21T12:00:00Z")` and its due
dates as `Z` instants beside it** — exactly the shape the paragraph above forbids.
`tsk-today` was `2026-08-21T23:00:00Z`, and 23:00 UTC is already **tomorrow**
anywhere east of UTC+2, so `describeDue` classified it `upcoming` and the "every
overdue and due-today task stays reachable" property counted one row instead of
two. Red in Asia/Tokyo, Asia/Kathmandu and Australia/Lord_Howe; green in the other
four, including both extremes.

Two things worth keeping:

- **The bug was in the FIXTURE, not in `describeDue`.** A task due at 23:00 local
  on the 21st really is due today. Reaching for the classifier would have broken
  correct behaviour to make a wrong test pass.
- **It was written before Phase 7a and had never been swept.** The doc line at the
  top of this file claimed the suite was green in all seven zones, and it was not.
  A verification claim decays exactly like a comment does — the sweep is cheap
  (~14s) and it is now run on any date-shaped change, not just on date-shaped
  *new* code.

Fixed by a `local(y, m, d, h)` helper in that file. Nothing outside the fixture
moved.

### Two tests are defect records, not assertions of intent

Named `DEFECT:` or `DOCUMENTS A GAP:`, each commented with why it was not fixed.
They pin current behaviour so the defect cannot be lost, and so the eventual fix
arrives as a **failing test**. See `BUGS.md`.

There were three. The first one below was **retired in Phase 7a** when the defect
it pinned was fixed, and replaced by a real cross-surface test — which is the
mechanism working as designed.

1. ~~The ignore store's two surfaces not sharing a key space.~~ **Fixed in 7a.**
2. A rolled-over date (`"2026-02-30"`) passing `describeDue`.
3. `eventIdOf`'s asymmetry being self-consistent within one surface, which is
   why it went unnoticed.

---

## Gaps

Ordered by how much they would hurt.

### No component or route tests at all

Zero. No jsdom, no `@testing-library/svelte`, no Playwright. Nothing verifies
that a component renders, that navigation works, or that `aria-current` lands on
the right item. **Everything visual and interactive is currently verified by
hand.**

Phase 4 was checked by `curl`-ing the SSR output of the built adapter-node
server for titles, the skip link, `aria-current` counts, and `PagePlaceholder`'s
throw (500 + the exact message). That is real verification, but it is not a test
and it does not run again.

**This is the largest gap and it grows with every UI phase.** Two decisions
pending: whether to add `vitest-browser-svelte` / jsdom for component tests, and
whether Playwright becomes a dependency. The prototype deliberately kept
Playwright out and ran it from a scratch directory twice.

**2026-08-21: this gap produced a real shipping bug and caught it by luck.** The
first `StatPopover` held one boolean, and pressing the pill did nothing at all —
a mouse click is preceded by a pointer entering, so hover had already opened the
panel and the click closed it again. `npm test` (389), `npm run check` (0/0),
`npm run build`, `check-contrast.py` (58/58) and `check:layout` (36/36) were ALL
green on that version. **None of the five gates can press a button.**

It was found by driving the built page in the machine's Playwright chromium — 27
assertions over opening, keyboard navigation, all four dismissal paths, the
reveal, and the clamped panel at 375px. Those assertions were a **throwaway
probe**, run once, and they do not exist in the repo.

**It is now a gate.** `npm run check:interaction` — 60 assertions when it was
decided and built the same day, 84 when 7c widened it to the calendar, and 97 once
Home's two register controls were wired. No new dependency, and see its own section below.

The gap it closes is no longer one widget: 6b's editing is gated through the same
script, which is where "the next thing that wants a rendered assertion" landed. The
general question — component tests via jsdom or `vitest-browser-svelte` — is still
open, and the answer so far is that driving the built page has caught three real
bugs and cost one dependency the repo already had.

### Nothing exercises hydration for real

`hydrateStores()` is called from the root layout's `$effect`. Tests cover the
store layer's hydration *contract* — empty before, populated after — but nothing
proves the layout actually calls it, or that the un-personalised first paint
looks acceptable. Needs a browser.

### No provider tests

Phase 5's territory. `stubProviders.ts` is untested; it is one hardcoded object.

### Not covered in `lib`

- `taskView.ts` — never ported (imports a component type).
- `taskBoard.ts` — never ported.
- `buildScheduleData()` — needs providers.
- `mergedSchedule()` — **ported but untested.** Its two mappers are well
  covered; the merge that composes them, applies edits in order, and annotates
  last is not. Worth a suite: the ordering it encodes is subtle.
- `nowMinutes()` — ported, no caller, no test.
- `escapeKey` action — no test (needs a DOM).
- `ics.ts`, `useIgnoreUndo.ts`, `floatingPanel`/`assistantPanel` geometry — not
  ported.

### `format.ts` leftovers

`formatShortDate` can still emit `"Invalid Date"` and is deliberately untested —
pinning that string would entrench it.

---

## Conventions

- **Probe before asserting.** Write a spec that only `console.log`s, run it with
  `--reporter=verbose --silent=false` (Vitest hides stdout on passing tests),
  read the real values, write the real spec, delete the probe. This caught V8's
  inconsistency on invalid ISO dates and would otherwise have produced a wrong
  test.
- **Always pass `now` explicitly.** Nothing reads the real clock. That parameter
  exists for this.
- **Build fixtures from local parts** — `new Date(y, m, d, h)` then
  `toISOString()`. Never `new Date("2026-08-17")`, which parses as UTC.
- **Run the existing suite before adding tests to a fix**, so "all N passed
  unmodified" is a claim about the fix rather than an artifact.
- **Never weaken a test to make it pass.** If it fails, that is a finding.
- **Do not pin garbage output.** Flag it and leave it uncovered instead.
- Comments explain *why* the assertion matters, matching the house style.

---

## Phases 8 and 9 and everything after — three new specs, both gates much wider

**640 tests, 29 files. `check:layout` 42 → 51. `check:interaction` 97 → 190.**

| Spec | Holds down |
|---|---|
| `availability.spec.ts` (20) | The two count maps and the pair they form; `orderedDayKeys` across a year boundary; `firstBookableDay` skipping a full first day and respecting the order it is given over the map's; `slotsForDay`'s mode filter keeping taken slots |
| `appointmentsActions.spec.ts` (13) | The throw becoming a VALUE — both 409 sentences, the 400 and the 404, the reason truncated where the markup cannot be trusted, and cancel releasing the slot it was booked against |
| `ask.spec.ts` (32) | The destination guard including near misses; `relativeDayLabel` across month, year and leap boundaries and at both ends of a day; the view models carrying no raw instant at all; `showsDayLabel`; and the conversation providers' copies, order and nulls |
| `nav.spec.ts` (12 → 21) | `flattenNav`, a parent before its children, the identity case, and that a child destination counts as built |
| `format.spec.ts` (89 → 92) | `formatWeekdayDate`, asserted to AGREE with `formatShortDate` about the date half rather than merely to work |
| `providers.spec.ts` (47) | Now pins **27** providers rather than 25 |

### The spec that changed shape twice, and what that taught

`availability.spec.ts` was written at 29 tests around a one-calendar-month
BOOKING WINDOW that was separate from the fixture. Its centrepiece froze **Monday
1 December 2025** — the worst case by construction, since a Monday packs business
days into the fewest calendar days and December is 31 days long — and asserted
that the fixture published at least as far as the window reached.

**It went red immediately and caught a real off-by-one:** `BOOKING_WINDOW_DAYS =
23` reached day 30 against a window that can reach 31. The fixture was raised to
25; the rule was not lowered.

Then the month picker was reverted to the chip strip, the window and the published
set became the same thing again, and `bookingWindowEnd` / `isBookableDay` /
`openCountInWindow` were deleted with their tests. The spec is 20 tests now.

**Deleting a test because its subject is gone is not the same as weakening one**,
and the difference is worth stating because the counts moved down. What is gone is
arithmetic that no longer exists. What replaced it is `publishedByDay`, and its
best test is the PAIR: a Saturday and a fully-booked Tuesday both have an open
count of zero, and only the second map separates them.

### What only a browser could prove, and why

`check:interaction` went 97 → 190. The ones that are not merely convenient to put
there:

- **The double-booking race, run for real.** Two pages against one server: A holds
  a slot, B takes it, A confirms and is told. `providers.spec.ts` proves the throw
  and `appointmentsActions.spec.ts` proves the 409; neither can show a student
  losing a slot underneath them. The mock store being process-global is a blocking
  bug, and this is the one place it is useful.
- **A negative: the booking chips do NOT move when the month grid is clicked.**
  Booking and browsing are separate questions on that page and the coupling runs
  one way. Nothing that renders nothing can check that two other components stayed
  still.
- **The nav disclosure's whole contract**, including that collapsing REMOVES the
  children from the DOM rather than hiding them, which is the difference between
  "out of the tab order" and "probably out of the tab order".
- **Nothing persisted by Ask THRIVE.** The assertion is that sending a message
  writes NO `localStorage` key, which needs a real one to be empty of.
- **Two independent scroll containers** — the history rail and the chat log —
  asserted as both scrollable and neither containing the other.
- **The page measure**: every route fills the room the gutter leaves it, keeps a
  visible gutter, does not widen its prose, and stops at its cap on a 1920px
  screen. Widths are layout, and layout needs a layout engine.
- **The calendar's order**: the grid above the fold, using its width, with the Key
  beside it on a desktop and below it on a phone.

### `check:layout` can press a button now, and it builds its own server

`/appointments` was already a target but only ever measured CLOSED, where it is
two cards and a list — incapable of overflowing. No preference could reach the
expanded state, because which advisor is open is component state. A target may now
name a `click` selector, waited for and pressed after the reload and before
anything is measured.

Both browser gates also now run `npm run build:node` themselves rather than
assuming a build exists, which closed a real hole: `npm run check:layout` used to
be able to measure yesterday's output and pass.

42 → 51 targets: `/appointments booking`, `/ask conversation`, `/ask career`.

### Three gate bugs of my own, all instructive

Recorded because the failure modes are the interesting part.

**A test that could pass for the wrong reason.** The Ask THRIVE clear-on-switch
assertion typed *"Which electives suit product analytics?"* — word for word one of
the Course Recommender's own example questions. So it matched the empty state
rather than the sent message and went red against perfectly correct code.

**An assertion measuring the wrong box.** "Each route fills the room it has"
compared the page's measure against `main`'s BORDER box, so the side gutters read
as a 40px shortfall on every route.

**An assertion that was too broad.** "The month grid is no longer hidden from
assistive technology" queried the section for ANY `aria-hidden` element and
matched each cell's dot row — which is legitimately hidden, because it repeats
what the cell's accessible name already says in words.

**A gate that can go green or red for a reason other than the one it names is
worse than no gate**, because it teaches everyone to argue with it.

### And one caught by a SKIP, which is the quietest failure there is

The chat log stopped being a scroll container when the Ask page lost its rail: the
panel became a `flex-col` child, and `flex-1` there governs height and silently
beat the height token, so the document grew instead of the log scrolling.

No assertion failed. `check:interaction` reported *"a keyboard can scroll the log
— SKIP: could not make the log overflow"*, and that was the only signal. The
layout looked fine. **A skipped assertion is a result, not an absence** — worth
reading the SKIP lines rather than only the FAIL lines.
