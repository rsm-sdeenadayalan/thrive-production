# HANDOFF

Session log, newest first. What happened, what was decided, what is still open.

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

## 2026-08-21 — Phases 8 and 9, three redesigns, a deploy, and this doc pass

**HEAD:** `81137b7` · **640 tests · 190 interaction assertions · 51 layout targets ·
six gates green · green in all seven timezones.** 110 commits, all pushed.

Long session. Two phases, then four follow-on requests that arrived mid-work, three
of which partly reversed the change before them. The reversals are the interesting
part and are recorded as such.

---

### The order things happened, because it explains some of the churn

1. **Phase 8** — `/appointments`, with a month calendar replacing the five-day chip
   strip. Designed, presented, approved with four answers.
2. **Phase 9** — `/ask`, arrived while Phase 8 was mid-flight. Phase 8 was finished
   and committed first rather than abandoned, because otherwise four answered
   decisions would have been discarded and an orphan fixture change left in the
   tree.
3. **"The appointments page is confusing"** — the month grid read backwards.
   Measured three arrangements, shipped a day list.
4. **"Ask THRIVE does not use its width"** and the destinations moved to the nav
   rail.
5. **"Move the saved conversations into a second left rail"** — which partly undid
   (4)'s removal of that rail, for a stated reason.
6. **"The pages sit in a narrow centred column"** — widened the container.
7. **"Revert the day picker to the chip strip"** — undid (3) entirely.
8. **"The pages are now too wide"** — undid part of (6).
9. **"Deploy to Netlify."**
10. **"Make the mini calendar clickable"** — undid the read-only mode from (7).

**What that cost, honestly:** two components written and deleted (`DayPicker`,
`MiniCalendar`'s `readOnly` and `booking` modes), three window functions written and
deleted with their tests, and a fixture constant moved 5 → 25 → 5. Everything
deleted rather than left unreachable.

**What it bought:** every one of those reversals came back with a residue that was
never about the design being reverted — see FINDINGS.

---

### Phase 8 — what the owner decided

Four questions, all answered with the recommendation: raise the fixture to a month;
availability-only marks; calendar top-right with "Your day" under it; proceed. All
four are now moot, because the month calendar is gone. Recorded so it is clear they
were answered rather than ignored.

### Phase 8 — the appointments surface as it stands

Two advisor cards, then two columns: the booking panel left (chip strip → meeting
type → times → reason → confirm), and "Your day" right with a clickable month
beneath it.

**Two days, one-way coupling.** `bookingDay` drives the chips and the times;
`browseDay` drives "Your day". A chip moves both; the month grid moves only
`browseDay`. Stated at both ends in the code, and the gate asserts the negative
half.

**The window IS the fixture again.** `bookingDays()` publishes five business days
and the strip shows those five. `bookingWindowEnd`, `isBookableDay` and
`openCountInWindow` are deleted — they existed only while a grid could show days the
fixture had not published.

### Phase 9 — the shape it settled into

Nav rail → history rail → chat. The three destinations are `children` of the `/ask`
item in `nav.ts`, rendered as a disclosure; the page's own rail holds one
destination's history.

**`flattenNav` is what keeps `nav.ts` a single source.** `allNav` and `isBuiltRoute`
are DERIVED from the tree, so a child cannot exist in the rail and be missing from
`PagePlaceholder`'s lookup — there is no second list to add it to.

**No chat store.** Conversations are provider data; a sent message lives in
component state and is gone on navigation, and the page says so before you type.
The gate asserts sending writes no `localStorage` key.

---

### Decisions made in the owner's absence, and the owner's later rulings

Phase 9 and the follow-ons ran without the owner. The ones since ruled on:

- **Home keeps the 1280 cap.** Asked, answered: do not pin it narrower. Home was
  1152 before any of this, and 1280 is one step up rather than a new problem.
- **The cold-start note is in the README**, beside the no-authentication note.
- **The doc pass** is this entry and the files listed below.

Still standing and reversible:

1. **`/ask` redirects (307)** rather than offering a landing page.
2. **The conversation is a search param**, not a nested route.
3. **The composer is live** with a fixed "I can't answer yet" reply in component
   state, said before you type.
4. **A real conversation under the wrong destination is a 404.**
5. **One `svelte-ignore a11y_no_noninteractive_tabindex`** on the chat log — axe's
   `scrollable-region-focusable` requires the tabindex, Svelte's rule forbids it on
   `role="log"`. **Still the one most worth a second opinion.**
6. **The history rail shows ONE destination's conversations**, not all three
   grouped, because the loader 404s a conversation opened under the wrong
   destination — a mixed list would mostly be 404s.
7. **The month grid pages**, and paging does not touch the selection.
8. **`--container-wide` is `/calendar` only.**

---

### What the gates caught, which is the argument for widening them

Six real defects, none visible to any gate that existed before:

1. **A 403 on every form submission.** `adapter-node` needs `ORIGIN`; dev is
   unaffected, so it worked in dev and failed only in the build.
2. **A silent no-op behind it** — the `enhance` callback's third branch said
   nothing, so Confirm visibly did nothing.
3. **"Too far ahead to book" announced about last Tuesday.**
4. **`BOOKING_WINDOW_DAYS = 23` was one short**, caught by a test that froze the
   worst case on purpose.
5. **`flex-1` beating a height token**, caught by a SKIP — the quietest failure
   there is.
6. **Two `<nav>`s labelled "Primary"**, which made a gate count one `aria-current`
   twice.

And **three bad assertions of mine**: one that could pass for the wrong reason, one
measuring the wrong box, one too broad. All three in TESTING.

---

### Docs updated in this pass

README (cold starts), DEPENDENCIES (`adapter-netlify` added — the first package
change since Phase 1's `playwright-core`), setup_info (two adapters, the deploy),
TESTING, BUGS, FINDINGS, CONVENTIONS (two new rules: form actions, and layout
numbers as tokens), CODEMAP (refreshed at `81137b7`), CHANGELOG, this file, and
**CONTEXT.md regenerated in full**.

### Loose ends

1. **The real-phone pass**, four items: touch drag on Home's task rows, the month
   grid at 375px, the 8px dot against a thumb, and the Ask history strip against a
   thumb.
2. **`/assignments`** — the same `TaskRow` with no `reorder` prop. Owes it a
   `role="list"` container.
3. **The retrieval service behind `/ask`.** The three destinations are shells on
   purpose.
4. **Django**, which is the fix for the process-global stores, the missing auth, and
   the cold-start wipe.
5. **Decision 5 above** (the a11y suppression) wants a second opinion.

---

## 2026-08-21 — session close: the last inert control, and the doc system

**HEAD:** `99fd968` · **563 tests · 97 interaction assertions · six gates green ·
green in all seven timezones.** 89 commits, all pushed.

Three answers came in during the handoff. Two were work and are done; the third is
a note.

### Home's "Add to calendar" — the last inert control in the app

Nothing had been blocking it since `$lib/ics` was ported; an `Event` already carries
everything an `IcsEvent` needs. **There is now no inert control anywhere in THRIVE.**
Four have been removed in total: the parked "View all", copy-to-list with nowhere to
copy to, "count me in", and this.

**`icsFromEvent` is a second mapper rather than a shared one**, and that is the only
real decision. An `Event` has a real `location` and a required `start`; a
`ScheduleItem` has a `detail` meaning two different things by stream and an optional
`startISO`, because a recurring class is a weekday rule. Collapsing them means
widening one type or narrowing the other, plus a discriminant, plus a nullable
return one path never needs. **The one rule they share is asserted on both**, which
is what stops parallel mappers drifting and is cheaper than the abstraction.

### The gate reads the file, not the download

92 → 97. Asserting that a download FIRED would prove the button is wired and nothing
else, and "wired" is not the interesting claim: **the output is read by a calendar
client rather than by a person**, and an unescaped comma or a placeholder DTSTART
imports "successfully" and is wrong.

So the page's `createObjectURL` is wrapped before load and the blob text kept. Five
assertions on CONTENT. **The UID one earns its place**: it must be the raw
`Event.id`, or importing the same event from Home and from the calendar would put
two entries in the student's real calendar instead of updating one — a key-space bug
whose consequence lands outside the app, where no test can reach it.

### The README's Node line

Loosened from "Node 24 and npm 11 are what this is developed against" to **Node 20
or newer**, naming 24 as what it is developed on and saying plainly that nothing
below 24 has been tested. A version that happens to be installed is not a
requirement, and reading it as one blocks a teammate for no reason.

### Docs updated this session

CONTEXT (regenerated in full, then patched twice for same-session deltas — see the
note below), CODEMAP, CONVENTIONS, HANDOFF, CHANGELOG, BUGS, FINDINGS, TESTING,
setup_info, README. DEPENDENCIES untouched: **no package changed in 7c or in any
follow-on**, verified by diffing `package.json` and the lockfile across the session.

**A note on the CONTEXT patches.** The file was regenerated in full at `695dbb2`
from a complete read of all 1,809 lines. The two later edits were same-session
patches under the exception §16 already records, and every delta was enumerated in
its commit message rather than left to be discovered. If that reads as too loose,
the regeneration is cheap to redo now that the tree has settled.

### Loose ends

1. **The real-phone pass**, now three items: touch drag on Home's task rows, the
   month grid at 375px, and **the 8px dot against an actual thumb** — it was chosen
   against a measurement in 46px cells and should be confirmed by a finger.
2. **`/assignments`** — the same `TaskRow` with no `reorder` prop. Owes it a
   `role="list"` container.
3. **Appointments**, then the two Django-dependent features.
4. **Teal and amber cannot be made more vivid** without moving lightness, which the
   contrast floor forbids. Recorded so it is not rediscovered.

---

## 2026-08-21 — 7c follow-ons: Home's join, the dots, and the doc pass

**HEAD:** `e743232` · 6 commits · 558 tests · six gates green · green in all seven
timezones. `check:interaction` **84 → 92**. (Superseded by the session-close entry
above, which carries the final counts.)

Four answers acted on, in the order that avoided doing the same work twice — code
first, then CONTEXT, so the regeneration described the final tree.

### 1. The agenda keeps no add form — settled, no code

Owner's answer, and it is now written into CONTEXT §14 as a decision rather than an
omission: the agenda spans thirty days, so there is no day for a new item to land
on, and both other views offer one. Do not revisit without a proposal for what day
an agenda-level add would add to.

### 2. Home's "count me in" is live

Inert since 6a with a comment beside it saying exactly why — the join store was
keyed on the calendar item id, so a write from Home would have landed under a key
the calendar never reads. 7c settled that. It is now real, in the calendar's exact
shape, and **the register vocabulary moved to `messages.common.events`**: two live
surfaces rendering the identical words for the identical act should not be two
strings for a translator to keep in step.

**The gate gained 8 assertions, and the pair is the point.** Join on the calendar,
navigate to Home, and the same event says so — nothing in between but a page load
and `localStorage`. And Home's own control writes the RAW id, checked against the
row's own DOM id, which arrives by a different route (`revealRowId()` builds one,
the click handler passes `event.id` to the store).

Wiring Home without that check would have reassembled the exact conditions of the
7a defect: two surfaces, one store, each self-consistent, nothing looking at both.

**"Add to calendar" beside it is still inert** — not blocked on anything now that
`$lib/ics` is ported, simply not what this was for. It is now the only dead
affordance left in the app. CONTEXT §18 loose end 20.

### 3. The month grid's dots — and size beat colour

Reported plainly because it is the useful part: **6px → 8px did more than five
retuned colour tokens did.** 1.8× the area is 1.8× as much of any colour to see.

The colour work, in oklch holding lightness so contrast could not move:

| token | before | after | chroma |
|---|---|---|---|
| on-track | `#14706b` | `#00716c` | 1.07× |
| watch | `#8f6220` | `#946000` | 1.15× |
| needs-help | `#6a5fb0` | `#7851c2` | 1.37× |
| civic | `#8a5f8f` | `#994ea3` | 1.69× |
| later | `#64748b` | `#4c74ad` | 2.46× |

**Teal and amber were already at the sRGB gamut boundary for their lightness.**
1.07× and 1.15× is all there is, and the only way to more is to move lightness,
which the contrast floor forbids. That is a real limit, not a tuning failure, and
it is CONTEXT §18 loose end 21 so nobody spends an afternoon rediscovering it.

**The collision fixed:** `later` and `muted` were dE 0.039 apart — half the next
pair — and carried FOUR of the eleven categories between them. `muted` cannot move
(it is all secondary text); `later` can, and nothing about "later" requires grey.
Worst pair on the grid 0.039 → 0.078.

**The collision avoided, which is the more transferable half:** raising violet's
chroma along its own hue walked it INTO indigo, the reserved "you are here" — dE
0.047, worse than the worst pair before the pass — and both appear on the month
grid at once. Re-centring the hue 288 → 296 in the corridor between indigo and plum
bought 1.37× the chroma for nothing: separation from both neighbours marginally
BETTER. **Check a saturation change against every reserved colour, not just the one
you are separating from.**

Contrast 58/58, unchanged, no threshold touched. Dot geometry measured at six
widths: no clipping, no reflow, no horizontal overflow, 5px of slack at 375px.

### 4. CONTEXT.md regenerated in full

All 1,809 lines read first. Six things it caught beyond the counts are listed in the
commit message; the three worth repeating here are that §8's key-space table had
joins in the wrong space, §10 still named `ItemDetail` as a *candidate* third caller
for the two actions, and §10 said the toast had no caller when it has three.

### 5. Two doc jobs that arrived mid-session

**No personal names in any doc**, now CONVENTIONS rule 8. Eight occurrences across
three files, all replaced with roles. Fixture data is out of scope and unchanged.
The one that needed rewriting rather than substituting was the advisor entry — it
named two people, and what it was documenting is that one is in-person-only and one
has a remote mode.

**The README rewritten for someone arriving cold.** Its main job is the guide to the
eleven docs, ordered by what a newcomer needs first. It also gained a backend
section (the 25-provider seam, Promises so signatures survive, dates formatted
server-side) and the six gates with what each catches.

**Four claims in the old README were wrong**, all in one paragraph: 43 assertions
(58), three ceilings (six), "hex values are hardcoded to mirror `:root`" (it parses
`app.css` — the exact opposite, and the reason the chroma pass needed no gate edit),
and a docstring path that had already been corrected.

### Still open

1. **Home's "Add to calendar"** — one small mapper away, `Event` carries everything
   `IcsEvent` needs.
2. **The real-phone list**, now with one more reason: 8px dots were chosen against a
   measurement and should be confirmed against a thumb.
3. `/assignments`, then Appointments.

---

## 2026-08-21 — Phase 7c: the calendar's editing surfaces. The calendar is done.

**HEAD:** `5b636f6` · 8 commits · **558 tests** (was 507) · six gates green ·
green in all seven timezones.

Worked end to end without stopping, at the owner's instruction. Every call made in
their absence is below with the reasoning, so any of them can be reversed.

### The decision this phase was handed

**`thrive:event-joins` now keys on the raw `Event.id`.**

The brief was right that this is 7a's defect in a second store, and right that it
had to be decided with the consumer in front of us. Having built that consumer, the
argument is stronger than "be consistent":

1. **One row asks both stores.** A `DayEventsSection` row offers "count me in" and
   "ignore" side by side. Under the old shape the component holds two ids for one
   event and has to remember which control takes which — the exact arrangement that
   produced the 7a bug, not merely a rhyme with it.
2. **Home already holds the other id, and says so in a comment.** `EventRow`'s
   "count me in" is inert *because this key space was unsettled*. Home holds an
   `Event`, so it holds `event.id` — raw.
3. **A join is a fact about an EVENT.** Labels and urgent are keyed by calendar item
   id for the opposite reason: they annotate a row the student may not own, on
   streams with no event behind them. That is the test for whether a fourth key
   space is ever warranted, and this is not one.

Nothing argued the other way. Three key spaces still, not four.

Old keys go stale and stay inert. No migration, same reasoning as 7a: absence means
"never joined", so a stale key is harmless rather than corrupt, and this is mock
data in dev.

**The test pins the stored key.** `calendarEvents.spec.ts` never round-trips: each
case reads the literal string out of the fake `localStorage`, or writes through one
surface's path and reads through the other's with the reading id hard-coded.
Verified to fail — **7 red** with `eventId = item.id` reinstated. A round trip over
the same pair of functions stays green, which is the whole point.

### The day figure and the rows agree, and it is now gated

Yes. Not argued — measured, in a browser, across **every day in the month that has
anything on it**: 36 days, 14 of them rendering an events section, figure equal to
rows on all of them, and again immediately after an add. That assertion is in
`check:interaction`, so the gap cannot reopen quietly. BUGS.md's 7a entry is closed.

### What was built

| | |
|---|---|
| `ItemDetail.svelte` | The dialog. Focus in / trapped / returned, Escape and outside press, two-step delete. |
| `AddItemForm.svelte` | Three kinds, three stores. Markup only — the routing is a module. |
| `DayEventsSection.svelte` | Join, leave, `.ics`, ignore. |
| `calendarEvents.ts` | The event id boundary. One `eventIdOf` call in the whole calendar. |
| `calendarAdd.ts` | The routing, out where a gate can see it. |
| `ics.ts` | Pure builder, clock as a parameter; `downloadIcs` reads it at the boundary. |
| `actions/focusTrap.ts` | Move focus in, keep it in, put it back. |
| `ui/UnIgnoreButton.svelte` | `IgnoreButton`'s twin. Calendar only. |

### Calls made in the owner's absence

Each is reversible and each has a reason:

1. **`AddItemForm` does not use `arriveAtRow`.** The brief said to use it *if*
   adding should take the student to the row. It should not: `arriveAtRow` needs a
   DOM id, calendar rows carry none, and giving every row one would add a second
   arrival surface with its own gate needs. The form sits directly above the list it
   adds to, on the day it adds to. Confirmation is the app-wide toast, naming WHICH
   LIST the item went to — three kinds go to three places and picking the wrong one
   is otherwise discovered days later on another page.
2. **No new `RevealKind`.** Nothing here wanted one, and the union is still closed.
3. **A to-do is dated at the day's start, not the form's time.** The source stored
   the form's time; `todoToItem` renders every to-do "All day" and the quick list
   never offers a time, so that was a number nothing reads, contradicting the row it
   produced.
4. **Label and urgent are written to the annotation stores only**, not also onto the
   custom event. The source did both, and that was a live bug — see below.
5. **`customEventToItem` attaches the event to the row.** The source recovered the
   id with `item.id.replace(/^custom-/, "")`, which CONVENTIONS forbids and which is
   doubly hazardous here because the prefix genuinely appears twice.
6. **The dialog is mounted outside the view branches.** The agenda has no day panel
   and its rows open one too, and `dayPanel` is keyed on the selection, which a
   student can change from the keyboard while the dialog is open.
7. **`AddItemForm` and `DayEventsSection` are absent in agenda view**, matching the
   source. The agenda spans thirty days and has no single selected day to add to.
   Flagged rather than fixed, because "which day does the agenda's add form add to"
   is a design question and it is the owner's.
8. **The interaction gate was widened**, not just the layout gate. The brief only
   asked for `check:layout`, but the dialog's whole contract is behaviour no unit
   test in this repo can see, and writing a weaker unit test that looks like
   coverage is what the brief told me not to do. It found two real bugs.

### Where the source contradicts itself or is simply wrong

Three, all recorded in BUGS.md and none ported:

- **`AddItemForm.tsx` stores urgent twice** — on the event and in the override
  store — and `mergedSchedule` resolves `override ?? item.urgent`. So clearing the
  flag in the dialog wrote `undefined` and fell back to the copy on the event.
  **Un-marking urgent did nothing.**
- **`ItemDetail.tsx` reads a stale snapshot.** Its checkbox renders `item.urgent`
  off the row it was handed, which never changes, so it does not move until the
  dialog is reopened. Read live here, through the same rule the merge uses.
- **`ItemDetail.tsx` deletes on one click** of a button labelled "delete", with no
  undo anywhere in the system for it.

### What the new gate caught, which is the argument for widening it

Two bugs, on its first run, in code that was green on all five other gates:

1. **A TypeError on every close with focus in the label field.** A Svelte 5 prop is
   a getter; the parent nulls `detail`, the `{#if}` tears the subtree down a tick
   later, and the input's `onblur` fired in between and read `item.id` off null.
   **The declared type is true of the value and not of the getter.** Fixed by
   latching the row at mount. Now a CONVENTIONS rule.
2. **Focus did not return to the opener.** A pointer press does not reliably leave
   focus on a button, so a mouse user landed on `<body>`. `ItemRow` focuses its
   trigger before opening.

Neither is visible to 553 unit tests, `svelte-check`, the build, contrast or layout.

### The 48rem breakpoint

**Already there** — moved in the 7b follow-on (`7f12511`), so this phase verified
rather than moved it. Re-measured after 7c, driving the built page:

| width | week columns | column | agenda | fallback note | h-overflow | tallest title |
|---|---|---|---|---|---|---|
| 1330px | 7 | 133px | — | no | 0px | 60px |
| 900px | 7 | 109px | — | no | 0px | 60px |
| 769px | 7 | 90px | — | no | 0px | 60px |
| 768px | 7 | **90px** | — | no | 0px | 60px |
| 767px | 0 | — | 28 groups | yes | 0px | — |
| 700px | 0 | — | 28 groups | yes | 0px | — |
| 640px | 0 | — | 28 groups | yes | 0px | — |
| 375px | 0 | — | 28 groups | yes | 0px | — |

Unchanged from 7b's table within 1px of rounding (that run measured the same button
with a different rounding method). Titles still cap at 60px — three lines. No
horizontal overflow at any width, no console output at any width. **7c added nothing
to the columns**: the add form and the events section live in the day panel below
the grid, not inside a column.

### The gates

`npm test` 558 · `npm run check` 0/0 · `npm run build` clean ·
`check-contrast` 58/58 · `check:layout` **42/42** (was 36) ·
`check:interaction` **84/84** (was 60) · seven timezones 558 each.

### Loose ends for the next session

1. **CONTEXT.md is owed.** §14 still describes 7c as pending, §5's phase table and
   every count are stale. Not patched — the file is regenerated in full by rule, and
   a partial edit leaves stale claims sitting beside fresh ones with no way to tell
   them apart. It is a job of its own, as last session's entry says.
2. **Home's "count me in" is still inert.** The key space is settled and the wiring
   is now one line on each side. Left to the phase that owns Home so it arrives with
   its own gate coverage.
3. **The agenda has no add form and no events section.** Owner's call: what day
   would an agenda-level add form add to?
4. **The real-phone list, unchanged:** touch drag, and the month grid's 44px cells.
5. **The `custom-custom-` double prefix stands** (MIGRATION §9 defect 14). Cosmetic,
   internally consistent, and now harmless — nothing parses it, because the row
   carries its own event. Changing the minted id would strand every stored event for
   no gain.

---

## 2026-08-21 — session close: CONTEXT regenerated after two phases

**HEAD:** `bac3fbf` · 15 commits this session, all pushed · 507 tests · six gates
green · green in all seven timezones.

No code. This entry records the doc close-out and what regenerating CONTEXT.md
turned up.

### CONTEXT.md was regenerated, overriding the deferral

Deferred twice by the owner, with good reason — three calendar phases in flight, and
a stale-and-flagged file beats a half-patched one. `/handoff` says always. I
regenerated, and read all 1,769 lines first: **regenerating a file that size from
partial knowledge would silently drop standing decisions from phases 1–6**, which is
destructive rather than merely wrong.

The deferral was the right call and the regeneration was still overdue, because those
are different claims. **Stale is survivable; contradictory is not**, and the file had
crossed from one to the other.

### What the regeneration caught, which is the argument for the rule

Nine things, and only two were counts:

1. §5's phase table said the calendar was **"not started"**. It is two thirds built.
2. The preamble said the calendar **"lands in a later phase"**.
3. 451 tests / 20 spec files / 127 files / 55 commits — all stale.
4. **§7 listed `nowMinutes()` as the calendar's sanctioned client clock read.** The
   calendar declined it and reads the server's clock instead. A doc's claim about
   the future had decayed into a false claim about the present.
5. **§13 said the calendar's "next up" would be `arriveAtRow`'s third caller.** It
   never became one — the line is static in the source, so there is nothing to jump
   to, and inventing a jump would have forced a third `RevealKind`.
6. **§8's key-space table said `ignoredEvents` is "normalised through
   `eventIdOf()`".** That is now exactly backwards: the store normalises *nothing*,
   which was the whole fix.
7. §11 said two routes "render a heading". Two routes are now *built*.
8. §12 did not mention that five providers finally have a consumer.
9. Bare `§9 defect N` references, inherited, which now collide with CONTEXT's own §9
   (React-isms) — qualified to `MIGRATION §9`.

**Items 4, 5 and 6 are the ones worth the ink.** None is a count. Each is a
*forward-looking claim that came true differently*, and a patch would have left all
three sitting beside the correct text with nothing marking which was which.

The file gained **a new §14 for the calendar** (it is the second-largest surface now
and had no section), pushing gates → 15, standing decisions → 16, voice → 17, loose
ends → 18, timeline → 19. Every cross-reference re-checked against the new numbering.

### The other docs

- **setup_info.md** — the stale 451, and **the timezone sweep is now documented**
  there for the first time. It has caught two real failures and is part of the
  definition of green; it had no entry in the "how to run things" doc, which is how
  it went unrun against `reveal.spec.ts` for weeks.
- **DEPENDENCIES.md** — untouched. No package changed in 7a or 7b (verified by
  diffing `package.json` and the lockfile across the whole session).
- **secret.md** — does not exist; `git check-ignore` confirms it is ignored anyway,
  which is the point of having listed it before it exists.
- **BUGS / FINDINGS / TESTING / CHANGELOG / CODEMAP / CONVENTIONS** — all appended
  during the phases themselves; nothing further owed.

### Loose ends for the next session

Full list in CONTEXT §18. The four that decide what 7c looks like:

1. **`thrive:event-joins`** — the same key-space bug as 7a's, in a second store, and
   7c builds its only consumer. The mechanism is settled; what is open is whether the
   raw `Event.id` is right for joins (almost certainly yes) and a cross-surface test
   that is non-vacuous in **both** directions.
2. **`check:layout` extended to week and agenda** (owner: approved).
3. **The day-figure gap closes on its own** once events have rows.
4. **`ItemDetail` is the candidate third caller** for `escapeKey` / `clickOutside`.

Plus the real-phone list (touch drag, and the month grid's 44px cells), and
`CalendarView.detail` still declared and unwritten.

---

## 2026-08-21 — 7b follow-on: the week breakpoint moves to 48rem

**507 tests · six gates green · green in all seven timezones.** One code change,
three answers.

### The change

**`sm` → `md`. The week-to-agenda fallback now sits at 48rem.**

40rem was built first because that is the width MIGRATION §4 and the Next comment
both name. Measured, it gave **71px columns**, where a three-line clamp held "MGT
142 · Machine Learning for Business" without overflowing and it still read as three
short stacks rather than a phrase — about 57px of text width, narrow enough that a
long word breaks mid-word.

The owner's call, and the reasoning is worth keeping: **"fits" and "is legible" are
different bars, and anything that narrow falls back to the agenda perfectly well.**
A view whose whole job is to be read owes the second bar.

Re-measured after the move:

| width | week columns | column | agenda | note | h-overflow | tallest title |
|---|---|---|---|---|---|---|
| 1330px | 7 | 132px | — | no | 0px | 60px |
| 900px | 7 | 108px | — | no | 0px | 60px |
| 769px | 7 | 89px | — | no | 0px | 60px |
| 768px | 7 | **89px** | — | no | 0px | 60px |
| 767px | 0 | — | 28 groups | yes | 0px | — |
| 700px | 0 | — | 28 groups | yes | 0px | — |
| 640px | 0 | — | 28 groups | yes | 0px | — |
| 375px | 0 | — | 28 groups | yes | 0px | — |

89px buttons, ~75px of text per title — enough that whole words land on a line
rather than hyphenating. Titles still cap at 60px, the three lines they should be.
No console output at any width.

**The knob is the breakpoint, never a min-width.** A min-width puts back the
horizontal scroll the fallback exists to remove, which is what the Next source did
and what its own comment called wrong. Recorded in CONVENTIONS, because it is the
second time this phase that a measurement beat an assumption.

### The two answers that were not code

- **`check:layout` extension to week and agenda: APPROVED for 7c.** A 13,764px
  agenda on a phone is what a vertical-overflow gate is for. Moved in BUGS and
  TESTING from "recommended" to "approved, deferred out of 7b because the surface
  it guards was still moving" — the distinction matters, since the gap is not
  acceptable, only postponed.
- **Agenda rows naming their own date: KEPT.** The owner's framing, recorded because
  it generalises: *the right instinct when the source is simply wrong is to improve
  on it rather than port the mistake.* That is now the second such case in two
  phases — the first was the 40rem fallback the source claimed and did not have.

All nine of 7b's absence decisions were approved.

### Still open

Unchanged from the entry below: CONTEXT.md after 7c, the `check:layout` extension in
7c, `thrive:event-joins` in 7c. The 71px column entry is closed.

---

## 2026-08-21 — Phase 7b: the other two views and the filter bar

**507 tests · six gates green · green in all seven timezones · all three views
render.**

Worked end to end without stopping, at the owner's instruction. Every call I made
in their absence is below with the options weighed, so any of them can be reversed.

### The discrepancy to know about first

**The Next source never had the 40rem week fallback.** MIGRATION §4 says week view
is "not rendered below `40rem` — the parent falls back to agenda", and
`WeekView.tsx`'s own doc comment says it too. Neither is true of the code:
`CalendarView.tsx` renders `<WeekView>` at every width, and `WeekView` handles
narrow screens with `overflow-x-auto` + `min-w-[42rem]` — a horizontal scroll,
which is exactly what its own comment calls the wrong answer.

So "the source wins" does not apply: the source has no behaviour here, only a
contradiction between its comment and its markup. The 7b brief said to preserve the
fallback, so it is **built for the first time**, and the port drops the min-width
and the scroll — a scrollbar would mean the fallback was doing nothing.

### Decisions made in the owner's absence

1. **The fallback is CSS, not `matchMedia`.** Weighed three ways. CSS (two
   media-gated wrappers) has no hydration guess and no flash, and CONVENTIONS is
   explicit that a viewport question CSS can answer belongs in CSS — the JS form is
   reserved for cases with no CSS equivalent, like moving focus. `matchMedia` would
   have to guess during SSR, so one width of student watches the wrong view paint
   and get replaced after hydration. Doing nothing (matching the source's actual
   scroll) was rejected because the brief asked for the fallback. **Cost, stated:**
   both subtrees build, so a desktop pays for one unused 30-day `groupAgenda` and a
   phone for one unused week grid. Both cheap; `display: none` keeps the hidden one
   out of the a11y tree.
2. **Below 40rem, week renders exactly what agenda renders** — list, no day panel.
   The alternative was list + day panel, which is a shape no view has. Plus a line
   saying why, because the switcher still shows "week" selected and the page owes a
   reason rather than appearing to ignore the click.
3. **Agenda rows name their own date when the grouping is not by day.** The
   prototype rendered all three groupings identically, so grouped by type, thirty
   days of rows each read "9:30 AM" with nothing anywhere saying which 9:30 AM. A
   time without a date, in a list spanning a month, is the wrong half of the
   information rather than less of it. Not shown when grouped by day, where the
   heading already is the date. `showsRowDate` is the decision, in the pure layer.
4. **`urgentOnly` hides undated to-dos.** They can never be urgent — urgent is
   applied by `mergedSchedule`'s `annotate`, which runs over `data.dated` only — so
   switching it on emptied the page EXCEPT that section, which reads as broken.
   This is `filterSchedule`'s own recurring-classes rule finished, not a new one;
   it drops recurring classes under the same switch for the same reason.
   **`filterSchedule` itself is untouched.**
5. **Compact week rows carry no checkbox.** A 17px control in a 71px column under a
   three-line title is a mis-tap waiting to happen. The week answers "what does my
   week look like"; selecting a day lands in the day panel where the rows are fully
   tickable.
6. **Undated to-dos are `allDay: false` with an empty time**, departing from the
   source's `allDay: true`. `ItemRow` renders `allDay ? "all day" : timeLabel`, so
   every undated to-do was labelled "all day" — a claim about a DAY, when having no
   day is precisely what puts them in their own section.
7. **The day panel is a snippet.** Two views render it and only agenda replaces it.
   The source's `view === "agenda" ? agenda : dayPanel` reads as "agenda is the odd
   one out" and hides that the panel is shared.
8. **Chips get `min-h-11` below `lg` only.** A filter nobody can hit is not a
   filter, but eleven 44px chips on a phone is most of a screen and spending that
   on a pointer device buys nothing. Same shape `ShowMore` already uses.
9. **`check:layout` was NOT extended** to the new views. It is shared gate
   infrastructure and the brief did not ask; covered by hand at five widths instead
   and recommended for 7c. Recorded as a gap rather than quietly left.

### Fixed while building

**`line-clamp-3` was doing nothing.** It works by setting `display: -webkit-box`,
so the `block` beside it won the cascade — carried over from the source, where the
same pair sits together with the same effect. Measured at a 71px column: "MGT 142 ·
Machine Learning for Business" rendered **140px tall, seven lines**. Nothing warns
about an unclamped clamp: the text is all there and it only looks wrong if you
happen to be measuring row heights. Found while measuring the week columns for a
different reason. Fixed by dropping `block`; nothing exceeds 60px now.

**TESTING.md's coverage table was three specs short and three counts stale** —
`buildSchedule`, `calendarDay` and `calendarViews` were missing entirely and
`taskView`, `calendarStores` and `ignoredEvents` were behind. It sums to 507 across
23 rows now, checked programmatically rather than by eye.

### How streams and labels are kept apart

Structurally, not by styling, so an edit cannot flatten them by accident: separate
headings, separate `<ul>`s with their own `aria-labelledby`, separate prefs fields
(`hidden` / `hiddenLabels`), separate helpers (`toggleCategory` / `toggleLabel`),
different accessible-name shapes ("Hide Class" vs "Hide items labelled thesis"), a
dot on a stream and never on a label, and the labels section absent entirely when
nothing is labelled. **Nothing iterates a merged array.**

`allLabels` runs on the UNFILTERED merge, and that is load-bearing: from `filtered`,
hiding a label would remove its own chip and leave no way to switch it back on.
Verified — hiding "thesis" removed the row and left the chip, struck through.

### The by-hand browser pass

`check:layout` only ever sees month view, so week and agenda are unvisited by every
gate. Driven against the production build instead:

| Checked | Result |
|---|---|
| the 40rem boundary | 641px and 640px → 7 columns; 639px and 375px → agenda + the note. 0px horizontal overflow at all four |
| week columns | 132px at 1330, **71px at 640** — the tightest width that still renders them |
| the clamp | max 60px (3 lines) at both widths, after the fix |
| a day's counts across a view switch | 5 → 5, unchanged |
| streams vs labels | 11 stream chips, labels absent until seeded, then a separate list |
| hiding a stream | 57 month dots → 40, persisted, survived a reload, restored by "show all" |
| hide all | the warning appears rather than the page silently emptying |
| urgent only | 114 agenda rows → 0, undated section gone too |
| show ignored | the toggle reads "(1)", 114 rows → 115 |
| an undated to-do | real checkbox, empty time column, tick wrote `thrive:quicklist`, survived a reload |
| a chip by keyboard | focus on the `sr-only` input, ring on the chip, `rgb(24,43,73)` = `--thrive-primary`, Space toggles |
| console | no warnings or errors anywhere |

### The measurement trap that cost twenty minutes

Reading `outlineColor` the instant after focus landed returned `--thrive-body`, and
I nearly replaced `outline-primary` with an arbitrary-property form, justified by a
comment stating a measurement that was wrong. **Tailwind v4's `transition-colors`
includes `outline-color`** — the probe was reading 0ms into a 120ms fade. Wait past
the longest transition before reading a computed style. In FINDINGS, because the
wrong reading was specific and self-consistent and looked nothing like an artefact.

### Still open

- **CONTEXT.md is still not regenerated**, per the owner's decision — after 7c.
- **Week columns at 71px** at the 40rem breakpoint. Readable, tight. 48rem would
  give ~86px. The breakpoint is the owner's; recorded with the measurement so it is
  a decision rather than a rediscovery.
- **`check:layout` blind to two of three views.** Recommended for 7c.
- **`thrive:event-joins`** is still queued for 7c, unchanged.
- Nothing needed a new `RevealKind`, and nothing touched `filterSchedule` or an id
  key space. Neither hard stop was reached.

---

## 2026-08-21 — Phase 7a: the calendar's spine

**487 tests · six gates green · green in all seven timezones · `/calendar` renders.**

The first of three calendar phases. Month grid, selected day, that day's items.

### The four decisions the owner made up front

1. **"Next up" reads the SERVER's clock.** `nowMinutes` comes from
   `+page.server.ts`, off the same `new Date()` as `todayKey`.
   `calendarSources.nowMinutes()` — sanctioned client read #1 — consequently has
   no consumer, which is a change from what the last handoff expected. The reason
   is that Next's `CalendarView` was `"use client"` so its memo could only run in
   a browser; the Svelte one renders on the server first, where the same call
   paints one "next up" row and lets the browser swap it after hydration. The
   value freezes at page load either way.
2. **Old ignore keys are left inert, not migrated.** One ignored event reappears
   once.
3. **The day's figure keeps counting events** although nothing renders them until
   7c. Both alternatives were worse; BUGS.md states why.
4. Proceed as designed.

### What porting `buildScheduleData` turned up

Three things MIGRATION §2 does not say:

- **The `evt-${event.id}` line is the ORIGIN of the ignore key-space defect.**
  Fixture ids are `` `evt-${dayOffset}-${i}` `` (`mock/events.ts:287`, verified), so
  the calendar's item id is `evt-evt-3-1`. Kept: every calendar item id names its
  stream, and the label and urgent stores are keyed on that space. The fix belonged
  at the store.
- **A missing advisor yields a titleless-but-located appointment row.** `title`
  falls back to `"Appointment"` while `detail` still reads
  `advisor?.location ?? "In person"`. Unreachable with current fixtures; ported
  as-is with the fallback documented.
- **`timeOf` / `minutesFrom` duplicate what `taskToItem` already does.** Left
  duplicated on purpose — one is server-side, one is `localStorage`-side, and
  MIGRATION §3 records that split deliberately.

### The ignore key space, and what actually fixed it

`eventIdOf` strips one `evt-`. A raw `Event.id` starts with `evt-` too, so it
cannot tell its inputs apart — and **the store was normalising its own
arguments**, so Home's `evt-3-1` was stored as `3-1` while the calendar's
`evt-evt-3-1` was stored as `evt-3-1`.

The fix is two lines: `setEventIgnored` / `isEventIgnored` key on exactly the
string given. The calendar sheds its prefix at its own boundary. **No Home
component changed** — every call site there already passed `event.id` raw.
`filterSchedule` was always in the raw space, so Home was the broken side.

Verified to fail: reverting turns 7 assertions red. Verified live in one browser:
ignoring on Home writes `{"evt-0-0":true}` and `/calendar` reads the same key.

**And a lesson that outlived it.** One direction of the new cross-surface pair
still passes with the bug reinstated, because both sides then share the same
mangling. "Crosses two surfaces" is not the property that catches a key-space
split — *not sharing a transformation* is. In FINDINGS.

### The timezone sweep caught something that was not mine

`reveal.spec.ts` had `NOW` as a `Z` instant with `Z` due dates beside it, which
this repo's own rule forbids. `tsk-today` at `2026-08-21T23:00:00Z` is tomorrow
anywhere east of UTC+2, so it failed in Asia/Tokyo, Asia/Kathmandu and
Australia/Lord_Howe. **The bug was the fixture, not `describeDue`.** Fixed with a
`local()` helper; nothing outside the fixture moved.

The wider point: TESTING.md claimed the suite was green in all seven zones and it
was not. That file was written before the test was. A verification claim decays
like a comment does.

### `MiniCalendar`'s keyboard grid — verified by hand, not by a gate

`check:interaction` stays Home-scoped as instructed, and nothing in 7a argued for
extending it. But 42 cells, a roving tabindex and six key bindings are not
unit-testable, so it was driven against the production build. What was pressed and
what came back:

| Pressed | Result |
|---|---|
| — | 42 cells, exactly **1** tab stop, today selected and `aria-current="date"` |
| Arrow Right / Down / Left / Up | 08-21 → 22 → 29 → 28 → 21, focus and selection agreeing at every step |
| Home, End | 2026-08-16 and 2026-08-22 — six days apart |
| PageDown | August → September, focus survives at 09-01, still 1 tab stop, **document did not scroll** |
| PageUp | back to August |
| six ArrowUps | August → July, focused cell on screen and selected |
| click a trailing cell | August → September, 09-05 selected |
| tick a row | `thrive:task-done` → `{"tsk-003":true}`, fraction 0/2 → 1/2, survives reload |
| — | heading outline h1 → h2 → h3 with no skipped level; **no console warnings or errors** |

The PageDown row is the one worth keeping: the Next version's shared
`preventDefault()` sat *after* the branch that returns, so paging a month also
scrolled the page. Measured at 0 → 0 here.

### Deviations from the Next source, all deliberate

- **No `font-mono` anywhere.** `designSystem.spec.ts` fails on it. Values take
  `.thrive-numeric`; "next up:", the type/time toggle, the category tags and the
  "today" chip are words and take DM Sans. This is the largest visual difference
  from the prototype.
- `ring` → `outline` in `SquareGrid` (MIGRATION §9 defect 10).
- `border-2` → `border` on the month controls, matching `Button`'s 1px port.
- `role="columnheader"` moved off the `<abbr>` onto a wrapping div — svelte-check
  rejects a grid role on a non-interactive element, correctly.
- `requestAnimationFrame` → `await tick()` for the focus move. **Not an arrival:**
  navigation inside one widget, which CONVENTIONS carves out.
- Urgent renders through `Tag tone="urgent"` rather than a second hand-rolled
  urgent chip.
- `SquareCell` / `SquareGroup` are declared in `calendarDay.ts` and **re-exported**
  from `SquareGrid.svelte`, so the brief's "SquareGrid exports them" holds while
  the shapes sit beside the function that builds them.

### Not built, and not stubbed

`ViewSwitcher`, `WeekView`, `AgendaView`, `KeyBar`, `ItemDetail`, `AddItemForm`,
`DayEventsSection`. Nothing was stubbed to make anything compile. `ItemRow` has no
`compact` and no `onOpen`; `eventItemsForDay` is not called. **The one thing that
anticipates a later phase is `CalendarView`'s `detail` state**, which is declared
and never written, because the brief names it as one of the three things that node
owns.

`prefs.view` is effectively pinned to month: nothing can change it until `KeyBar`
and `ViewSwitcher` land.

### Answered after the report, and now settled rather than open

All four of 7a's closing questions came back. Recorded here so 7b does not
re-litigate any of them.

- **CONTEXT.md is regenerated after 7c, not now.** The owner's words: three
  calendar phases are in flight and a stale-and-flagged file beats a half-patched
  one. The `updated-at` stays behind and the hook will keep saying so — **that is
  the intended state, not a missed step.** Do not patch it in place in 7b; the
  regeneration is one job at the end of 7c.
- **`thrive:event-joins` is handled in 7c, not before.** It is MIGRATION §9 defect
  13 and it is the same bug 7a just fixed, in a second store: the join store is
  keyed on the calendar item id (`evt-evt-3-1`) where the ignore store is keyed on
  the raw `Event.id`. The reason to wait is the good one — **7c builds
  `DayEventsSection`, its only consumer**, so the decision gets made with the
  consumer on screen rather than in the abstract. It becomes a live bug the moment
  Home grows a "count me in" button, which is not this phase either.
- **The day-figure gap stands unless the owner says otherwise.** They are looking
  at it on screen. Assume it holds; do not pre-emptively change what the header
  counts or what the month grid dots.
- **375px goes on the real-phone list**, below.

### The real-phone list

Two things now wait on the same session with an actual handset, because a
simulated viewport cannot answer either:

1. **Touch drag on Home's task rows.** Carried from the previous handoff, still
   unaddressed.
2. **`/calendar`'s month grid at 375px.** The page is 1513px and passes the layout
   gate, but the cells are ~44px wide — at the touch-target floor, in a 7×6 grid,
   with a dot row inside each cell. Nothing measurable is wrong; it has just never
   been touched by a thumb.

### Still open

- **MIGRATION §9 defect 14** (`custom-custom-…` ids) is untouched and unscheduled.
  Cosmetic and internally consistent — `deleteCustomEvent` clears the matching
  `custom-${id}` — so it is noted rather than queued.
- `prefs.view` can hold `week` or `agenda` from a hand-edited store while nothing
  renders those views. Harmless today because no control writes it, and it stops
  being a question the moment `ViewSwitcher` lands in 7b.

---

## 2026-08-21 — session close: four questions answered, two features scoped

**HEAD:** `bfa0ac3` · 11 commits this session, all pushed · 451 tests · all six
gates green.

No code this entry. It records the owner's answers, which close four open
questions outright, and two features scoped in enough detail to plan against.

### Answered, and now settled rather than open

- **`COLLAPSED_TASK_ROWS` stays at 4.** A ~124px inner scroll is barely
  noticeable; losing a quarter of the visible tasks is. The grid not moving was
  the guarantee that mattered and it still holds.
- **`/calendar` keeps its card link** although its body is still a note. It is in
  `primaryNav`, the rail already links there, and the real body is the next phase.
- **`/classes` stays link-less indefinitely.** The card is the feature; the page
  was never needed. **Do not revisit.**
- **`Toast` having no caller is expected.** It and copy-to-list return on the same
  flag. Leave it mounted.
- **Touch drag stays unaddressed**, to be flagged again on a real phone.
- **A task moved past seven days leaving Home's list is fine.** `/assignments`
  later.

### The calendar is next, and it is the big one

**15 components, the largest surface in the app.** `CalendarView` is the only
stateful node; the other fourteen are the month grid, week columns, agenda, day
sections, item rows, the detail dialog, the add form, the key bar and the events
section.

**`buildScheduleData()` is still unported and is the gating piece.** It needs five
providers, all of which now exist. `lib/schedule.ts` is ported and tested, so the
pure layer is largely waiting on that one function.

Three things already queued to land there: the `eventIdOf` key-space defect's
calendar half, the "next up" arrival, and `nowMinutes()` finally getting a real
consumer.

### Scoped, not built: Ask THRIVE as a full page

**This replaces the earlier tabs-on-top idea. Do not build tabs.**

A **second left rail beside the nav rail**, so two rails sit side by side, holding
three sub-items — **Resources, Course Recommender, Career** — plus a chat window
and saved chat history.

Two constraints to design against rather than discover:

- **Saved chat history cannot live in `localStorage`.** It is the first persisted
  thing that is not a small override keyed by id, and it needs **Django or
  the RAG service a teammate is building**.
- **Two rails, one `nav` landmark.** The shell keeps exactly one `nav` in the a11y
  tree at a time; a second rail must not become a second competing landmark.

Also unsettled, and worth naming now: Resources and Career are the subjects of two
PARKED routes, so whether they become sub-routes of `/ask`, stay standalone, or
merely share a name is open. And `FEATURES.floatingAssistant` still exists — a
floating assistant plus a page with chat and history is two homes for one
conversation.

### Scoped, not built: Group Projects

A future **fifth nav item**: group members, a project holding tasks and subtasks,
and assigning a task to a person.

**It is the first feature that is not one student's private view**, and that is
the whole difficulty rather than a detail:

- **Real accounts.** MIGRATION §9 defect 2 — no auth on any server action — stops
  being a note and becomes a blocker.
- **A shared database.** Every persistence property in the store layer assumes one
  person's overrides in their own browser.
- **The fixtures model one student.** No second person, no group, no assignee
  exists anywhere in `mock/`.
- **The nav has four destinations by decision**, and the mobile bar has four slots.
  A fifth is the first addition since the trim to four.

### The planning consequence, stated plainly

Both scoped features move Django from "later" to the critical path. Neither can be
demoed on the mock layer at all — which is a different situation from the
appointment and request flows, which work today and are merely process-global.

### Docs updated

CONTEXT regenerated in full (and the regeneration caught a contradiction the
mid-session patches had left: §13 claimed two different phone heights in two
paragraphs). FINDINGS gained the vacuous-assertion lesson. CODEMAP's built-at
caught up to HEAD. CHANGELOG, TESTING and setup_info carry the counts.

---

## 2026-08-21 — copy-to-list follows its surface

**HEAD:** `5e6b3d1` · 1 commit, pushed · 451 tests green · all six gates green.

Third in the same family as the two below: an action whose result the student
cannot see reads as broken. The quick list lives in the floating To-do panel
behind `FEATURES.floatingTodo`, so with the flag off the copy succeeded, persisted
to `thrive:quicklist`, and showed nothing. Now gated on that flag. Visibility
only — store, logic, tests and toast all stay, and flipping the flag restores a
byte-identical row (verified by flipping it and re-measuring).

### The strip is right-anchored now, and it fixed a pre-existing shift

The brief asked that removing a control not move the others. Above `sm` that
already held — the `flex-1` content column pushes the strip right, and Edit sits
at x=761 with two controls or three.

Below `sm` it did not. The strip wraps to its own line, where it was LEFT-aligned,
so removing the leading Copy control slid Edit and Add-a-note 49px left (x=86 →
37). **Expanding a card did the same thing in reverse**, since that inserts two
reorder controls ahead of them — so this was a shift that already existed and
gating one control merely exposed.

`ms-auto` at every width. Measured after: Edit at x=244, last control's right edge
at x=340 on a phone, identical with the flag on and off.

### What I could not make identical, and why

Row heights are identical on a phone and the page is 3281px either way. **On
desktop one of four rows is 20px shorter** with the control hidden: the content
column gains 46px and that row's chip line stops wrapping to a second line. It is
a horizontal reflow, not the strip's geometry, and the only way to prevent it
would be to reserve 46px of dead space on every row forever — which would keep
that row needlessly wrapped. Card bodies stay 300px and the page 1218px, so the
grid is immovable.

### What broke — my own gate assertion, and it is the useful part

The first version of `copy-to-list appears exactly when the quick list does`
inferred the flag from the page: it looked for a To-do launcher and treated its
presence as "flag on". The selector `/to-?do list$/i` **matched the copy button's
own accessible name**, "Copy X to your to-do list" — so the check read the thing
it was gating as proof the gate was open. It passed with the guard AND with the
guard removed.

Caught only by running the verified-to-fail step. The flag is parsed from
`features.ts` now, the way `check-contrast.py` parses `app.css`, and it fails
correctly in both directions.

**New standing decision:** an assertion's expected value must never be derived
from the thing under test.

### Decisions made

- **`FEATURES.floatingTodo` gates the control, not a new flag** (brief). One word
  brings back the panel and the button together.
- **The strip is right-anchored at every width** (mine). Needed to honour the
  no-shift constraint below `sm`, and it removes an existing shift on expand. It
  does move the phone strip from left- to right-aligned, which is a visible change
  to the current state — flagged here rather than buried.
- **The toast stays mounted** even with no caller. It returns with the button on
  the same flag; removing and re-adding it would be churn.

### Loose ends carried forward

- **`Toast` has no caller while `floatingTodo` is false**, so it is unexercised
  outside its six tests. Not dead code — same flag restores both — but worth
  knowing that nothing on screen can currently raise one.
- Everything from the entry below is unchanged.

---

## 2026-08-21 — two follow-ons after 6b

**HEAD:** `df72ad1` · 2 commits, both pushed · 451 tests green · all six gates green.

Both were loose ends 6b's own handoff had just written down, closed the same day.

### 1. Each show-more control governs its own region

Loose end 6 from the entry below. Both disclosures on the Tasks card named
`tasks-card-list` — the whole list, including the done group neither expands.

Fixed by giving each region an id: `#tasks-open-list` renders only when there are
open rows (so it is never an empty box taking a `space-y-3` gap — safe, because
the footer control exists only when there are rows to hide) and
`#tasks-done-list` renders always, empty while collapsed, so the id its control
names is never absent.

The gate's selectors are `button[aria-controls="tasks-open-list"]` now, which
deleted the `.at(-1)` document-order hack that had cost two debugging rounds. Two
assertions hold the property.

### 2. A card links out only when its destination is built

`isBuiltRoute(href)` asks `primaryNav`; `SectionCard` renders its "View all" only
when the answer is yes. Decided in the one component that renders the affordance,
so all four cards got it at once and a fifth gets it free.

**Tasks, My Classes and Upcoming Events lost their link.** Today's classes keeps
`/calendar`.

`isKnownRoute` is the companion: a parked route and a typo both fail
`isBuiltRoute` for different reasons, and hiding a link over a typo is the silent
no-op this repo hates, so `SectionCard` warns in dev on an href in neither list.

**The layout claim, stated precisely rather than as "no shift".** A `min-h-11`
floor on the header row guarantees the band cannot shrink below the link's 44px
touch target. Desktop is pixel-identical — four bands at 67/103px, page 1218px.
**On a phone the Tasks band is 22px shorter**, because its description regains the
width the link occupied and sets on one line instead of two. That is a horizontal
reflow, not the button's height, and no floor can prevent it. Reported rather than
smoothed over.

### Decisions made

- **`primaryNav` membership IS the definition of "built"** (owner). Derived, so
  unparking a route restores its links with no edit.
- **`/classes` is unlikely ever to be built** (owner). Route and card stay; only
  the link goes.
- **`COLLAPSED_TASK_ROWS` stays at 4** (owner): a 124px inner scroll is barely
  noticeable, losing a quarter of the visible tasks is, and the grid not moving is
  what mattered.
- **Touch drag stays unaddressed** (owner), to be flagged again on a real phone.
- **A task past seven days leaving Home's list is fine** (owner); `/assignments`
  comes later.
- **A dev warning, not a throw, for an unknown href.** `PagePlaceholder` can throw
  because it IS the page; taking Home down over a "View all" would be worse than
  the broken link.

### What broke

Nothing in the product. Two authoring faults of mine, both fixed before commit: a
python re-indent that left the new wrapper's contents one tab short, and a first
attempt at the gate helper that factored the selector into a shared function —
which `page.evaluate` cannot see, since it serialises only the one function it is
given (`ReferenceError: tasksCardControl is not defined`).

### Loose ends carried forward

- **`/calendar` keeps its card link while its own body is still a note.** It is
  primary and the rail already links there, so the card is no worse. Revisit only
  if "in the navigation" and "has real content" stay apart.
- **Nothing gates the drag on touch** — unchanged, and deferred to a real phone by
  decision.
- **CONTEXT was PATCHED for these two changes, not regenerated.** §11, §13, §14 and
  §17, plus the counts in §5. The sanctioned same-session exception, flagged at the
  top of the file.

### Still open from earlier phases

Unchanged: §9 defect 1 (process-global mock stores, **BLOCKING** a multi-person
demo), shallow provider copies, `buildScheduleData()` unported, three dead
providers, `requestTypeHelp` with no consumer, the calendar half of the ignore
key-space defect, Home fitting 1218px rather than 1052px.

---

## 2026-08-21 — Phase 6b: task editing

**HEAD:** `5cdad70` · 4 commits, all pushed · 439 tests green · all six gates green.

Everything deferred from 6a. The persistence layer was already there from 3b, so
the work was wiring and the interesting parts were the three things the brief
asked to be handled deliberately.

### 1. The undo arrival: one tick IS enough, and here is why

Measured in a real browser, not reasoned about, and measured **both ways**.

`undoTick` unticks, then READS the derived list — Svelte's deriveds are pull-based,
so the post-undo list is available immediately with no flush — then asks
`planReveal` whether the restored row is past the collapsed slice, expands the card
if so, and only then calls `arriveAtRow`. Every write precedes the single `tick()`.

**The counterfactual is the part worth keeping.** With the expansion moved out of
that handler and into an effect, the hard case — a restored row hidden behind "show
more" — lands nowhere, focuses nothing, marks nothing, and logs **zero console
warnings**, because the gate drives the production build where the dev warn is
compiled out. Indistinguishable from a successful arrival at a row that was already
on screen. Exactly the silent no-op that was most feared.

So the reframe: **the flush count was the wrong question.** The rule is "write
everything before you arrive", and it is now in CONVENTIONS in those terms. The
loud failure is the gate assertion `a hidden row still gets its arrival mark`.

### 2. The tick resolution bug: not reintroduced

Home's rows carry a real `Task` object end to end. `taskToggle.toggle(task)` takes
the object; nothing in this path parses an id. `isTickable` does not arise here
because every row has a writable source by construction — the calendar's
`tickItem` dispatch is untouched.

### 3. The stat pills are still honest — and would not have been

This needed a change 6a did not anticipate. `TaskStatPills` counts
`item.due.urgency` off the **server's** descriptor. The moment a due date became
editable, "1 overdue" would have survived moving that task to next week: the
dashboard contradicting the list beneath it, which is the exact bug that moved the
counting to the client in the first place.

Fixed by resolving ONCE in `+page.svelte` and handing the same array to both. The
gate's `ticking every counted task takes its pill to zero` is still green, now via
real ticking rather than a seeded `localStorage`.

### Decisions made

- **Controls wrap to their own line below `sm`** (owner). Five 44px buttons is
  220px against a 343px card. Shrinking them would trade a layout bug for a WCAG
  2.5.8 failure.
- **No `justChanged` ring** (owner). The Next row marked a ticked task for the
  whole 6s undo window; this app has ONE arrival treatment and the ring is spent on
  the undo, which is the move that needs finding again.
- **"Needs a date" accepts no drops** (owner). Nothing to write —
  `Task.dueDate` is required. Enforced as a TYPE (`DatedGroupKey`), not remembered.
- **`TaskNotes`' `matchMedia('(hover: hover)')` is the THIRD sanctioned client
  read** (owner), and recorded in CONVENTIONS. It is not the deleted `hoverIntent`:
  that gated hover-to-reveal, which is CSS; this decides whether to move FOCUS, and
  no media query can do that.
- **Reordering only when the card is expanded** (mine, forced by 6a's flat-when-
  collapsed decision). Collapsed rows are a flat slice spanning groups, and sort
  keys are read per group, so a move across a boundary would persist a key and
  change nothing on screen — a control that appears to work and does not.
- **Commit-on-blur for the title**, which the Next source did not do (it committed
  only on Enter and Save). Requested for the gate. It forced the Cancel guard.
- **`AddTaskForm` keeps the source's native `<select>`** for priority; the
  three-radio rule was about `PriorityPicker`. Different question: three values
  being changed in a strip, versus one of four fields being filled in sequence.
- **`Toast` built and mounted.** Not scope creep: without it, copy-to-list is a
  silent no-op, because the floating quick list is feature-flagged off so the copy
  has no visible destination either.
- **`COLLAPSED_TASK_ROWS` stays at 4** — see the loose end below.

### What broke

Two real defects, both mine to find and both fixed:

- **Every date converter threw a `RangeError` on a "Needs a date" row.** Latent in
  the Next source; 6a made it reachable by surfacing those rows. Reproduced against
  the Next source before fixing rather than assumed.
- **`dragend` on a dropped row read a destroyed `{#each}` block's derived** —
  `derived_inert`, live in the production build with all six gates green. Found by
  dragging by hand.

And **defect 3 nearly returned twice.** The controls were one cause; the other was
inherited from 6a — title and chips on one wrapping line with the title
`flex-1 min-w-0` means the TITLE gives way, not the chips. Measured mid-build at
375px: a 90px title box, three lines, six characters a line. Fixed by giving the
title its own line; 303px and one line after.

Three authoring faults in my own probes and gate code: a synthetic `input` event
that left a submit button disabled (so "add a task" looked broken when it was not),
taking the FIRST `aria-controls="tasks-card-list"` control (which expands Done, not
the list), and a blind toggle that collapsed an already-open card and made the drag
check report SKIP for its own bug.

### Loose ends carried forward

- **The collapsed Tasks card scrolls ~124px inside its fixed body.** 6a measured
  299px of content against the 300px cap — it fit exactly. A desktop row is now
  61–81px rather than 54px and the collapsed body holds 424px. This is arithmetic,
  not styling: five 44px controls plus the 44px add button cannot fit 300px in any
  arrangement. **The grid still cannot move** (fixed height, asserted by two gates).
  `COLLAPSED_TASK_ROWS = 3` would fit and is a visible change to Home's densest
  card, so it is the owner's call, not this constant's. Recorded at the definition.
- **`TaskRow` now requires a `role="list"` container.** It renders
  `role="listitem"`. `/assignments` is the next caller and owes it that.
- **The two show-more controls on the Tasks card share `aria-controls`.** The done
  group's and the open list's both name `tasks-card-list`. It tripped the gate twice
  during authoring. Harmless to a reader, but two controls claiming the same region
  is not right and it is a trap for the next script.
- **Nothing gates the drag on touch.** HTML5 drag does not fire there at all, which
  is why the keyboard buttons exist; but no gate asserts the buttons are the only
  route on a phone.
- **`check:interaction`'s "nothing threw or warned" is per-gesture, not per-page.**
  Stated at the assertion now. When a feature adds a gesture, the gate must make it.

### Still open from earlier phases

Unchanged: §9 defect 1 (process-global mock stores, **BLOCKING** a multi-person
demo), shallow provider copies, `buildScheduleData()` unported, three dead
providers, `requestTypeHelp` with no consumer, the calendar half of the ignore
key-space defect, Home fitting 1218px rather than 1052px.

---

## 2026-08-21 — click only, an arrival cue, and a gate that can press a button

**HEAD:** `aadfca9` · 6 commits, all pushed · 389 tests green · all six gates green.

Five pieces, all follow-ons from the popovers landing earlier the same day.

### 1. Hover removed. Click only.

Tried in use and rejected by the owner: three pills sit in one row, so a cursor
crossing that row opened and closed panels nobody asked for.

`openedBy: 'pointer' | 'command' | null` went with it. Every job that state did
was about reconciling hover with click — which one opened it, whether a pointer
leaving should close it, whether tabbing in should pin it — so with one way in
there was nothing left to distinguish. It collapsed back to `open`, and three
branches that could only take one value went rather than sitting there as
decoration. Focus now moves into the list unconditionally on open, for the same
reason: it was conditional because hover must never move the caret.

**`hoverIntent.ts` deleted, not parked.** One caller, and nothing queued — the
calendar, appointments, Ask THRIVE — needs a JS hover gate that Tailwind's
`hover:` utilities do not already cover. Kept-in-case is how a lib grows things
nobody can delete later. `clickOutside` and `escapeKey` both still have callers
and stay. No user-facing string mentioned hovering.

### 2. The jump is visible now

The reveal moved focus and scrolled, which was correct and invisible: everything
on Home is on one page, so a student choosing an item saw nothing change and
assumed the click had failed. `focusRevealedRow` became `arriveAtRow`.

**Indigo inset ring, solid for most of 1200ms then faded.** Indigo because it is
the reserved "this is where you are now" colour and an arrival cue is that
sentence. An outline because it cannot move the layout, does not contest the
background wash or left border a task row already uses for priority, and follows
each row's own radius — so one rule covers both row shapes.

**The ring is a normal declaration and the animation only removes it.** That is
backwards until you notice the global reduced-motion reset forces
`animation-duration: 0.01ms !important`: a mark painted by a keyframe would be
invisible under reduced motion. Declared plus `animation: none` there leaves the
ring on, still cleared on the beat by the timer.

Only one row is ever marked. A second jump to the same row forces a reflow between
the class removal and the re-add, or the animation does not restart. The duration
is a token read by both the component and the gate, so there is one copy of it.

### 3. `check:interaction` is a gate

37 assertions. The case for it was already written: the other five gates were all
green on the version where pressing a pill did nothing.

**Verified to fail, three ways**, by breaking each thing on purpose — hover
reintroduced (6 red, including the original bug reproduced exactly), the arrival
mark not applied (4 red), the mark never cleared (2 red). That is the third
property every gate here is supposed to have and it is now demonstrated rather
than claimed.

It reads `--thrive-arrival-duration` from the running page rather than repeating
it, and it knows no fixture ids — the task ids it ticks to force a zero count come
from choosing the popover's own items and reading where focus landed. One check
reports SKIP rather than passing when the fixture cannot produce a reveal target
past a collapsed slice.

### 4. `arriveAtRow` is the standard, not the popovers' helper

Promoted and moved to `$lib/arrive`. Three things want it and only one exists
yet: the popover jumping to a task, 6b's undo returning to a task just ticked,
and the calendar's "next up" pointing at the item it names. Each could hand-roll
a `scrollIntoView` and each would arrive differently, and two arrival treatments
on one page is worse than either — a student learns the cue once.

The move also splits two halves that were only sharing a file: **`$lib/arrive`**
is "I know which row", **`$lib/reveal.svelte`** is "something else has to find
it". Reach for the channel only when the asker cannot know which card owns the
row. And the new file declares no runes, which is what a plain `.ts` should mean
here.

CONVENTIONS carries the rule plus the part that is easy to get wrong: **not every
focus move is an arrival.** Navigation inside a widget is not one, and neither is
focus recovery onto a container after the row it was on stopped existing —
marking that would tell the student they had been taken somewhere when they had
just lost their place. Both cases are live in the tree.

No behaviour change; same 37 assertions.

### 5. `arriveAtRow` says so when the row is not there

Asked and answered mid-session: it returned without doing anything, which is the
failure the arrival cue exists to prevent, sitting inside the cue. Now a
`console.warn` naming the missing id, behind `import.meta.env.DEV` — a warning not
a throw, because a student must never see an exception over a wayfinding cue.

`check:interaction` now fails on console warnings too, and **cannot see this one**
because it drives the production build. That limitation is written at the
assertion, and the branch was verified by hand against `vite dev` instead. See
FINDINGS: a check that appears to cover something it cannot is worse than no
check, because it converts an unknown into a false known.

### Decisions made

- **Hover is gone for good**, and its absence is asserted rather than assumed,
  because reintroducing it is the only route back to the swallowed-click bug.
- **Delete an abstraction that loses its last caller** unless a specific named
  surface wants it. `escapeKey` was rightly kept with no caller in Phase 4 — but
  against two named surfaces, not against the general chance.
- **A correct implementation of a bad interaction is still bad.** The `openedBy`
  work was real engineering spent making hover behave; the answer was that hover
  should not have been there.
- **Durations are motion or dwell**, and they do not share tokens.
- **`designSystem.spec.ts` now scans `.ts` too.** `.thrive-arrived` is the first
  class applied from JavaScript, and a typo there is the exact silent nothing that
  check exists to catch.
- **The aria-controls deviation is accepted** (owner): the panel names an id that
  is absent while closed. The alternative is a permanently mounted panel and two
  permanently mounted document listeners per pill.
- **No extra wording on the events card** (owner): the show-more label carries it.
- **Keep the honest 21-item popover** (owner); revisit a cap only if it gets very
  long.
- **`arriveAtRow` is the standard way anything on Home reaches a row** (owner).
  One treatment, one function, never a hand-rolled `scrollIntoView`.
- **`/swatch` stays as it is** (owner): the popover and the arrival ring are
  missing from it, and it is slated for deletion, so not worth the time.
- **`check:interaction` stays scoped to the widget that broke** (owner). Extend it
  when something else proves it needs one, not on principle.
- **1200ms stands** until a real student says otherwise (owner).
- **The CONTEXT patch is accepted** (owner). Full regeneration is for accumulated
  drift across a session, not a four-spot delta inside one. The rule stands for
  the normal case.
- **The calendar's "next up" uses `arriveAtRow` directly** (owner), unless it has
  to reach a row inside a collapsed day group — settle that when the calendar
  lands, not now.
- **`arriveAtRow`'s single `tick()` gets checked explicitly in 6b** (owner), and
  if one tick is not enough it must **fail loudly rather than quietly**. A silent
  no-op is the failure mode the owner most wants caught.
- **`arriveAtRow` warns in dev on a missing row** (owner, asked and answered). Not
  a throw: a student must never see an exception over a wayfinding cue. The branch
  is behind `import.meta.env.DEV`, so **no gate covers it** — `check:interaction`
  drives the production build. Verified by hand against `vite dev` instead, both
  directions. The gate now fails on console warnings anyway, with a note at the
  assertion saying exactly what it cannot see.

### What broke

Nothing in the product. Three probe/gate authoring faults, all mine: a stray
object-literal `=` for a `:`, one check name long enough to run into its own
detail column, and — earlier the same day — the `aria-expanded` selector that
matched `ShowMore`.

### Loose ends carried forward

- **`CONTEXT.md` was PATCHED for item 4, not regenerated.** Four spots: the file
  counts, the arrival paragraph in §13, one standing decision, and the
  CONVENTIONS rule count in CODEMAP. Grep-verified that no stale claim survives.
  Flagged because the standing rule is full regeneration and this is a deliberate
  deviation on a file that was thirty minutes old — say the word and it gets a
  clean regeneration.
- **`check:interaction` covers one widget on one page.** Scoped there by decision.
  The general component-test question is still open, and 6b's editing is the next
  thing that wants a rendered assertion.
- **The done-group branch in `TasksCard`'s reveal effect is still unreachable**
  from Home — no pill counts a done task. 6b's undo wants it.
- **`arriveAtRow` awaits ONE `tick()`.** Enough for every caller today (expanding
  a card is one state write). 6b's undo is the first case that might need two. It
  is named at the definition, in CONVENTIONS as a sharp edge, and in CONTEXT §17,
  and it now warns in dev — so 6b will hear it rather than having to know.
- **`CONTEXT.md` regenerated in full** at `d3621b9`. No longer a loose end.

### Still open from earlier phases

Unchanged: §9 defect 1 (process-global mock stores, **BLOCKING** a multi-person
demo), shallow provider copies, `buildScheduleData()` unported, three dead
providers, `requestTypeHelp` with no consumer, the calendar half of the ignore
key-space defect, Home fitting 1238px rather than 1052px.

---

## 2026-08-21 — the stat pill popovers

**HEAD:** `ae48473` · 3 commits, all pushed · 389 tests green.

### What was done

The loose end the previous entry called "queued, specified, NOT built". Designed
before building, as that entry asked, and the design is the part worth reading.

**The shape: the page owns an intent, the cards own their state.** A pill's
popover calls `reveal.request({ kind, id })` and knows nothing else. Each card
reads the channel, asks `planReveal(itsOwnList, itsLimit, id)`, and if the answer
is "mine, and hidden" it sets its OWN `$state`. `ShowMore` is untouched, so a
student can collapse the card again immediately.

Rejected: lifting all four cards' collapse into a page-level store (inverts
ownership for four cards to serve one feature), prop-drilling the channel (three
components in between have no interest in it), and a `<details>`-based disclosure
(the show-more control lives in the footer band, outside the disclosure content).

**Context, not a module singleton.** The channel is created in `+page.svelte`, so
it dies with the page — which is what keeps "collapse resets on navigation" true
by construction rather than by a `reset()` somebody has to remember.

**Grid immobility needed nothing added.** `.thrive-card-body` was already a fixed
height rather than a maximum, so expanding can only scroll. Verified: card tops
at 162,162,672,672 before and after a reveal, body still 300px.

### The measured contradiction, and the decision it forced

**The events pill counts 21 events this week. The card showed the next four
upcoming. Seventeen of the popover's items had no row on the page to jump to.**
Not a collapse problem — the pill's set and the card's set were different sets.

Asked, and answered by the owner: **collapsed is the next four, expanded is the
week, `/events` is still the rest.** It rests on both sets being prefixes of the
same ascending list, so `max(collapsedLimit, weekCount)` contains everything the
pill can list. `expandedEventLimit` carries the argument and a test asserts the
prefix property rather than trusting it. On a quiet week the `max` holds its floor
at four, so nothing changes at all.

### Decisions made

- **A zero-count pill is not a control.** No button, no `aria-expanded`, nothing
  to press. `statTones.calm` already made the number calm; this is the same idea
  applied to the interaction. Verified in a browser: a `<div>`, and neither hover
  nor a forced click opens anything.
- **A list, not a menu.** `role="menu"` brings a single tab stop and Tab-to-exit,
  which is right for a command menu and wrong for jump targets. Every item is an
  ordinary tab stop; arrows are a convenience.
- **`openedBy`, not `open`.** Two ways in is more than one boolean of state — see
  FINDINGS. This is the bug of the session.
- **Hover never moves focus.** Three pills in a row would fling focus about as a
  cursor crossed them. Focus moves in on click or keyboard only.
- **One focus-return rule:** restore to the pill if and only if focus is currently
  inside the panel. Covers Escape, click-outside and pointer-leave. Choosing an
  item hands off instead, because focus is about to land on the row.
- **`weekEventIds` deleted in favour of `thisWeek` on each event row.** Two shapes
  of one fact were going down; the pill had ids with no titles and the card had
  titles with no window.
- **`hoverIntent` holds the `(hover: hover)` gate**, rather than each component
  writing `matchMedia`. Same reasoning as `.thrive-numeric`: one expression of a
  rule, or it spreads.
- **Pills are 44px touch targets on mobile**, all three, including an inert one. A
  row of pills at two heights reads as a rendering fault.

### What broke

- **The pill did nothing when pressed.** Every gate green. See FINDINGS.
- **Three browser-probe checks failed on correct code** — the probe's own
  selector matched `ShowMore`, which also carries `aria-expanded`.
- **Two `svelte-check` a11y warnings**, both fixed structurally rather than
  suppressed: the arrow-key handler moved from the panel onto the items (where
  focus actually is), and the hover listeners moved into an action.

### Loose ends carried forward

- **`CONTEXT.md` is stale at `f8593b7`.** It is regenerated in full by rule, never
  patched, so it was deliberately left rather than half-updated. Sections 5, 6,
  13 and 17 all move. **This is the first thing to do next session.**
- **The 27 browser assertions are a throwaway probe, not a gate.** They caught the
  only real bug in the phase, and nothing in the repo can catch it again. Worth
  deciding whether they become `check:interaction` beside `check:layout`.
- **Home's phone height grew 2878 → 2949px.** Desktop unchanged at 1238px.
- **The done-group reveal branch in `TasksCard` is unreachable from Home today** —
  no pill counts a done task. Built anyway; 6b's undo wants exactly that path.
- **`aria-controls` names an id that is absent while the popover is closed.** The
  accepted cost of mounting the panel only while open, which is what makes
  `escapeKey` and `clickOutside` need no open state of their own.

### Still open from earlier phases

Unchanged: §9 defect 1 (process-global mock stores, **BLOCKING** a multi-person
demo), shallow provider copies, `buildScheduleData()` unported, three dead
providers, `requestTypeHelp` with no consumer, the calendar half of the ignore
key-space defect, Home fitting 1238px rather than 1052px.

`escapeKey` is no longer a loose end — it has a caller.

---

## 2026-08-21 — Phase 6a: Home, plus the repalette and the nav trim

**HEAD:** `f8593b7` · 10 commits, all pushed · 373 tests green.

> Date note: the previous entry and several `app.css` comments are stamped
> 2026-08-22, a day ahead of the real date. Commit hashes are the ordering that
> can be trusted.

### What was done

Three pieces of work in one session, in this order: the navy repalette and the
type rule (`8c283d6`, `922b8bb`, `41e891a`), the nav trim (`2fdefbb`), and
Phase 6a Home (`022b269`, `6bac960`, `ebeb895`), followed by two density passes
(`36395f0`, `074486d`) and a decisions-and-gates commit (`f8593b7`).

**Measured everything that was a pixel.** Drove the built page in the machine's
Playwright chromium at every step rather than reasoning about heights. That is
now the standing method for layout work, and it earned itself three times over
this session — see FINDINGS.

### Decisions made (this session's questions, answered)

- **Yellow is decoration on light surfaces**, a real graphic only on navy. Not an
  active indicator: "you are here" stays indigo, because two colours meaning
  "here" is how a reservation dies.
- **Gold `#c69214` rejected** at 2.79:1. `watch` already covers a legible warm
  accent.
- **`on-track` → teal.** The only reserved colour whose value changed.
- **Parked routes live in a separate list, not behind a flag.** A flag needs
  every surface to remember to filter; a separate list makes rendering a parked
  item structurally impossible.
- **Settings is parked.** Confirmed by the owner this session: nothing to
  configure yet.
- **`escapeKey` is kept** despite having no caller — the floating panels and the
  Ask THRIVE page will want it. Confirmed this session.
- **Tasks' collapsed view is flat; grouped on expand.** Asked and approved. The
  card carried ~190px of furniture before its first row, and at any cap that let
  the grid fit a laptop it showed one task.
- **Do NOT cut card rows to reach a 1052px viewport.** Confirmed by the owner:
  two task rows would make the card useless, and "show more" exists for exactly
  that. 1238px is the accepted result.
- **An `urgency: "unknown"` row gets its own group at the TOP.** Confirmed this
  session, and built. Loud is correct, invisible is not.
- **`contain: paint` stays** whether or not the phantom scroll is headless-only.
- **`playwright-core` added as a devDependency** — the first dependency since
  Phase 1. There is no zero-dependency way to measure real layout, and the
  alternative was leaving the bug ungated.

### Loose ends carried forward

**Queued, specified, NOT built — the stat pill popovers.** Clicking a stat pill
opens a popover listing the actual items behind the number: the overdue tasks,
the tasks due today, the events this week. Click always opens it; hover also
opens it on desktop. The items in the popover are clickable and jump to the task
or the event — **which means if the target row is hidden behind "show more", the
card has to expand and scroll to it**. That last part is the interesting
requirement: it couples the popover to the collapse state, so `collapseList` and
the cards' local `$state` need a way to be driven from outside. Worth designing
before building.

**Phase 6b is task editing:** ticking, undo, rename, priority, notes, due date
editing, drag to reorder, add task. `TaskRow` renders read-only with disabled
checkboxes today and a footer line saying so; that line goes when 6b lands.
`homeGroups.ts` is the read-only half of the Next app's `useTaskBoard` — the rest
of that hook is what 6b needs.

**Then, in order:** the calendar (15 components, the largest surface), then
appointments, then the **Ask THRIVE page** — three tabs (chat, class recommender,
job recommender), a chat window, and a saved chat history rail on the LEFT beside
the nav rail, so two rails sit side by side. Wired to a teammate's RAG service
later. `/ask`
exists as a placeholder route with the nav entry already in place.

**Strings keep being extracted** into `$lib/messages` as each surface is built.
That is the standing rule now, not a one-off for Home: Mandarin stays possible
only if no surface ships with inline copy.

### Still open from earlier phases

- §9 defect 1, the process-global mock stores. **BLOCKING** before any
  multi-person demo. Django is the fix.
- Provider copies are shallow; nested arrays are shared with the store.
- `buildScheduleData()` still unported — the calendar needs it.
- Three dead providers (`getSyllabi`, `getResources`, `getCurrentResume`).
- `requestTypeHelp` has no consumer.
- Home fits 1238px, not 1052px. Accepted.

---

## 2026-08-22 — Phase 5, the data layer

**HEAD:** `0dcca16` · 4 commits, all pushed · 324 tests green.

### The handoff correction that mattered

The previous entry said Phase 5 was "the 25 providers **against Django**". That
was wrong and was corrected before any code was written. Django does not exist
and is not being written here. This phase ports the providers against **the same
mock fixtures the Next app uses**. Django replaces the provider bodies much
later. No HTTP client, no API layer, no backend integration was written.

Anyone reading the old line and building an API client would have invented a
contract against a backend nobody has designed, and every guess would have been
load-bearing by the time it was discovered.

### What was done

Four commits, one per layer: fixtures + clock, the three stores, providers +
boundary, tests.

**Verified by mechanical diff, not by eye.** All 25 signatures diffed identical
against the Next source. The provider bodies were diffed comments-stripped, and
the only differences are the five intended ones. Eight of thirteen fixture
modules are byte-identical; the rest differ only in comments except `degree.ts`.
The old repo was confirmed untouched afterwards.

**Green in seven timezones**, UTC+14 to UTC−11, per the sweep TESTING.md
documents. This phase is entirely date-shaped, so the sweep was not optional.

### Decisions made

- **`Appointment` gains `slotId`.** Needed to release the right slot by id.
  Chosen over a side map in the store because it is the shape the Django model
  has anyway. Verified nothing in the tree constructs an `Appointment`, so no
  existing test broke.
- **`expectedCompletion` dropped** from the type and the fixture. It was a
  second, stale answer to a question the timeline already derives.
- **Copies stay shallow.** Faithful to the source. The nested-array hole is
  pinned by a test rather than quietly deep-copied, because deepening it is a
  behaviour change beyond a port.
- **No `resetStores()` export.** Test isolation via `vi.resetModules()` instead,
  to keep a test-only function out of the production surface.
- **`mock/` and `latency.ts` stay private.** Only `types`, `providers` and
  `labels` are public.

### Still open

- **§9 defect 1 — the process-global stores. BLOCKING.** Unchanged and
  unfixable at this layer. Django is the fix. Anything resembling a multi-user
  demo before then will have students booking over each other.
- **`buildScheduleData()` is still unported.** It was blocked on the five
  providers; they exist now. This is the obvious next task.
- **Shallow copies.** Documented, tested, not fixed.
- **`requestTypeHelp` has no consumer** in the Next tree — ported anyway, since
  the type picker it belongs under is a later phase. Delete it if that picker
  never lands.
- **Nothing renders any of this yet.** 25 providers and no route reads more than
  `getStudent()`. The data layer is ahead of the UI by design, but it means the
  only evidence it works is the test suite.

---

## 2026-08-21 — repo created, port through Phase 4

**HEAD:** `b0f7c3b` · **13 commits, all pushed** · first session in this repo.

Establishes the doc system here. It could not live in the old repo, which has
been read-only reference since Phase 1.

### What was done

**Inventory.** Read the frozen Next prototype at `4e0a65b` and wrote
`MIGRATION.md` — 1,449 lines, nine sections. Corrected three counts that were
wrong in the brief and are still wrong in the old repo's own `CODEMAP.md`: **25
provider functions** (not 21), **83 tests** (not 61), and `todayKey()` living in
`buildSchedule.ts` (not `format.ts`). Ran the suite and the contrast script to
verify rather than transcribe.

**Repo.** Created `rsm-msaad/thrive`, private, empty. Cloned to `~/code/thrive`.

**Phase 1 — scaffold + design system.** SvelteKit 2.63 / Svelte 5.56 runes / TS
strict / Vite 8 / `adapter-node` / Tailwind v4 / Vitest, npm. Ported
`globals.css` → `app.css` faithfully: all three layers, every token at identical
values, the 1px/1.5px distinction kept as two concepts, weight left at the call
site, light-only, no shadows. Fonts self-hosted via `@fontsource`. Dropped three
dead things (both shadow tokens, `.thrive-priority-label`) with the reason
commented in place. **Contrast gate 43/43.** Built `/swatch` as a visual diff
target.

**Phase 2 — pure logic + tests.** Ported `format.ts`, `schedule.ts`,
`buildSchedule.ts`, `calendarItems`, `calendarSources`, `ignoredEvents`,
`calendarPrefs`, `tickItem`, `quickList`, `data/types.ts`. **All 83 tests moved
with only an import-alias change and passed on the first run** — the strongest
evidence the logic really was pure. Made the one requested collapse:
`localDayKey(iso)` + `dayKeyOf(date)` → **`dayKeyOf(value: Date | string)`**.
Added three tests for it, since every ported test passed a `Date` and the string
branch had no coverage. Wrote `CONVENTIONS.md`.

**Phase 3a — `format.ts` test suite.** 73 tests. `describeDue` had none despite
being the most-used pure function in the app. Every branch, every field, the
boundaries rather than the middles, both private helpers via their public
surfaces, both DST transitions, both countdown thresholds from both directions.
**Verified green in seven timezones** from UTC+14 to UTC−11, including one with
a 30-minute DST offset.

**Phase 3a-fix — input guards.** `describeDue` was rendering `"Invalid Date"`
and `"in NaN months"` into the UI for an unparseable date and — worse —
classifying it `upcoming`, so a broken deadline was invisible. Added a fourth
state via a discriminated union. `formatClockTime` returned
`"NaN:undefined PM"`; now validates and returns `"--:--"`. **All 159 existing
tests passed unmodified**, proving neither guard changed valid-input behaviour.

**Phase 3b — persistence layer.** 14 `localStorage` keys plus `toast`, ported to
Svelte 5 runes as module singletons. Hydration is an explicit `hydrateStores()`.
102 new tests pinning the four properties. Dropped six React-only workarounds.

**Phase 4 — the shell.** Root `+layout.server.ts` and `+layout.svelte`,
`AppShell`, `SideRail`, `TopBar`, `BottomNav`, `nav.ts`, `PagePlaceholder`,
`SectionHeading`, `Avatar`, an `escapeKey` action, and 13 routes. Wired
`hydrateStores()`. Gated both floating widgets behind `FEATURES`. **First phase
with something to look at in a browser.**

### Decisions made

- **The doc system lives in this repo, not the old one.** The old repo is
  read-only reference; verified untouched after every phase.
- **Hydration strategy A**, by instruction: server renders un-personalised,
  overrides land after mount. Implemented as one explicit `hydrateStores()` call
  from the root `$effect` — the seam a single surface can later wait on.
- **Storage presence, not `$app/environment`,** decides browser-vs-server. No
  `localStorage` *is* the server, and it keeps the layer testable in Node with
  no jsdom.
- **`days: null`, not `NaN`,** on the unknown due descriptor. `NaN` is a
  `number` to the type system and flows silently into arithmetic; `null` forces
  the caller to narrow.
- **`@lucide/svelte`, not `lucide-svelte`** — the latter is legacy, pinned to
  Svelte 3/4 at v1.0.1.
- **`.svelte.ts` for the four rune-declaring files.** Forced: Svelte only
  processes runes there, and a plain `.ts` with `$state` is silently inert.
- **The `use*` prefix dropped** from every reactive reader. Nothing about them
  is a hook any more.
- **Stubbed `/assignments` and `/appointments`** although neither was on the
  Phase 4 list — both are nav destinations and `/assignments` is one of four
  fixed mobile slots, so omitting them put a 404 behind a permanent tab.
- **Probe before asserting.** Every suite was written against observed output
  from a throwaway probe. It caught two real things (see below).
- **Document out-of-scope defects as tests**, named as defect records, rather
  than fixing them or losing them.

### What broke, and what that found

- **A cross-surface store test failed and found a real pre-existing defect.**
  `eventIdOf` strips one `evt-` prefix, but the raw `Event.id` is itself
  `evt-3-1`, so the calendar keys the ignore store on `evt-3-1` and Home on
  `3-1`. Each surface is self-consistent; **neither sees the other.** Ignoring
  an event on Home leaves it showing on the calendar. No existing test caught it
  because each exercises one side, and the two Phase 2 cases encode
  contradictory conventions. **Recorded, not fixed** — picking the canonical key
  affects already-stored data.
- **One of my own Phase 3a tests was timezone-dependent** and the TZ spot check
  caught it. `"2026-02-30"` is a date-*only* ISO string, so it parses as UTC and
  rolls to Mar 1 in PDT but Mar 2 in UTC. A live demonstration of exactly the
  hazard the module exists to prevent. Fixed the assertion; no production code
  affected.
- **The `format.ts` probe revealed V8 is inconsistent** about invalid ISO dates:
  `"2026-13-01"` is `Invalid Date`, but `"2026-02-30"` rolls forward and parses
  fine. I would have written a wrong test from first principles.
- **A stale `node build/index.js` on port 3000** made a verification return 404
  and nearly had me conclude a route was not matched. Two orphaned listeners.

### Two known defects built correctly rather than reproduced

- **Page titles at weight 400** (MIGRATION §9 defect 4). Every `h1` sets
  `font-bold` at the call site. `PagePlaceholder` alone was seven of the twelve.
- **The leftover 2px strokes.** The rail, header and bottom bar all draw
  `border-*-2` in the prototype, with comments calling it "the standard 2px
  edge" — both leftovers from the reversed 08-12 direction. Ported at **1px**.

### Blockers

None hard. One decision is genuinely blocking a later phase: the ignore store's
canonical key space, because `taskBoard` and the calendar both depend on it.

### Next priorities

1. **Phase 5 — data providers.** All 25 signatures are inventoried in
   MIGRATION §2. This is the seam Django plugs into, and it unblocks Home,
   `/degree`, `/career`, and the calendar.
2. **Shared primitives** — `Button`, `Card`, `Tag`, `EmptyState`, `Countdown`,
   `DueChip`. The 20 `border-2` call sites arrive with `Button`; build them at
   the correct weight.
3. **Decide the ignore store key**, then fix it and convert the defect-record
   tests into real assertions.
4. **Re-set the timeline.** Release 1 "end of August 2026" and the control group
   both predate the rebuild decision.

---

## Open loose ends

Carried forward. Mirrored in `CONTEXT.md` §15.

| # | Item | Blocking? |
|---|---|---|
| 1 | **Ignore store key-space defect.** Home and the calendar key it differently. Needs a decision on the canonical key; affects stored data. | Phase where either surface lands |
| 2 | **Where an `urgency: "unknown"` row goes** in a list grouped by overdue/today/upcoming. The union makes it a compile error, so `taskBoard` cannot be ported without deciding. | `taskBoard` port |
| 3 | **Missing year** in `formatShortDate` and `fullLabel` — two dates a year apart format identically. Parked pending real screens. | no |
| 4 | **`countdownPhrase` counts to "13 months"** with no year branch. Parked with #3. | no |
| 5 | **`taskNotes` on `createOverrideStore`?** It duplicates the persistence logic, and the hardening it needed is the drift that argues for collapsing it. | no |
| 6 | **Home's placeholder copy.** Deliberately not `PagePlaceholder`. | no |
| 7 | **Mount `Toast`?** Store ported and tested; one import. Nothing raises one until the quick list exists. | no |
| 8 | **`useIgnoreUndo.ts` not ported.** Same shape as `taskToggle`. | floating widgets |
| 9 | **`formatShortDate` still emits `"Invalid Date"`** — the last unguarded function in `format.ts`. | no |
| 10 | **A parseable-but-wrong date still gets through `describeDue`.** V8 rolls `"2026-02-30"` into March. Needs a round-trip check, which is input validation rather than a parse guard. | no |
| 11 | **`SectionHeading` ported but unused.** No call sites until Home or the calendar. | no |
| 12 | **Nav has 11 destinations, 9 are placeholders.** Worth deciding whether the rail should distinguish built from unbuilt during build-out. | no |
| 13 | **`hydrateStores()` timing not observed in a browser** under a throttled connection. The un-personalised flash is by design but has not been looked at. | no |
| 14 | **Release 1 scope and dates need re-setting** against the rebuild. | planning |
