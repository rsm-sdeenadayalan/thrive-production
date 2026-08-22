# BUGS

Defects found and fixed, and the patterns behind them. Newest first.

Note on links: this repo has no PRs — all commits go direct to `main`
(solo, no review gate yet). Commit hashes stand in.

---

## 2026-08-21 (later) — a gate that could not fail, and a bug that was not one

### The assertion read the first `<p>` and called it the date

`e89c1a7`. The owner reported that clicking a day in `/appointments`' month grid did
not move "Your day", and pointed out that `check:interaction` was supposed to assert
exactly that and had been green throughout.

**The feature was not broken.** All 42 cells drive the pane, in the dev server and
in the built app, on both advisors, at 1512/1280/900px, for in-month cells, for
trailing cells from an adjacent month, and after paging. `MiniCalendar` is fully
controlled, `MyDayPane` reads the same `browseDay` that fills the cell navy, and
nothing between them latches.

**The assertion, however, could not have caught it if it had been.** Two holes:

1. It read `section[aria-labelledby="my-day"] p` -- *the first paragraph in the
   pane* -- and asserted only that the text differed. It never looked at the list.
   Latch the rows and leave the date reactive and this stays green forever.
2. It took the FIRST eligible cell, which is always inside the displayed month. The
   adjacent-month trailing cells -- the ones a student reaches for at a month
   boundary, and the ones the owner named -- had never been clicked once.

And "the first `<p>`" is only the date line while the date line happens to be first.
Both paragraphs now carry hooks (`[data-my-day-date]`, `[data-my-day-scope]`) so
neither can stand in for the other.

**THE PATTERN: an assertion that reads a position rather than an identity is a
false green waiting for a layout change.** The fix is a hook on the element, and a
check on the thing the user actually reads -- which was the list, not the date.

### `check(name, true, 'a sentence')` is not an assertion

`280cb2a`. `'the calendar is allowed more width than the rest'` was asserted as a
literal `true` with prose for a reason. It could never go red, and its prose went
stale the moment the cap changed -- it was still claiming 96rem after the token was
deleted. Replaced with a real comparison of the two routes' measured gutters.

**Grep for `check(` calls whose second argument is a literal.** They are load-bearing
in the count and load-bearing nowhere else.

### The symptom was real even though the bug was not

Worth keeping separate from the two above. Two things made a working feature read as
broken, and neither is a defect in the reactive graph:

- **The result was 270px above the control**, and off-screen entirely at an 800px
  viewport height, because the grid's last row was already past the fold.
- **Weekly recurrence made two days look identical.** Aug 24 and Aug 31 both show
  MGT 142 at 9:30. The only differentiator was `text-2xs text-muted-ink` (11.25px)
  in the far corner of the heading row.

**THE PATTERN: before hunting a reactivity bug, check whether the change is VISIBLE.
"Nothing happened" and "something happened where I could not see it, and looked the
same when I could" are the same bug report and different bugs.**

---

## 2026-08-21 — after Phases 8 and 9: the redesigns and the deploy

### A `flex-1` silently beat a height token, and only a SKIP said so

**Found by:** `check:interaction`, by skipping. **Fixed in:** `63bb79f`.
**Severity: MEDIUM** (the composer walked off the bottom of a long conversation).

Ask THRIVE's chat panel carried `flex-1` alongside `xl:h-[var(--thrive-chat-height)]`.
While it sat in a `flex-row` beside a rail, `flex-1` governed WIDTH and the height
token governed height. When the rail was removed the panel became a `flex-col`
child, where `flex-1` sets `flex-basis: 0%` plus grow — which governs the MAIN
axis, now the height, and beats the `h-` beside it.

So the panel took its content's height, the log never overflowed, and the document
scrolled in its place. Every assertion still passed. The only signal was
`check:interaction` reporting **"a keyboard can scroll the log — SKIP: could not
make the log overflow"**, and the layout looked entirely fine.

Fixed by gating it: `xl:flex-1`, so it applies only in the row.

**Pattern to watch:** `flex-1` means different things in a row and a column, so
moving an element between the two changes what it constrains. And **read the SKIP
lines** — a skipped assertion is a result, not an absence.

### Two `<nav>` landmarks both labelled "Primary"

**Found by:** an `aria-current` count that came back 2 instead of 1.
**Fixed in:** `45765fe`. **Severity: LOW** (a gate bug, not a user-facing one).

`SideRail` and `BottomNav` both carry `aria-label="Primary"`. That is CORRECT —
whichever is displayed is the primary navigation, and they are never displayed
together, since the rail is `hidden lg:flex` and the bar is `lg:hidden`. But both
are in the DOM at every width, so a gate scoping by the label matched both and
counted one `aria-current` twice.

Fixed with `data-nav="rail"` / `data-nav="bottom"` hooks rather than by renaming a
label that was right.

**Pattern to watch:** `display: none` removes an element from the accessibility
tree and NOT from `querySelectorAll`. A selector is not a proxy for what a screen
reader sees.

### `process.env` in `vite.config.ts` broke `npm run check`

**Found by:** `npm run check`. **Fixed in:** `9a50383`. **Severity: LOW.**

Selecting the adapter from an environment variable needs `process`, and this
project has no Node types — `DEPENDENCIES.md` records rejecting `@types/node` in
Phase 5 on the rule "do not add a dependency where the platform already answers".

Fixed by reading through a narrowed `globalThis` rather than by reversing that
decision for one property access.

**Pattern to watch:** a config file is type-checked by the same project it
configures, and it is the one file most likely to want host globals the app does
not have.

---

## 2026-08-21 — Phases 8 and 9

### Every form submission returned 403, and only in the built server

**Found by:** `check:interaction`, the first time it tried to book anything.
**Fixed in:** `8c4f68e` (gates) and `a39fa55` (the doc). **Severity: HIGH** — the
feature was entirely non-functional in production.

`POST /appointments?/book` came back `{"message":"Cross-site POST form
submissions are forbidden"}`. `adapter-node` cannot know the public URL it is
served on, and SvelteKit's CSRF check compares a POST's `Origin` header against
the URL it thinks it is serving. Without `ORIGIN` set it guesses, the guess does
not match, and the POST is refused.

**Two things made it invisible until Phase 8.** Nothing in the app had ever
posted anything — Home and the calendar write to `localStorage` — so the whole
app was GET-only. And **`npm run dev` is unaffected**, because Vite serves on the
origin it reports. So booking worked perfectly in development and failed
completely in the build, which is the worst possible split.

Both browser gates now set `ORIGIN` when they spawn the server. That is not a
workaround: it is the same variable a real deployment must set, so the gates now
drive the app the way it actually has to be run. `setup_info.md` records it,
including the reverse-proxy alternative and why `csrf: { checkOrigin: false }` is
the wrong reach — the check is the only thing in front of form actions that have
no auth yet.

**Pattern to watch:** *a capability the app has never used has never been
configured.* The first POST, the first upload, the first WebSocket will each find
their own version of this.

### The 403 was silent, which was the worse half

**Found by:** the same run. **Fixed in:** `b034b31`. **Severity: HIGH.**

The `use:enhance` callback handled `result.type === 'success'` and
`'failure'` and treated everything else as "nothing local to say". A 403 is
`type: 'error'`, so the confirm button **visibly did nothing**: no confirmation,
no alert, no console message a student would ever see.

A press that produces no response is this repo's worst failure mode, and it is
the same shape as the id-parsing tick that "worked" and reverted. Every branch of
both `enhance` callbacks now ends in something on screen, via
`messages.appointments.errors.unexpected`.

**Pattern to watch:** an `else` that says nothing. In a handler with three
outcomes and two branches, the third outcome is a silent no-op.

### The month grid announced past days as "too far ahead to book"

> **Subject since deleted.** The month grid as a day picker was reverted, so the
> code this describes is gone. Kept because the PATTERN is not: two conditions
> collapsed into one message because they produce the same visual state.

**Found by:** a new `check:interaction` assertion, written to check exactly this
distinction. **Fixed in:** `79d1a63`. **Severity: MEDIUM** (screen-reader only).

`labelFor` computed `outsideWindow = dayKey < todayKey || dayKey > windowEnd` and
mapped both to one sentence. A month grid **always renders six leading cells from
the previous month**, so a grid opened on the current month announced last
Tuesday as too far ahead.

Both cells are grey and both refuse the click, so the accessible name is the only
channel where that difference exists at all — which makes it the only place it
could be wrong unnoticed. Three answers now: `alreadyPast`, `beyondWindow`,
`nothingOpen`.

**Pattern to watch:** two conditions collapsed into one message because they
produce the same VISUAL state. The visual state is not the whole state.

### `BOOKING_WINDOW_DAYS = 23` was one day short of the rule

> **Subject since deleted.** The separate booking window went with the month grid;
> the window and the published fixture are the same thing again. Kept because the
> pattern is live anywhere two numbers have to agree with nothing asserting it.

**Found by:** `availability.spec.ts`, which freezes the worst case on purpose.
**Fixed in:** `2e6dba4`. **Severity: LOW** (a day or two of the grid greyed for
no reason a student could see).

The window is one calendar month, which can reach `today+31`. 23 business days
from a Monday reaches day 30. 25 reaches day 32.

The instructive part is that the arithmetic was reasoned about and got the
inclusive/exclusive boundary wrong, and the test that caught it only caught it
because it froze **a Monday in a 31-day month** rather than a convenient date. The
spec now asserts the coupling in both directions, so lowering the rule to match a
short fixture goes red too.

**Pattern to watch:** a fixture and a rule that have to agree, with nothing
asserting they do.

---

## 2026-08-21 — Phase 7c, the calendar's editing surfaces

### `ItemDetail` threw on every close with focus in the label field

**FIXED** · `d6c96c0` · was **HIGH** in effect: a TypeError in production on a
routine dismissal

`item` is a prop, which in Svelte 5 is a GETTER over the parent's state -- here
`CalendarView.detail`. Closing writes `null` into that state and the `{#if}` then
tears the subtree down. Between those two things the getter returns null while the
component's handlers still exist, so the label field's `onblur`, firing DURING
teardown, read `item.id` off nothing:

```
TypeError: Cannot read properties of null (reading 'id')
```

**The type said `ScheduleItem` and was telling the truth about the value and not
about the getter.** That is the transferable part: a prop's declared type does not
survive the parent revoking it, and any handler that can fire during teardown is
reading a prop that may already be gone.

Fixed by latching the row at mount -- `const row = untrack(() => item)` -- which
fixes the whole class rather than that one handler. It is also honest about what
the component already was: `detail` is a snapshot, the dialog is modal, and the two
things that CAN change while it is open are read from their stores.

**Found by `check:interaction`**, which fails on a console error. No unit test could
have seen it: the suite runs in Node with no jsdom, so it has no focus model, and
the throw needs a real blur during a real unmount. It only surfaced at all because
something in that gate finally opened the dialog -- the same shape as 6b's
`derived_inert`, where a warning sat in the production build until a gate performed
the gesture.

### Focus did not return to the control that opened the dialog

**FIXED** · `d6c96c0` · **MEDIUM**

`focusTrap` restores focus to whatever held it at mount. A POINTER press does not
reliably leave focus on a button -- Chrome does it, Safari on macOS does not -- so a
mouse user closing the dialog landed on `<body>` and the next Tab started at the top
of the page. `ItemRow` now focuses its trigger before calling `onOpen`, which costs
keyboard users nothing and makes the return deterministic.

### `annotate`'s shortcut would have kept urgent on a done row

**FIXED before shipping** · `d6c96c0` · latent, unreachable through today's mappers

Moving the done-suppression into the shared `urgentFor` rule made the existing
`if (!label && !isUrgent) return item` early return wrong: a row arriving urgent AND
done, with no override, has two falsy resolved values, takes the shortcut, and keeps
the flag the suppression exists to remove. Only custom events arrive carrying
`urgent` and none of them is tickable, so it could not fire -- but "unreachable" was
a property of the mappers, not of the function. The condition now asks whether
anything actually differs. Pinned by a test that goes red on the old shortcut.

### Two defects NOT reproduced from the Next source

Both were read, understood, and built differently. Recorded so a future reader
comparing the two trees does not "restore" them.

- **Un-marking urgent in the dialog did nothing.** `AddItemForm.tsx` wrote label
  and urgent onto the custom event AND into the annotation stores, and
  `mergedSchedule` resolves `override ?? item.urgent` -- so clearing the override
  fell straight back to the copy on the event. One source now: the annotation
  stores, for all three kinds alike.
- **The dialog read a stale snapshot.** `ItemDetail.tsx` rendered `item.urgent`
  from the row it was handed, which never changes, so the checkbox did not move
  until the dialog was reopened. Read live through `labelFor` / `urgentFor` here.

### Resolved: the day's figure counts events that have no row

**CLOSED** · `af7fb53` · was LOW, and lasted exactly the one phase it was given

`DayEventsSection` is mounted, so every category the header counts has rows
beneath it. Verified in a browser rather than argued: `check:interaction` walks
every day in the month that has anything on it -- 36 days, 14 of them with events
-- and asserts the figure equals the rows rendered, including after an add. The
gap cannot reopen quietly.

---

## 2026-08-21 — Phase 6b, task editing

### Every date converter threw a RangeError on a "Needs a date" row

**FIXED** · `ad42a35` · was **HIGH**, and latent in the Next source

`dateForGroup`, `fromDateInputValue` and the due shortcuts all carry the task's
existing clock time over when only its DAY changes -- correct, and the reason a
problem set due at 11:59pm stays due at 11:59pm when it moves to today.

They did it by reading `new Date(fromISO).getHours()`. For a date that will not
parse that is `NaN`, `setHours(NaN, NaN)` yields an Invalid Date, and
**`Invalid Date.toISOString()` throws a RangeError.** `toDateInputValue` was
quieter and no better: it returned the literal string `"NaN-NaN-NaN"`, which a
native `<input type="date">` silently rejects, leaving a field that looks broken.

The group guaranteed to hit this is `unknown` -- "Needs a date" -- which exists
*precisely* because a due date did not parse, and whose entire purpose is that a
student can fix it. So every route out of it (the date input, all three
shortcuts, a drag into a dated group) would have raised an exception in front of
the person using the one control the group was surfaced for.

**Reproduced against the Next source before fixing it**, rather than assumed:

```
toDateInputValue("not-a-date") => "NaN-NaN-NaN"
dateForGroup THREW: RangeError: Invalid time value
```

**Fix:** one `clockFrom` helper, falling back to the reference instant's clock and
then to local midnight. A date that never parsed has no time of day to preserve,
so nothing is lost. `toDateInputValue` returns `""`, which is what "no value
selected" means to a date input.

**Why it was latent in Next and live here.** The Next app filtered by
`due.urgency === group.key` over three groups, none of which is `"unknown"`, so
those rows rendered *nowhere* -- a separate defect, fixed in 6a by giving them
their own group at the top of the list. Making them visible is what made the
crash reachable. **Fixing one bug can promote another from unreachable to
certain**, and the fixtures contain no unparseable date, so nothing would have
caught it in use.

**Now gated:** 5 tests in `taskBoard.spec.ts` covering the input, both
shortcuts, and all three dated drag destinations.

### `dragend` on a dropped row read a destroyed block's derived

**FIXED** · `5bfd3eb` · was **LOW** in effect, **MEDIUM** as a warning

Dropping a task into another group tears down its `{#each}` block. The browser
then fires `dragend` on the old element, and that handler read the `reorder`
prop -- a derived owned by the block that had just been destroyed. Svelte named
it exactly: `derived_inert`, *"reading a derived belonging to a now-destroyed
effect may result in stale values"*.

No stale value did any harm today, because the handler only cleared state that
`onDrop` had already cleared. But the warning was real and it was **present in
the production build**, and a stale read inside a drag handler is the kind of bug
that takes a day to find.

**Fix:** the row no longer owns that cleanup. `TasksCard` clears its own drag
state from a `document` `dragend` listener that exists exactly as long as
`drag !== null` -- the same "lifetime is the state's" shape as `clickOutside` and
`escapeKey`, one level up. A cancelled drag leaves the source row in place so its
`dragend` bubbles; a completed drop has already cleared synchronously.

**How it was found, and the part that matters:** by dragging a row in a real
browser. All six gates were green. `svelte-check` reports 0/0, 439 tests pass, and
`check:interaction` *does* fail on console warnings -- but only for gestures it
actually performs, and nothing performed a drag.

**Now gated:** the gate drags a row between groups. Verified to fail by putting a
`dragend` back on the row: 1 red.

**The pattern:** *a gate that fails on console noise only covers the gestures it
makes.* Its "nothing threw or warned" assertion reads like a blanket guarantee and
is really a per-interaction one. Same family as the note in FINDINGS about a check
that appears to cover what it cannot.

### The undo arrival, answered

**NOT A BUG** · `5bfd3eb` · the open question from `aadfca9`, closed

`arriveAtRow` awaits one `tick()`, and 6a predicted the undo would be the first
caller needing two. Measured in a real browser, both ways.

**One tick is enough -- but only because of the ordering, not the count.**
`undoTick` unticks, reads the recomputed derived list, decides whether to expand
the card, expands it, and only then arrives. Every write precedes the flush.

With the expansion moved into an effect instead, the hidden-row case lands
nowhere, marks nothing, and logs **no warning in production**. Now the
hidden-row arrival is a gate assertion, which is the loud failure that was asked
for.

---

## 2026-08-21 — found and fixed while building the stat pill popovers

### Pressing a stat pill did nothing at all

**FIXED** · `035c4ff` (and `4439c58` for the gate's other half) · was **HIGH**

The popover opened on hover as well as click, and held ONE boolean for its open
state. A mouse click is preceded by a pointer entering, so:

```
pointer enters  -> open = true
click           -> saw open, closed it
net effect      -> nothing
```

The feature's headline interaction was dead. A second fault sat behind the same
boolean: clicking to open and then moving the mouse closed the panel, because a
pointer leaving cannot tell a hover it started from a click it did not.

**How it was found:** by driving the built page in Playwright, on the first
attempt to click a pill. **Every other gate was green** — 389 tests,
`svelte-check` 0 errors and 0 warnings, a clean build, contrast 58/58, layout
36/36. None of them can press a button.

**Fix, in two steps.** First `openedBy: 'pointer' | 'command' | null`, so hover
opened only what was shut and hover closed only what hover opened. Then, the same
day and after the owner tried it, **hover was removed entirely** — three pills sit
in one row, so a cursor crossing that row opened and closed panels nobody asked
for. `openedBy` collapsed back to a boolean with hover gone.

**Now gated:** `scripts/check-interaction.mjs`, and specifically the assertion
that **hovering a pill does NOT open its popover** — reintroducing hover is the
only route back to this. Verified to fail on it: putting `onpointerenter` back
turns 6 checks red, including "clicking a pill opens its popover".

**The pattern:** a control with two ways in has more states than it has booleans.
If two input methods can produce the same visible state, the state has to record
which one produced it — or the second will undo the first. And the corollary the
owner reached: a correct implementation of a bad interaction is still bad.

### Jumping to a row changed nothing on screen

**FIXED** · `4439c58` · was **MEDIUM**, and reported by the owner

Choosing an item in a stat popover moved focus to the row and scrolled it into
view. Both correct. Everything on Home is already on one page, so for a row that
needed no scrolling **nothing moved and nothing changed**, and a student who
clicked "Submit peer review" concluded the click had failed.

The focus ring is not the answer: `:focus-visible` is exactly what does not
render for the pointer user who just clicked.

**Fix:** `.thrive-arrived` — an indigo inset ring on the arrived row, solid for
most of a 1200ms beat then faded. An outline because it cannot move the layout,
does not contest the background wash a task row already uses for priority, and
follows each row's own radius so one rule fits both row shapes.

**A trap inside the fix.** `app.css` ends with a blanket
`animation-duration: 0.01ms !important` for `prefers-reduced-motion`, so a mark
*painted* by a keyframe appears and vanishes within a hundredth of a millisecond —
invisible, with no error. So the ring is a normal declaration and the animation
only takes it away; reduced motion gets `animation: none` and a timer still clears
it.

**Now gated:** five assertions in `check-interaction` — marked, uniquely marked,
cleared after its beat, marked even when no scrolling was needed, and marked under
reduced motion with `animation-name: none`. Verified to fail: not applying the
mark turns 4 red, never clearing it turns 2 red.

**The pattern:** a correct action that shows nothing reads as a failure. "It
works" and "it appears to work" are different acceptance criteria and only one of
them is the product.

### `arriveAtRow` could do nothing, silently

**FIXED** · `aadfca9` · was **LOW** today, **HIGH** the moment 6b lands

`arriveAtRow` awaits one `tick()` and returns if the row is not in the DOM. Fine
for every caller today, because expanding a card is a single state write. But an
arrival that lands too early is **indistinguishable from a successful arrival at a
row that was already visible** — which is the exact bug above, arriving by another
route.

**Fix:** a `console.warn` naming the id it could not find, behind
`import.meta.env.DEV`. A warning and not a throw, because a student must never see
an exception over a wayfinding cue.

**Not gated, and that is stated at the assertion.** `check:interaction` drives the
production build, where the branch is compiled out. It now fails on console
warnings anyway — worth having — but it cannot see this one. Verified by hand
against `vite dev` instead: a normal arrival warns about nothing; a row with its
id removed warns exactly once and names it.

**Open for 6b:** unticking a task moves it between groups, and if that regrouping
takes two flushes the single `tick()` is not enough. Decided: check it explicitly
there, and if one tick is too few, make it fail loudly.

**The pattern:** a silent no-op is the worst failure mode in this app. It is what
made the reveal read as a dead click, what an id-parsing row lookup did before
`tickItem` dispatched on the attached source row, and what a hover-swallowed press
looked like.

---

## 2026-08-21 — found and fixed during the repalette and Phase 6a

### 37px of scrollable empty space at the bottom of Home

**FIXED** · `074486d` · was **MEDIUM**, and invisible

Home could not fit any viewport shorter than 1275px however tightly the header
was packed. 37px of that was not content:

```
every element renders at or above  1238px
body.scrollHeight                  1238px
window.scrollTo(0, 1e6)            moved 37px    <- the page really does scroll
documentElement.scrollHeight       1275px        <- and this agreed with nothing
```

A card with a fixed height and overflowing content — Upcoming Events, which
scrolls at rest by design — was leaking its scrollable overflow out to the
document.

**Fix:** `contain: paint` on `.thrive-card-body`. Measured rather than guessed:
`overflow: hidden`, `overflow: clip` and `overflow-x: hidden` all left the 37px
in place.

**How it was found:** by accident. A predicted 24px saving from shortening the
top bar measured 8px, and chasing the missing 16px turned this up. Nothing was
watching for it.

**Now gated:** `scripts/check-layout.mjs` asserts across 12 routes × 3 viewports
that the page cannot scroll further than it paints, and it was verified to fail
on this exact bug before being trusted. `check-contrast.py` carries a
browser-free backstop asserting the containment is still declared.

**The pattern:** a document that scrolls past its own content is always a bug.
It is dead space, it makes "does this fit on one screen" unanswerable, and it is
invisible in a screenshot.

### A task with an unparseable due date vanished from Home

**FIXED** · `f8593b7` · was **MEDIUM**

`useTaskBoard` grouped by `due.urgency === group.key` over `overdue | today |
upcoming`. The fourth urgency state added by the Phase 3a-fix guards,
`"unknown"`, matches none of them — so a task whose due date would not parse was
filtered out of every group and rendered nowhere. No error, no log, no gap on
screen.

Inherited from the Next tree, where the fixtures contain no unparseable date,
which is why nobody noticed.

**Fix, in two steps.** Phase 6a returned those rows explicitly in an
`unclassified` array so the information was at least reachable, and recorded that
where they belong was an open question. This commit answers it: `unknown` is a
real group, FIRST in the order, headed "Needs a date".

**The pattern:** a filter over a closed union silently drops anything the union
grew. `describeDue` gained a fourth state in Phase 3a-fix and this consumer was
never revisited. When a union grows, grep its consumers — the compiler will not
tell you, because `filter` on a non-matching value is legal.

### `flex-1` silently defeated the card height cap

**FIXED** · `ebeb895` · was **LOW**, caught before shipping

`.thrive-card-body` set `height: var(--thrive-card-body-cap)` at desktop, and the
element also carried `flex-1` inside a flex column. `flex: 1 1 0%` wins, so the
body grew to its content and the cap did nothing: 423px measured against a 248px
cap.

Valid CSS, no warning, and the cap was visibly "there" in the file.

**Fix:** drop `flex-1`. Found by measuring the built page, not by reading.

### `svelte-check` passed on a component that threw on every request

**FIXED** · `ebeb895` · was **LOW**, caught before shipping

`SectionCard` gained a `meta` snippet prop. It was added to the `$props()` type
annotation but not to the destructuring pattern, so the template referenced an
undeclared identifier. `npm run check` reported 0 errors over 367 files; the
route returned 500 with `ReferenceError: meta is not defined`.

**The pattern:** an unknown identifier in a Svelte template is not a type error.
A typecheck proves the types agree, not that the page renders. Serve the route.

---

## Still open, inherited deliberately

*(unchanged from the previous entry — the three process-global mock stores,
BLOCKING; and the shallow provider copies)*

---

## 2026-08-22 — fixed during the Phase 5 port

Four defects from `MIGRATION.md` §9 that were **built correctly rather than
ported**. None of these was a bug in this repo; each is a bug in the Next
prototype that a faithful port would have inherited.

### `cancelAppointment` released a slot by matching start time

**FIXED** · `955fc93` · was **LOW**, would have become **HIGH**

`providers.ts:252-260` in the Next tree iterated `claimedSlotIds` and released
the first slot whose `start` equalled the appointment's, because the appointment
carried no reference back to the slot it claimed.

Correct with one advisor per service and distinct times — which is exactly what
the fixtures give it, so nothing ever revealed it. **Wrong the moment an advisor
publishes two simultaneous slots**, where it frees whichever the set iteration
reached first. The student cancels one appointment and someone else's slot opens
up.

**Fix:** `Appointment.slotId`, set at booking, deleted at cancellation. One
exact delete, and it drops the rebuild of the advisor's entire slot list that the
scan needed.

**The pattern:** this is the same shape as "never resolve a row by parsing its
id" — reconstructing a relationship from a value that merely *correlates* with
it. `start` is not an identity. Store the reference.

### The provider boundary was violated in exactly one place

**FIXED** · `d26f4e6` · was **LOW**, a build break later

`app/degree/requests/page.tsx:8` did
`import { requestTypeLabel } from "@/lib/data/mock/requests"` — the only import
in the whole tree reaching past `@/lib/data` into a mock module. Confirmed by
grep, not taken on faith: the three other `lib/data/mock` matches are comments.

It would have broken the build the day the mock modules were deleted for Django,
which is the one day nobody wants a surprise.

**Fix:** both label maps moved to `data/labels.ts`, on the public side. They were
never mock data — they are labels for a closed union in `types.ts`, correct no
matter what is behind the providers.

### Four providers returned fixtures by reference

**FIXED** · `955fc93` · was **LOW**

`getStudent`, `getDegreeProgress`, `getAdvisors` and `getResources` returned
module-level fixtures directly, while the file's own comment two functions above
said a caller "should never see it change underneath them". The store-backed
providers all copied.

No live bug — nothing mutated them. But "no live bug" is a property of today's
callers, not a contract, and the next caller does not read the comment.

**Fix:** all 25 return copies. Still shallow, as they were — the nested-array
hole is pinned by a test rather than silently closed.

### `DegreeProgress.expectedCompletion` was a second, stale answer

**FIXED** · `327f7af` · was **LOW**

Declared on the type, hardcoded `"Spring 2027"` in the fixture, while
`buildProgramTimeline` derived **Fall 2027** for the same student. Two answers to
one question, and the only reason nothing contradicted on screen was that the
field rendered nowhere.

**Fix:** dropped from the type and the fixture. The finish term is derived —
`ProgramTimeline.expectedFinishTerm`.

**The pattern:** a stored field that duplicates a derived one is a bug with a
delay on it. It cannot be kept in step, and it stays quiet until someone renders
it.

---

## Still open, inherited deliberately

### The three mock stores are process-global — **BLOCKING**

`MIGRATION.md` §9 defect 1, unchanged by this port and unfixable at this layer.
Module-scope objects shared by every visitor to the `adapter-node` process:
concurrent students book over each other and see each other's requests and
resume versions, and everything resets on restart or hot reload.

Django is the fix. Each store says so at its definition. **Do not put this in
front of more than one person before then.**

### Provider copies are shallow

`{ ...version }` shares `version.skills`, `version.courses` and
`version.experience` with the store, so `returned.skills.push(...)` mutates it.
Faithful to the Next source. Pinned by a test in `providers.spec.ts` that fails
if someone deep-copies on purpose, and says why.

---

## 2026-08-21 — fixed

### `describeDue` rendered an invalid date as a real, invisible deadline

**FIXED** · `adf11d0` · was **HIGH**

An unparseable date produced:

```
{ urgency: "upcoming", label: "Invalid Date",
  countdown: "in NaN months", days: NaN, fullLabel: "Due Invalid Date" }
```

The strings were the visible half. The damage was `urgency: "upcoming"` — every
`NaN` comparison is false, so a broken date fell past `days < 0`, `days === 0`
and `days === 1` into the final branch. It would **never appear in the overdue
group**, so a student would never see that deadline at all. Invisible is worse
than wrong.

Every sibling mapper already guarded with `Number.isNaN(date.getTime())` —
`taskToItem`, `todoToItem`, `customEventToItem`. This one function was the
exception.

**Fix:** `DueDescriptor` became a discriminated union with a fourth state,
`urgency: "unknown"`, where `days` is `null` rather than `NaN`.

**Pattern to watch:** a sentinel that shares its type with the valid case is not
a guard. `NaN` is a `number` as far as TypeScript is concerned, so it flows
silently into `a.days - b.days` and `days <= WEEK`. `null` does not typecheck
there, which is the whole point.

**Pattern to watch:** when one function in a family lacks a guard its siblings
all have, that is not a style difference.

### `formatClockTime` emitted `"NaN:undefined PM"`

**FIXED** · `adf11d0` · was **LOW**, latent

`formatClockTime("abc")` returned `"NaN:undefined PM"`, every part of which
reached the DOM. `formatClockTime("9:5")` returned `"9:5 AM"` — the minute half
was never parsed, just interpolated. `formatMeetingPattern` composes this, so a
malformed `CourseMeeting.startTime` produced `"Mon NaN:undefined PM"`.

Latent rather than live: no caller passes anything but a well-formed value. It
was still reachable.

**Fix:** validate the `HH:mm` shape and the ranges, return `"--:--"`. Lenient on
a one-digit hour (`"9:30"` already worked); strict on the minute, because
`"9:5"` is not a time.

---

## 2026-08-21 — Phase 7a: fixed

### The ignore store's two surfaces do not share a key space — **FIXED (was HIGH)**

Recorded below on the same day and fixed in Phase 7a. The canonical key is the
**raw `Event.id`** (`evt-3-1`), which is the space `filterSchedule` had always
expected — so Home was the broken side, exactly as the entry below predicted.

**The fix was not in the calendar.** `setEventIgnored` / `isEventIgnored` were
normalising their own arguments through `eventIdOf`, so a raw id handed in got
mangled to `3-1`. They now key on precisely the string given, and the one surface
holding a prefixed id — the calendar — calls `eventIdOf` once at its own
boundary. No Home component changed: every call site there already passed
`event.id` raw.

**The honest fix was the one the entry below called honest:** stop deriving the
key from a prefix at all. The doc comment claiming "passing a raw id through
twice is safe" was the false sentence that let the bug be written twice, and it
is gone.

**Verified to fail.** Reverting the two lines turns 7 assertions red across
`calendarStores.spec.ts` and `ignoredEvents.spec.ts`. Also driven in one real
browser: ignoring an event on Home writes `{"evt-0-0":true}`, and `/calendar`
reads the same key.

**A lesson that outlived the bug.** One direction of the new cross-surface pair —
"the calendar ignoring an event hides it on Home" — still PASSES with the
normaliser reinstated, because both sides then share the same mangling. A
cross-surface test is not automatically non-vacuous; the other four assertions are
what actually catch it. Recorded in FINDINGS.

**Accepted, not migrated:** keys written under the old shape stay in
`localStorage` and are inert, so an event ignored on Home before this change
reappears once. Absence means "never touched" in this store, so a stale key is
harmless rather than corrupt. Mock data, dev-only, and a migration shim whose only
input is a browser nobody can inspect is worse than the one-time reappearance.

---

## 2026-08-21 — Phase 7b: fixed while building

### `line-clamp-3` was doing nothing next to `block` — **found and fixed**

`ItemRow`'s compact variant is the week column's shape: time above title, clamped
to three lines. The clamp did not clamp. Measured at a 71px column: "MGT 142 ·
Machine Learning for Business" rendered **140px tall — seven lines**.

`line-clamp-3` works by setting `display: -webkit-box`, so a `display` utility
beside it wins the cascade and the clamp silently stops applying. The class string
was `'... line-clamp-3 block ...'`, carried over from the Next source where the
same pair sits together and has the same effect.

**Nothing warns about an unclamped clamp.** It is not an error, the text is all
there, and it only looks wrong if you happen to be measuring row heights in a
narrow column. Found by measuring the week columns at the tightest width the
40rem fallback still renders them at, which was not what that probe was for.

Fixed by dropping `block`. Verified: nothing exceeds 60px now, at 640px and at
1330px, which is exactly three lines of `text-xs`.

**Pattern to watch:** a utility that works by setting `display` is in silent
conflict with every `display` utility. `line-clamp-*`, `truncate` and `sr-only`
are the ones in this codebase.

### The Next source never had the week fallback — **built, per instruction, at 48rem**

MIGRATION §4 says week view is "not rendered below `40rem` — the parent falls back
to agenda", and `WeekView.tsx`'s own doc comment says the same. **Neither is true
of the code.** `CalendarView.tsx` renders `<WeekView>` whenever the view is week,
at every width, and `WeekView` handles narrow screens with `overflow-x-auto` and
`min-w-[42rem]` — a horizontal scroll, which is the exact thing its own comment
calls the wrong answer ("a view that technically renders and cannot be read is
worse than a view that admits it does not fit... rather than papered over with a
scroll").

So this is not a MIGRATION-versus-source disagreement to resolve in the source's
favour: the source has no behaviour here, only a contradiction between its comment
and its markup. The owner's 7b brief said to preserve the fallback, so it is built
for the first time — in CSS, and the port drops the min-width and the scroll, since
a scrollbar would mean the fallback was doing nothing.

**And it sits at 48rem, not the 40rem the comment named.** See the entry below:
40rem was built first, measured, and moved.

Boundary re-measured after the move: 769px and 768px render seven columns at 89px,
767px / 700px / 640px / 375px render the agenda plus a note. Zero horizontal
overflow at every width.

---

## 2026-08-21 — Phase 7b: accepted, with a reason

### Week columns were 71px at 40rem — **FIXED: the breakpoint moved to 48rem**

Built at 40rem first, because that is the width MIGRATION and the Next comment
both name. Measured at 640px, the narrowest width that still rendered the grid: the
seven columns came out **71px**, and although a three-line clamp held "MGT 142 ·
Machine Learning for Business" without overflowing, it read as three short stacks
rather than a phrase. At ~57px of text width a long word breaks mid-word.

**"Fits" and "is legible" are different bars, and a view whose whole job is to be
read owes the second one.** Owner's call, and the right one: anything that narrow
falls back to the agenda perfectly well, so the breakpoint belongs where the
columns are readable rather than where they merely fit.

Moved to 48rem (`md`). Re-measured: **89px columns at 768px**, up from 71px, with
about 75px of text width per title — enough that whole words land on a line instead
of hyphenating. Titles still cap at 60px, which is the three lines they should be.
Fallback now at 767px, and horizontal overflow is 0px at every width tested
(1330 / 900 / 769 / 768 / 767 / 700 / 640 / 375).

The lesson, since it is the second time this phase a measurement beat an
assumption: **the breakpoint is the knob, never a min-width.** A min-width puts the
horizontal scroll back, which is the thing the fallback exists to avoid.

### `check:layout` only ever sees the calendar's DEFAULT view — **queued for 7c**

The gate visits `/calendar` with an empty `localStorage`, so `normalisePrefs`
returns `view: 'month'` and the week and agenda views are **unvisited by every
gate**. That matters most for the agenda, which is 13,764px tall on a phone over a
30-day range — a long list is exactly where a vertical-overflow gate earns its
keep.

Covered by hand this phase instead, at eight widths across all three views: zero
horizontal overflow everywhere, and the page never scrolls past what it paints.

**Approved for 7c by the owner** — a 13,764px agenda on a phone is exactly what a
vertical-overflow gate is for. Deferred out of 7b rather than dropped: the calendar
was still being built, and adding a view dimension to a shared gate script is worth
doing once the surface it guards has stopped moving.

---

## 2026-08-21 — Phase 7a: accepted, with a reason

### The day's figure counts events that have no row yet — **LOW, one phase only**

`CalendarHeader` counts every item on the selected day and the month grid dots
every category on it, events included — but `DayEventsSection` is Phase 7c, so a
day can read "5" above three rendered rows. Confirmed live: 1 class + 2 tasks
render, 2 events do not.

**Why not fixed:** the two alternatives are worse. Filtering events out of the
count and the dots would break "one filter, applied once" and change what the
month grid shows twice — once now and once when 7c puts it back. Folding events
into a generic day group would ship them without their register controls, blurb
and relevance badge, which is the whole reason `DAY_GROUPS` excludes them.

Pinned by `calendarDay.spec.ts` → `"counts events too, because the figure beside
it does"`, which states the reason in the test rather than leaving it to be
rediscovered as a bug.

**Owner's call, after seeing the reasoning: it stands** unless looking at it on
screen changes their mind. So do not pre-emptively change what the header counts
or what the month grid dots — the fix, if one is wanted, is 7c arriving on time
rather than 7a hiding a number.

### `SquareGrid`'s white halo — **built correctly, not ported**

MIGRATION.md §9 defect 10. The Next version rings the "next up" cell with
`ring-2 ring-indigo ring-offset-1` and never sets `ring-offset-color`, so it takes
Tailwind's default white — right only because the strip has so far only ever sat
inside a white panel.

Built as `outline-2 outline-offset-1 outline-indigo` instead. An outline's offset
region is transparent, so there is no colour to set or to get wrong, and the two
indigo markers in the app (`.thrive-arrived` and this) are now drawn the same way.

---

## 2026-08-21 — found, recorded, NOT fixed

Each of these is pinned by a test named as a defect record, with a comment
saying it captures current behaviour rather than desired behaviour. The fix
arrives as a failing test, which is the right signal.

### The ignore store's two surfaces do not share a key space — **HIGH · FIXED in 7a, see above**

`calendarStores.spec.ts` → `"DEFECT: the two surfaces do NOT share a key space"`

`eventIdOf` strips exactly one leading `evt-`. But the raw `Event.id` in the
fixtures is **itself** `evt-3-1`, and the calendar prefixes it again to
`evt-evt-3-1`. So the function cannot tell them apart:

| Surface | Id it holds | After `eventIdOf` | Key space |
|---|---|---|---|
| Calendar | `evt-evt-3-1` | `evt-3-1` | **`evt-3-1`** |
| Home | `evt-3-1` | `3-1` | **`3-1`** |

Each surface is self-consistent. Cross-surface, **neither sees the other** —
ignoring an event on Home leaves it showing on the calendar and vice versa. That
is the exact opposite of the module's own headline ("ONE store, read by both
surfaces") and of MIGRATION.md §6.

Pre-existing in the prototype. **No existing test caught it** because each
exercises one side, and the two prototype cases encode *contradictory*
conventions — one asserts the map is keyed `"3-1"`, the other feeds
`filterSchedule` ids keyed `"evt-3-1"`. Both pass. Together they cannot both be
right.

**Why not fixed at the time:** picking the canonical key changes which
already-stored data stays valid. My read is that the raw `Event.id` should win,
making Home the broken side — but the honest fix is probably to stop *deriving*
the key from a prefix at all, since `evt-`-prefixed raw ids make the normaliser
ambiguous by construction.

**Both reads turned out right.** Fixed in Phase 7a exactly that way; the entry at
the top of this file records it.

**Pattern to watch:** a normaliser that cannot distinguish its input cases. Also:
three copies of one id rule (MIGRATION §9 defect 12 flagged the copies without
characterising the consequence).

### A parseable-but-wrong date still gets through `describeDue` — **LOW**

`format.spec.ts` → `"DOCUMENTS A GAP: a rolled-over date is parseable"`

V8 is inconsistent about invalid ISO dates. `"2026-13-01"` (bad month) is
`Invalid Date` and the new guard catches it. `"2026-02-30"` (bad day) **rolls
forward into March** and parses fine, so it arrives as a real date the student
never chose.

**Why not fixed:** catching it needs a round-trip check — reformat the parsed
date and compare it to the input, which is what `customEventToItem` already does
for day keys — and that is input validation rather than a parse guard. Out of
scope for the guard phase.

### `formatShortDate` can still emit `"Invalid Date"` — **LOW**

Untested deliberately: writing `expect(...).toBe("Invalid Date")` would entrench
it. The last unguarded function in `format.ts`. Currently unreachable with
garbage via `describeDue` (the date has already parsed by then) but directly
callable.

---

## 2026-08-21 — queued for Phase 7c, deliberately not fixed in 7a

### `thrive:event-joins` is keyed on the calendar item id — **LOW now, the same bug as above later**

MIGRATION §9 defect 13. `setEventJoined(item.id, …)` is called with the calendar's
id (`evt-evt-3-1`), whereas the ignore store keys on the raw `Event.id`
(`evt-3-1`). **This is the defect 7a just fixed, in a second store.**

It is LOW today only because the join store has exactly one consumer and that
consumer does not exist yet. It becomes real the moment Home grows a "count me in"
button, which would hold `event.id` and write to a different key — producing the
two-stores-one-name split all over again.

**Deferred to 7c by decision, not by omission.** 7c builds `DayEventsSection`,
which is the join store's only consumer, so the key-space choice gets made with
the consumer on screen rather than in the abstract. Fixing it in 7a would mean
choosing a canonical key for a store nothing reads.

The precedent is set, so 7c has the easy version of the question: the store keys
on exactly what it is handed, and the surface holding a prefixed id sheds it at
its own boundary. What 7c has to decide is whether the raw `Event.id` is right for
joins as well — it almost certainly is, since a join is a fact about an EVENT
rather than about a calendar row — and to add a cross-surface test that is not
vacuous in either direction. See CONVENTIONS and FINDINGS for why the second half
is the harder one.

---

## 2026-08-21 — inherited, on the do-not-reproduce list

From MIGRATION.md §9. Built correctly rather than ported.

### Page titles at weight 400 — **built correctly**

Twelve of thirteen `h1`s in the prototype render at 400, because weight came out
of the type scale on 08-15 and the headings were never updated. Every `h1` in
this port sets `font-bold` at the call site. `PagePlaceholder` alone accounted
for seven of the twelve.

### Leftover 2px strokes — **built correctly in the shell**

The rail, header and bottom bar all draw `border-*-2` in the prototype, with
comments calling it "the standard 2px edge" — both leftovers from the bordered
direction of 08-12 that the 08-15 restyle reversed without sweeping call sites.
Ported at **1px**, which is what a decorative hairline is under the current
direction.

**Not yet addressed:** the ~20 `border-2` call sites in `Button.tsx`, `TaskRow`,
`MiniCalendar`, `DueDateEditor`, `AddTaskForm`, `SectionCard`, `AssistantPanel`
and `QuickListWidget`. None of those is ported yet. `Button.tsx:20` puts
`border-2` on every variant, so building `Button` correctly fixes most of them
at once.

### Still open, inherited, not yet relevant

Recorded so they are not rediscovered. None is reachable in the port yet.

- **Home Tasks card collapses at 375px** — HIGH. Isolated to `TaskRow`,
  pre-existing rather than restyle damage (verified by stashing and re-measuring).
- **Avatar overlaps the nav** — MEDIUM. Not reproduced so far: the shell uses one
  `nav` landmark in the a11y tree at a time and the header is a separate
  stacking context. **Needs a browser check at both widths.**
- **Floating launchers cover page content at 375px** — MEDIUM. Both widgets are
  gated off behind `FEATURES`, so not currently reachable.
- **Empty states read as large grey slabs** — LOW, cosmetic.
- **`cancelAppointment` releases a slot by matching start time** — LOW. Wrong if
  an advisor ever publishes two simultaneous slots. Arrives with Phase 5.
- **Stale `DegreeProgress.expectedCompletion`** — LOW. Hardcoded `"Spring 2027"`
  while the timeline derives Fall 2027. Rendered nowhere. **Do not carry the
  field**; prefer the timeline's `expectedFinishTerm`.
- **`SquareGrid` ring offset assumes a white background** — LOW, visual.
- **Provider boundary violation** — `degree/requests/page.tsx` imports from
  `lib/data/mock/requests`. Becomes a build break when the mocks are deleted.
  `data/index.ts` in this repo documents where those label maps belong.
- **No auth on any server action** — HIGH. Not yet applicable: there are no form
  actions in the port. SvelteKit form actions have exactly the same property.
- **Module-level stores shared by every visitor** — was BLOCKING in the
  prototype. Resolved by construction here: there is no server-side store, and
  the Django backend is the real fix.
