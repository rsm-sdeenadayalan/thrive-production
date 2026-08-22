# Conventions

Rules this codebase holds by agreement rather than by tooling. Each one exists
because breaking it produced a real bug that was hard to see — except the last,
which is about what goes into the documentation rather than into the code.

---

## Components never see a raw timestamp

**Every date is classified and formatted on the server, then passed down as a
string. A component receives `"Overdue"`, `"in 3 days"`, `"2:30 PM"`,
`"2026-08-17"` — never an ISO instant it has to interpret.**

### Why

Two failures, both invisible in normal use:

1. **A browser in a different timezone from the server disagrees about what
   "today" is.** A task due at 11:00pm on the 17th is "today" to the server and
   "tomorrow" to a student one timezone east. In Next this surfaced as a
   hydration mismatch. In SvelteKit it surfaces as SSR HTML that silently
   changes after hydration — quieter, and worse.

2. **A client-computed date freezes.** `describeDue()` called during render
   answers once and keeps that answer until something else re-renders it. A tab
   left open overnight insists an overdue assignment is still due tomorrow.

### How it is done

- **Read the clock in a `load` function.** `+page.server.ts` / `+layout.server.ts`
  call `new Date()`, pass it into `describeDue(iso, now)`, and return the
  resulting `DueDescriptor` — not the ISO string.
- **Return view models, not raw rows.** The Next app built `SlotView`,
  `AppointmentView`, `RequestView`, `VersionView`, `CourseworkRow`,
  `TaskWithDue`, `DayOption` for exactly this. Each has its date fields already
  rendered to strings. Keep that shape.
- **`todayKey()` is called once, on the server**, and travels down as a string
  that is compared with `===`. Never recompute it in a component.
- **`dayKeyOf()` is the only place a local day key is built.** It takes a `Date`
  or an ISO string. Do not hand-roll `toISOString().slice(0, 10)` — that shifts
  an evening item onto the next day anywhere behind UTC.

### The narrowed exception: anything the student can edit

A student can move a due date, and that edit lives only in `localStorage`. So
something has to reclassify it without a round trip.

**The rule is narrowed, not broken: the server still decides what "now" is.**

- A `load` function computes `nowISO = new Date().toISOString()` and passes it
  as a prop.
- The client re-runs `describeDue(iso, now)` — which is **pure and takes `now`
  as a parameter** — against that same instant.
- **The client never calls `new Date()` to ask what day it is.** There is still
  exactly one answer to that question and it is still the server's. Only the
  recomputation moved.

This is why `describeDue`'s `now` parameter exists. It is not a convenience or
a testing seam. Removing the parameter and reading the clock inside would
collapse the exception into the bug it was designed around.

### The three sanctioned client reads

Exactly three, all deliberate, all documented at their definition:

1. **`nowMinutes()`** in `calendarSources.ts` — minutes past midnight, for the
   calendar's "next up" line. Called from a handler or a memo, never during a
   server render, and only when the selected day *is* today. On any other day
   the caller passes `0`, which yields the first timed item.
2. **`matchesWide()`** in the floating-panel geometry — a `matchMedia` read, not
   a clock, but the same hydration shape and gated the same way. (Not yet ported;
   the floating panels are a later phase.)
3. **`TaskNotes`' autofocus gate** — `matchMedia('(hover: hover)')`, added in 6b.
   Opening the note panel is an explicit request to write, so focus lands in the
   field — but only where a keyboard will not cover the screen. On a phone
   autofocus throws the keyboard over half the card, and the note button sits in
   a thumb's resting arc, so the mis-tap cost is real.

   **This is not the `hoverIntent` that was deleted**, and the difference is the
   whole reason it is allowed. That one gated hover-to-reveal, which is CSS and
   needs no JavaScript opinion. This one decides whether to move FOCUS, and no
   media query can do that — there is no CSS form of it to prefer.

Note what is NOT on this list: `Date.now()` used as an id nonce, in `quickList.ts`
and `taskBoard.ts`'s `mintTaskId`. It is never parsed back into a day and never
asks what "now" is, so it is not a clock read in the sense this rule is about.
A nonce is not a date.

A third briefly existed and is gone: `hoverIntent` read `(hover: hover)` for the
stat pill popovers' hover opener. Hover was removed from that interaction on
2026-08-21 — three pills in one row meant a cursor crossing it opened and closed
panels nobody asked for — and the action went with it. **Hover-to-reveal in this
app is CSS**, Tailwind's `hover:` utilities, which compile to
`@media (hover: hover)` without any JavaScript needing an opinion. If a surface
ever genuinely needs the JS form, put the media query in one action rather than
in each component.

Anything else reading the clock on the client is a bug until argued otherwise
in review.

### Nothing enforces this

This is the part that changed in the port, and it is the reason this file
exists.

In Next, the `"use client"` / server-component boundary enforced the rule **at
compile time**. A server-only module could not be imported into a client
component; the build failed. The discipline was mechanical.

**SvelteKit has no such wall.** `+page.server.ts` and `+page.svelte` are
ordinary modules. A component can `import { describeDue }` and call it with no
`now` argument — the default parameter is `new Date()`, so it compiles, runs,
renders something plausible, and is wrong in a way no test and no type will
catch.

So from here the rule is **convention, and review is what enforces it**.

What to look for in a diff:

- `new Date()` anywhere under `src/routes/**/*.svelte` or in a component
- `describeDue(x)` called with one argument
- `.toLocaleDateString(`, `.toLocaleTimeString(`, `.getHours()`,
  `Date.parse(`, or `Date.now()` in a `.svelte` file
- a prop typed as `string` that holds an ISO instant and is formatted at the
  point of render
- a new `load` function that returns a raw provider row instead of a view model

Known accepted deviations, inherited and recorded in MIGRATION.md §3 so they do
not get relitigated as discoveries: the calendar's day heading and the agenda's
group headings call `toLocaleDateString` on an already-safe day key, and
`taskToItem` / `todoToItem` format a `timeLabel` on the client because their
source rows are `localStorage`-only. These produce locale-formatting
differences, not date drift.

Phase 7a adds two more of the same kind, both in `MiniCalendar`: the **month
label** and each **day cell's accessible date**. The reason they cannot move to
the server is structural rather than convenient — the grid pages to any month
with no round trip, which is the whole point of keeping classes as weekday rules,
so there is no finite set of months a `load` could pre-format. Both format a day
key already built from local parts by `fromDayKey`, so what varies between server
and client is locale wording, never which day it is.

7b adds two more of the same shape, both formatting a day key the browser chose:
`WeekView`'s weekday abbreviations, and the agenda's per-row date when its groups
are not days. Same reasoning — the week and the range are walked client-side, so no
`load` could have pre-formatted them, and what varies is locale wording rather than
which day it is.

Phase 8 and its redesigns add exactly ONE, and the arithmetic of getting there is
worth recording because the count went up and then back down.

`/appointments` briefly had two — `MyDayPane`'s day heading and `BookingPanel`'s
`dayLabel` — while a month grid was the day picker, because a grid that pages
anywhere has no finite set of days a `load` could pre-format. Reverting to the chip
strip removed the second: the chips carry their finished labels from the server, so
`BookingPanel` takes a `dayLabel` PROP and formats nothing.

**`MyDayPane`'s heading remains**, and now for a better reason than the grid gave
it: the clickable month can point that pane at ANY day in any month it pages to,
so the set really is unbounded. It formats a key already built from local parts by
`fromDayKey`, so what varies is locale wording rather than which day it is.

**Note what is NOT on the list:** every slot time, every chip label, every
appointment label and the whole confirmation are formatted on the server, and
`AppointmentView` carries no field a component could format wrongly except the
ISO bounds, which only `icsFromAppointment` reads.

Phase 9 adds **none**, which is the more interesting result. `/ask` renders
timestamps on every message in a conversation and every entry in the rail, and
all of them arrive as strings: `ConversationView` has no ISO field on it at all,
so there is not a timestamp available to a component that wanted one. That is
stronger than a convention about what components may do — `ask.spec.ts` asserts
the absence. Where a phase can reach that shape, it should.

### A viewport question that CSS can answer belongs in CSS

The same rule as hover-to-reveal, and 7b is where it was first tested on something
other than hover.

Week view needs seven readable columns, so below `48rem` the agenda answers
instead. That fallback is **two media-gated wrappers**, not a `matchMedia` read:

- CSS has an exact equivalent, so the JS form buys nothing. The reserved case is
  the one with no CSS equivalent — `TaskNotes`' autofocus gate decides whether to
  move FOCUS, and no media query can do that.
- A `matchMedia` read has to GUESS during SSR. One width of student would watch the
  wrong view paint and be replaced a beat after hydration, which is the quiet drift
  this whole file is about.
- It costs building both subtrees. Stated rather than discovered: a desktop pays
  for one `groupAgenda` over thirty days it will not show, a phone pays for one week
  grid. Both are cheap, and `display: none` keeps the hidden one out of the
  accessibility tree, so nothing is announced twice.

**Pick the breakpoint by measuring, not by naming a size.** 40rem was built first
because that is the number MIGRATION and the Next comment both use. Measured, it
gave 71px columns — clamped correctly and still not readable — so it moved to
48rem and 89px. "Fits" and "is legible" are different bars. And the knob is always
the breakpoint: a min-width would put back the horizontal scroll the fallback
exists to avoid.

**If a fallback ever hides a view the student explicitly chose, say so on screen.**
The switcher still shows "week" selected, because that is their choice and it is
honoured the moment the screen is wide enough — so the page owes them a reason
rather than appearing to have ignored the click.

What that list does NOT license: reading the clock. `nowMinutes` for the "next
up" line is computed in `+page.server.ts` from the same `new Date()` as
`todayKey`, and `calendarSources.nowMinutes()` — sanctioned read #1 above — has
no consumer as a result. It stays on the list for a caller that genuinely runs
only in a handler. In Next, `CalendarView` was `"use client"` so its memo could
only run in a browser; the Svelte component renders on the server first, where
the same call would paint one "next up" row and let the browser silently swap it
after hydration. The value freezes at page load either way, so the client read
costs a visible flip and buys nothing.

---

## Moving a student to a row goes through `arriveAtRow`

**One function, `$lib/arrive`. Never a hand-rolled `scrollIntoView`.**

### Why

Several things want to say "here is the row you asked about": a stat pill's
popover jumping to a task (built), 6b's undo returning to a task just ticked, the
calendar's "next up" line pointing at the item it names. Each could do it itself,
and each would arrive slightly differently — a different scroll `block`, a mark or
no mark, focus moved or only the viewport nudged.

**Two arrival treatments on one page is worse than either of them alone**, because
a student learns the cue once and then it means something else somewhere else.

### What it does, and what a caller owes it

`arriveAtRow(target)` awaits a tick, focuses the row, scrolls it with
`block: 'nearest'`, and marks it with `.thrive-arrived` for one beat.

A caller owes it two things:

- The row renders `id={revealRowId(target)}` and `tabindex="-1"`. `revealRowId` is
  the single place that id is built, so the caller and the row cannot drift.
- Whatever had to change for the row to exist has already happened — a card
  expanded, a filter cleared. `arriveAtRow` returns without doing anything on a
  missing row rather than throwing at a student; it is a courtesy on top of the
  real change, not the change itself. **In development it warns**, naming the id
  it could not find.

### The known sharp edge

**`arriveAtRow` awaits exactly one `tick()`.** If the row needs more than one
flush to exist, the arrival does nothing — no mark, no focus move, and a student
who sees no change concludes the click failed. Which is the bug the arrival mark
was built to fix, arriving by a different route.

**It is no longer silent about it.** `import.meta.env.DEV` guards a
`console.warn` naming the id it could not find, so the next caller that arrives
too early announces itself in a terminal instead of being hunted. Note what that
costs: `check:interaction` drives the PRODUCTION build, where the branch is
compiled out, so **no gate covers it.** Verified by hand against `vite dev`
instead — a normal arrival warns about nothing, a missing row warns exactly once.

### Settled in 6b: one tick is enough, but only if you make it enough

The question was checked in a real browser rather than reasoned about, both ways.
**The flush count is not the mechanism. The ordering is.**

`arriveAtRow` awaits one `tick()`, which flushes whatever has already been
written. So the rule for a caller is:

> **Make every state change the row's existence depends on BEFORE you call
> `arriveAtRow`. Never leave one to an effect that has not run yet.**

`TasksCard.undoTick` is the worked example. It unticks, then READS the derived
list — Svelte's deriveds are pull-based, so the post-undo list is available
immediately with no flush — then asks `planReveal` whether the restored row is
past the collapsed slice, expands the card if it is, and only then arrives. One
tick has every change to flush and the arrival lands.

**Measured both ways.** With the expansion moved out of that handler and into an
effect, the hard case — a restored row hidden behind "show more" — lands nowhere,
marks nothing, and logs **no warning in the production build**. Indistinguishable
from a successful arrival at a row that was already on screen, which is precisely
the failure this cue exists to prevent.

It fails LOUDLY now, as decided: `check:interaction` asserts the hidden-row
arrival, and that assertion is what goes red. The dev-only `console.warn` still
cannot be seen by any gate, so the gate is the loud part.

A caller that genuinely cannot write everything up front should say so and be
argued about in review — do not reach for a second `tick()`.

### What is NOT an arrival

Not every focus move. The distinction matters because the wrong cases would look
identical from outside:

- **Navigation inside a widget.** `StatPopover` moving focus between its own
  items. No row is involved.
- **Focus recovery.** `UpcomingEvents` focusing its list container after an event
  is ignored. The row focus was on has just stopped existing, and the container is
  the nearest thing that still means "you were here". Marking it would tell the
  student they had been taken somewhere when they had in fact lost their place.

### Asking versus doing

Two halves, and they are different modules on purpose:

- **`$lib/arrive`** — "I know which row." Plain `.ts`, no runes.
- **`$lib/reveal.svelte`** — "something else has to find it." The channel a
  popover writes a request into; the card that owns the row answers, expands
  itself if it must, and then calls `arriveAtRow`.

Reach for the channel only when the asker cannot know which card owns the row.
Otherwise call the function.

---

## Never resolve a row by parsing its id

**Attach the resolved source object at merge time and dispatch on that.**

`calendarSources` puts the whole `Task` or `QuickItem` onto each calendar item;
`isTickable` and the tick writer read `item.task` / `item.quickItem`. No id
slicing, no array search.

The previous version sliced a prefix off `item.id` and searched the server's
task array. It missed every task the student added themselves (those live in a
different store) and every undated to-do in the agenda (whose synthetic id was
never prefixed). Both failed the same way and **silently**: the guard found
nothing and returned, the checkbox appeared to tick, and the next render put it
back. No error, no log.

### Corollary: `eventIdOf()` takes a calendar item id, and nothing else

**The store keys on exactly the id it is handed. The one surface holding a
prefixed id sheds it at its own boundary.**

`eventIdOf()` strips one leading `evt-`. Given a calendar item id
(`evt-evt-3-1`) that recovers the raw `Event.id`. Given a raw `Event.id` — which
already begins with `evt-` — it **mangles** it to `3-1`, a key nothing uses.

The function cannot tell those two inputs apart, so no care at the call sites can
make it safe to call twice. This was a HIGH defect until Phase 7a: the store
normalised its own arguments, so Home's write to `evt-3-1` landed under `3-1`
while the calendar's landed under `evt-3-1`. Each surface was self-consistent and
neither could see the other.

What to look for in a diff:

- `eventIdOf` applied to anything that is not a calendar item id
- `eventIdOf` applied twice on one path
- a normaliser reintroduced inside `setEventIgnored` / `isEventIgnored`
- a **one-sided** test for a cross-surface store. The original bug hid behind two
  tests that each exercised one surface and both passed; `calendarStores.spec.ts`
  now writes through one surface's real path and reads through the other's.
  Even then, one direction of that pair still passes with the bug reintroduced,
  because both sides share the same mangling — the other four assertions are what
  catch it.

`isVisible` in `schedule.ts` strips the same prefix inline, because importing the
store into a module the server renders through would poison it. That is the one
sanctioned sibling, stated in both places. MIGRATION.md §9 defect 12 is the
record of what happens when a third copy appears.

### Corollary, settled in 7c: BOTH event-scoped stores share the raw id space

`thrive:ignored-events` and `thrive:event-joins`. A join and an ignore are both
facts about an EVENT, and one `DayEventsSection` row offers them side by side --
so if they keyed differently, that row would hold two ids for one event and would
have to remember which control took which. That is precisely the arrangement that
produced the 7a defect.

`calendarEvents.ts` is the calendar's one boundary and calls `eventIdOf` once,
handing the raw id back with each row. The join store, like the ignore store,
normalises nothing.

Note what makes this consistent rather than merely tidy: labels and urgent are
keyed by CALENDAR ITEM id for the opposite reason -- they annotate a row the
student may not own, on streams that have no event behind them at all. Three key
spaces, and the test for a fourth is "is this a fact about the event, or about the
row?"

### And the test shape, because the obvious one does not work

**Pin the STORED KEY, never a round trip.**

A store that mangles on write and mangles identically on read is perfectly
self-consistent about a key nothing else in the app uses. That is exactly what
7a's bug was, and a round-trip test passes throughout it.

So a key-space test must not share a transformation with the code:

- read the string straight out of the fake `localStorage` and compare it to a
  hard-coded literal, **or**
- write through one surface's real path and read through the other's, with the
  reading side's id hard-coded rather than derived.

Then break it on purpose and count the reds. `calendarEvents.spec.ts` goes 7 red
with `eventId = item.id` reinstated; that number is the evidence the file is worth
having.

---

## One filter, applied once

`filterSchedule()` runs on the whole `ScheduleData` before anything renders.
The month dots, the week columns, the agenda and the day lists all read the
already-filtered result.

This makes the old failure — a dot on a day with no row beneath it —
structurally impossible rather than something to remember. If a new consumer
needs filtered data, give it the filtered `ScheduleData`; do not filter again
downstream.

**Still true with three views.** 7b added week and agenda and neither filters for
itself: `CalendarView` calls `filterSchedule` once and hands the result to the
month grid, the week columns and the agenda alike. The property that falls out of
it is worth naming, because it is the one a reviewer can check in a browser:
**switching view does not change what a day counts.** The header figure, the
`n of m done` fraction and the month dots are all derived from the same filtered
data, independent of `prefs.view`. Measured across a view switch: 5 and 5.

### The one collection `filterSchedule` cannot reach

Undated to-dos. They are not in `ScheduleData` — they have no day to be in — so
they travel beside it as `MergedSchedule.undatedTodos` and only the agenda renders
them.

`visibleUndatedTodos` in `$lib/calendarViews` applies the two dimensions that CAN
apply to them, **by the same rules**, and it is the only place that is allowed to.
`showDone` is obvious. `urgentOnly` hides all of them, and that is not an
invention: urgent is applied by `mergedSchedule`'s `annotate`, which runs over
`data.dated` only, so an undated to-do can never carry the flag. Leaving them in
meant switching urgent-only on emptied the whole page except that one section,
which reads as a broken filter.

**This is `filterSchedule`'s own recurring-classes rule finished, not a new one.**
It drops recurring classes under `urgentOnly` for exactly the same reason, and says
so at that line. Nothing in `filterSchedule` changed, and nothing may: it is one of
the two things this project does not guess at.

---

## Store shape: overrides, never whole truth

Persisted state records **only what the student personally changed**, keyed by
id, with `undefined` meaning "never touched, use the source value".

**Corollary, learned in 6b: resolve those overrides ONCE per page, not once per
consumer.** Home has two things reading the same task list — the stat pills and
the Tasks card — and `+page.svelte` resolves for both. Each resolving its own
would let a moved due date restyle the card while the pill above it went on
counting the server's answer. Two views of one list that can disagree is the same
bug in a different place, and the pills were made client-side in 6a specifically
to stop it.

A bare set of "done task ids" cannot express *"I unticked a task that ships as
done"* — reload and it silently re-ticks itself. A write that matches the
source value **forgets** the override rather than storing it, so the store only
ever holds genuine divergence.

The store layer is not ported yet. When it is, this shape is the requirement,
and so is the "empty on the server, real after mount" ordering.

---

## A prop is a getter, so its declared type has a lifetime

**Any handler that can fire while a component is being torn down is reading a
prop the parent may already have revoked.**

In Svelte 5 a prop is a getter over the parent's state. `ItemDetail` declares
`item: ScheduleItem`, and that is true of the VALUE. The parent closes the dialog
by writing `null` into `detail`; the `{#if}` around the component tears the
subtree down a tick later. In between, the getter returns null while the
component's handlers still exist.

It threw, in production, on an ordinary dismissal: closing with focus in the label
field fired the input's `onblur` during teardown and `commitLabel` read `item.id`
off nothing. Found by `check:interaction`, which fails on a console error — no
unit test in this repo could see it, because the suite has no focus model.

**Two remedies, and prefer the second where it is honest:**

1. Guard the handler. Fixes one site, and the type says the guard is dead code, so
   review eventually deletes it.
2. **Latch the value at mount** — `const row = untrack(() => item)`. Fixes the
   whole class and states the assumption out loud.

The latch is only correct when the prop genuinely cannot change for the instance's
lifetime, and that has to be arguable rather than assumed. It is here: `detail` is
a snapshot, the dialog is modal so nothing can swap the row underneath it, and the
two fields that CAN change while it is open are read from their stores instead.
Where a prop really does change, guard the handler.

What to look for in a diff:

- a prop read inside `onblur`, `onpointerup`, a transition callback, an observer
  callback, or anything else that can outlive a conditional block
- a component that latches a prop which the parent DOES update — the mirror
  failure, and a silently stale view rather than a throw

Same family as 6b's `derived_inert` (a `dragend` on a row a drop destroyed). Both
are "the DOM outlives the state for one tick".

---

## A dialog owes six things, and attributes are three of them

`role="dialog"` and `aria-modal="true"` are claims. What they promise is
behaviour, and the Next source made three of those promises without keeping them.

The six, and where each lives:

| Obligation | How |
|---|---|
| Named | `aria-labelledby` pointing at the real heading |
| Announced as modal | `aria-modal="true"` plus the scrim |
| Focus moves in | `use:focusTrap`, `initial` selector |
| Focus is trapped | the same action |
| Focus returns to the opener | the same action, on destroy |
| Escape dismisses | `use:escapeKey` |

Two things that are NOT in the action, on purpose: it does not close anything, and
it does not make the page behind it inert. A non-dismissible dialog is a real
thing, and folding dismissal in would make it un-declinable.

**The opener must be focused before the dialog opens.** A pointer press does not
reliably leave focus on a button — Chrome does it, Safari on macOS does not — so
`ItemRow` calls `focus()` on itself in the handler before `onOpen`. Without it a
mouse user lands on `<body>` and the next Tab starts at the top of the page.

**A destructive action inside one needs a second step, and the second step needs
its geometry thought about.** In `ItemDetail` the safe control takes the position
the trigger occupied and holds focus, so neither a double-tap nor an Enter can
destroy anything. A confirm button rendered where the trigger was reintroduces the
accident the step exists to prevent. And Escape peels one layer: with the question
up it cancels the question, not the dialog.

---

## A mutation is a form action, and errors come back as values

**Nothing in this app fetches from a click handler. A change to server state is a
`<form>` posting to a named action, and a failure the student can hit is a
`fail()` rather than a throw.**

### Why

Three things fall out of it, and the first is the one that matters:

- **`load` re-runs after a successful action.** A booking appears in the day pane
  beside the panel and in the list below it with nothing to keep in sync by hand.
  A fetch would have needed a client-side cache and a decision about when to
  invalidate it, which is two more places to be wrong.
- **A per-row button works with no JavaScript.** `AppointmentList` renders a
  one-field form per row; the Next version called a server action imperatively
  from a click handler, so the button did nothing at all without JS.
- **`useTransition` becomes one boolean around one await.** MIGRATION §8.4 —
  there is no Svelte equivalent because there is no concurrent renderer, and a
  boolean is the honest shape.

### Errors are values, and the layer that knows chooses the words

`SlotUnavailableError` is caught in the action and returned through `fail(409,
…)`. Two people CAN want the same slot — the page was rendered before somebody
else took it — so a taken slot is an ordinary outcome the panel renders, not a
crash. **Anything else re-throws**, because a provider failing for a reason
nobody has thought about must not be reported to a student as a booking problem.

The message is the DATA LAYER's, passed through rather than replaced from
`messages.ts`. It throws two different sentences — "no longer listed" for an id
that does not resolve, "just taken" for one that has been claimed — and only that
layer knows which happened. Flattening both would tell a student somebody took a
slot that never existed. This is the one sanctioned exception to "every
user-facing string lives in `messages.ts`", and it is narrow: the copy still
lives in exactly one place, that place is just not this file.

### Every branch of an `enhance` callback ends in something on screen

`success`, `failure`, and **everything else**. The first version treated the
third as "nothing local to say", and a 403 made the confirm button visibly do
nothing — no confirmation, no alert, nothing a student could see. A press that
produces no response is the failure mode this repo treats as its worst.

### And the operational half: `ORIGIN`

A form action needs it, or every POST is a 403. See `setup_info.md`. `npm run
dev` is unaffected, so this fails only in the build — which is why it is written
down rather than remembered, and why both browser gates now set it.

What to look for in a diff:

- `fetch('/some-route', { method: 'POST' })` from a component
- an `enhance` callback with no final `else`
- an action that lets a domain error escape instead of shaping it
- a `catch` that swallows everything rather than re-throwing what it does not
  recognise
- a new POST surface with no note about `ORIGIN`

---

## A disabled thing in a composite widget takes `aria-disabled`, not `disabled`

**If a keyboard has to be able to REACH something it cannot activate, it must
stay focusable.**

> **No live example right now.** The case this was written for — a month grid whose
> closed days had to be crossable — was deleted with the booking grid, and the
> booking chips use plain `disabled` correctly, because a chip strip is a row of
> independent buttons rather than a composite widget: nothing has to be crossed to
> reach anything else. The rule stays because the distinction is the part that is
> easy to get wrong, and the companion below IS live.

The month grid's closed days were the case. A student arrowing across a month had
to be able to cross a shut weekend to reach the Monday behind it, and a
`disabled` button cannot receive focus at all — so the walk would stop dead at
the first closed cell.

Two things follow, and both have bitten:

- **The cursor and the selection become two values.** With one, arrowing onto a
  focusable-but-unselectable day either selects it (booking days by accident) or
  refuses to move (breaking the spatial model, where ArrowDown means "a week
  later"). `MiniCalendar` keeps `cursorKey` whose `null` MEANS "the selection", so
  the second value only exists on the exceptional path.
- **The handler is what refuses, so the handler needs a test.** Playwright reads
  `aria-disabled` the way assistive tech does and will not click it without
  `force` — which is what turns the assertion into a real one: the click is
  pressed through and the handler declines it.

### The companion: a scrollable region must be focusable, and a linter disagrees

axe's `scrollable-region-focusable` requires `tabindex="0"` on anything with
overflow, or its content is unreachable by keyboard. Svelte's
`a11y_no_noninteractive_tabindex` objects to it on a non-interactive role. The
chat log is both.

**Accessibility wins, suppressed at that one site with the reason in the markup.**
Never repo-wide, and never by relaxing the check — `npm run check` stays at 0
errors and 0 warnings.

And the finding underneath it, which is the more useful half: **a `min-h-0` chain
makes a child able to shrink, but something still has to give it a height to
shrink within.** Until the chat panel had one, the log never overflowed, the
document grew instead, and the tabindex was guarding nothing. The gate said so by
permanently skipping its own keyboard-scroll assertion.

What to look for in a diff:

- `disabled` on a `gridcell`, a `tab`, an `option`, or a roving-tabindex item
- a single value used as both "what is chosen" and "where focus is", in a widget
  where some items cannot be chosen
- `overflow-y-auto` on an element with no `tabindex`
- a `min-h-0` chain with no height at the top of it
- **`flex-1` on an element that also sets a height.** It governs the MAIN axis, so
  it is a width in a row and a height in a column — and in a column it silently
  beats the `h-` beside it. Moving a panel between the two changes what it
  constrains. This shipped once: the chat log stopped being a scroll container and
  no assertion failed, because the only signal was `check:interaction` SKIPPING
  its own keyboard-scroll check.

---

## Layout numbers are tokens, and there are three of them

**A container width, a gutter, and a line length are three different questions.
Never solve one with another, and never type any of them into a component.**

| Token | Utility | What it answers |
|---|---|---|
| `--container-page` (80rem) | `max-w-page` | how wide may a page get |
| `--container-wide` (96rem) | `max-w-wide` | …and `/calendar`, which wants more |
| `--thrive-page-gutter-x` (2.5rem) | `lg:px-page-x` | how far off the edges does it sit |
| `--container-measure` (68ch) | `max-w-measure` | how long may a LINE OF TEXT get |

### Why the shell does not own the width

It used to: `max-w-6xl` on `AppShell`'s `main`. One number governed every route, so
a page that wanted more width could not have it without widening Home by accident.
The shell provides the gutters; **each page names its own measure.** How wide a
page should be is a property of what is on it.

### The gutter and the cap are two knobs and you need both

Learned by getting each wrong in turn. 72rem left ~120px of dead margin either side
at 1512px, so it went to 96rem — and then the cap stopped biting at that width
entirely, the gutter collapsed to the shell's 20px of padding, and content ran to
the edge. **A gutter alone does not solve a 2560px monitor; a cap alone does not
solve a 1512px one.**

### And the line length is separate from all of it

A paragraph at 1500px is not readable. So containers fill their allowance and TEXT
does not: page intros and standing notes take `max-w-measure`. Capping the
container instead would leave the dead margin exactly where it was.

`ch` rather than `rem`, because the constraint is characters per line and `ch`
tracks the font.

**Put the cap on the element that OWNS the text.** A full-width `<p>` wrapping a
capped `<span>` looks identical and is not the same thing — the element whose line
length matters is the one with the text in it, and a gate measuring paragraph
widths reads the wrapper.

What to look for in a diff:

- `max-w-` followed by a Tailwind size step (`max-w-5xl`, `max-w-2xl`) on a page or
  a page-level region, rather than one of the four tokens above
- a `px-` on `main` or a page root that is not `page-x`
- a widened container with no prose cap added in the same change
- a cap moved onto a wrapper instead of onto the text

---

## No personal names in documentation

**No doc in this project names a person.** Not a teammate, not faculty, not staff,
not a student. Refer to the role instead: "the backend work", "the faculty lead",
"a teammate", "the owner".

This applies to every `.md` at the repo root and to any new one. It does **not**
apply to fixture data — `mock/student.ts` and `mock/appointments.ts` carry the names
the app renders, and those are data rather than documentation.

**Removing a name must not remove information.** If a sentence stops making sense
without it, rewrite the sentence. The advisor entry in CONTEXT §12 is the worked
example: it named two people, and what it was actually documenting is that one is
in-person-only and the other has a remote mode — which is the distinction the
booking panel's mode filter exists for. It now says that, and points at the fixture
file.

An address is not a mention. The repo slug and the clone URL stay, because there is
otherwise no way to find the repo.

What to look for in a diff: any capitalised pair that is not a place, a product or a
technical term. `grep -rniE "prof\.|@ucsd\.edu"` catches the obvious cases.
