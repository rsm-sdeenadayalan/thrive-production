# FINDINGS

Reusable patterns and lessons. Things worth knowing again.

---

## 2026-08-21 (later) — "the app renders too large" is usually not one knob

Asked twice in one day, and the answer was different both times.

The first time it WAS the root: `--text-sm` is `1rem`, so a 16px root put the desk
body at 16px rather than the 15 the design was drawn for, and a phone bump stacked
on top to make 17. One rule fixed type, spacing and every rem-based control height
at once.

The second time the root was already right -- 93.75% at >=64rem, computing to 15px at
both 1512 and 1920 -- and `--spacing` was already tighter than stock (0.25rem at a
15px root is a 3.75px step, against Tailwind's 4px). Neither knob was responsible.
What was generous was the STEP CHOSEN at each call site, and the worst offender was
the one list that appears on every page: nav rail items at 41.25px with 3.75px gaps.

**THE LESSON: measure the two global knobs first, then stop looking for a global
knob.** Reporting "the root is already correct and here is what it computes to" is
more useful than finding something to adjust.

**And `--spacing` is not the lever it looks like.** In Tailwind v4 `min-h-11`,
`size-3.5` and every control height derive from it, so a 10% reduction shrinks touch
targets and icons along with the gaps. Scoping call sites to `lg:` compresses the
air without touching either -- and it makes "mobile is unchanged" a measurable claim
rather than an intention. Phone document heights came out byte-identical.

## 2026-08-21 (later) — the design system usually already answers the question

Two asks in one session were solved by finding the existing answer rather than
writing one.

The Ask THRIVE conversation rail sat on the page's own cream and read as text
floating in a margin. The nav rail solves the identical problem with `bg-sunken`
behind a `border-line` edge -- and `.thrive-panel[data-tone="sunken"]` IS that pair
plus the panel radius. No new token, no new colour, and the contrast gate stayed
58/58 because every pair involved was already computed.

Same shape for the current-conversation marker: `TaskRow` already expresses "this
row is special" as a 2px left stripe. Reusing it also surfaced the detail that
matters -- the stripe has to be 2px on EVERY row and only change colour, or clicking
through the list shuffles it sideways.

**THE LESSON: when a request says "give it a distinct surface", the first move is to
find what already has one.** `grep` for the component that solved it, not for the
token that might.

---

## 2026-08-21 — a design can be reverted and still leave the right residue

`/appointments` shipped three day pickers in one session: a five-chip strip, then a
month grid, then a bookable-day list, then the chip strip again. That reads as
churn, and mostly was. What is worth keeping is the distinction between what a
revert should take back and what it should leave.

**Taken back:** the month grid as a picker, the separate one-calendar-month booking
window, `bookingWindowEnd` / `isBookableDay` / `openCountInWindow`, the day list
component, the 25-business-day fixture, and `MiniCalendar`'s `booking` and
`readOnly` modes. All of it deleted rather than left unreachable.

**Left behind, because it was never about the grid:**

- **`publishedByDay` beside `availabilityByDay`.** An open count alone cannot tell
  a fully-booked Tuesday from a Saturday — both are zero. The chips needed that
  distinction as much as the grid did.
- **A per-day open COUNT on each chip.** The original strip made a student select
  a day to discover it was empty.
- **`BookingDayView`**, which turned out to be the Next tree's `DayOption` with
  those counts added.

> **When you revert a design, ask which of its parts were answers to questions the
> design invented, and which were answers to questions that were already there.**
> The second kind should survive.

---

## 2026-08-21 — the same measurement can be an improvement and a regression

The booking flow was measured three ways at 1512px:

| arrangement | total path | day→time | direction changes |
|---|---|---|---|
| day picker on the right | 1320px | 538px leftward | 3 |
| three side-by-side columns | **1362px** | 305px | 0 |
| two columns, step 4 stacked | 1128px | 313px | 0 |

The three-column version fixed exactly what it set out to fix and made the journey
LONGER, because three columns sweep the whole page width. Had the brief only asked
for "no backtracking" it would have shipped, and the report would have claimed an
improvement truthfully while the thing got worse.

The same shape appeared in the page container: 72rem left 120px of dead margin, so
it went to 96rem, and at 1512 the cap stopped biting entirely and content ran to
the edge. Two knobs were needed — a gutter for the near case, a cap for the far
one — because a gutter alone does not solve 2560px and a cap alone does not solve
1512px.

> **Measure the thing you were asked about AND the thing you might be trading it
> for**, and put both in the gate. `check:interaction` now asserts the ordering and
> the total, and the gutter and the cap.

---

## 2026-08-21 — an affordance beats a caption, every time

"Your month" shipped as a read-only reference: cells as `<div>`s, no focus, no
hover, the grid `aria-hidden`, and a caption reading *"A reference while you book.
Nothing here is clickable."*

Every one of those was a correct implementation of "not interactive", and the thing
still read as broken, because a month grid with dots on it looks like a date
picker. The caption was arguing with the shape and losing.

The fix was to make it interactive. But the reasoning from the read-only version is
worth keeping, because it holds in the other direction: **if a cell is not a
control, do not use an element that looks like one** — and the fix there is to
change the ELEMENT (`<svelte:element this={readOnly ? 'div' : 'button'}>`), not to
drop the handler, since a focusable cell that does nothing is worse than no cell.

> **A caption cannot make an affordance mean something else.** If you find yourself
> writing one that explains why a control does not work, the control is the problem.

---

## 2026-08-21 — two selections on one page, and the coupling has a direction

`/appointments` has a booking day (the chips) and a browse day (the month grid).
The obvious implementations are both wrong:

- **One shared day** — clicking the grid to look at next Thursday silently changes
  which day you are booking.
- **Two fully independent days** — "Your day" stops showing what the slot you are
  about to take would collide with, which is the entire reason that pane exists.

What works is a one-way coupling: a chip moves both, the grid moves only the browse
day. Asymmetry in a UI usually smells, so this one is stated at both ends in the
code and the gate asserts the negative half — after a grid click, the pressed chip
and the rendered times are byte-identical.

> **When two controls write related state, write down which direction the coupling
> runs and assert the direction it does NOT.** A positive assertion cannot tell a
> one-way coupling from a two-way one.

---

## 2026-08-21 — reusing a component means finding the assumptions, not the shape

`MiniCalendar` was built in Phase 7a with `size` and `showTodayButton` props it
had no caller for, and a doc comment saying they existed because the same grid was
meant to serve as a booking picker later. Phase 8 was that later, and the props
were the least of it.

What transferred: the panel shape, month paging, the 6×7 grid, the grid roles, the
roving tabindex with its documented fallback, and the whole keyboard walk.

What did NOT, and none of it was a prop:

1. **Dots come from `ScheduleData` categories.** Booking needs an advisor's open
   count, which is a different question about the same day.
2. **Every rendered day is selectable.** Booking has two independent reasons to
   refuse a day, and they look identical.
3. **Paging is unbounded.** Booking is capped a month out.

All three turned out to be *additive* — one optional prop and a branch in four
places — which is what made reuse correct rather than merely cheaper. (That prop
is gone with the grid it served; the component is back to one shape and has two
interactive call sites, which is the outcome the props were kept for in the first
place.) **The test
for "reuse or fork" is not how similar the two surfaces look. It is whether the
differences are additions or contradictions.** Had any of the three required
changing what `/calendar` does, a sibling component would have been right.

The thing worth not forking, specifically, was the ~80 lines of keyboard grid
navigation carrying two fixes the Next version did not have. A near-copy would have
carried the fixes on the day it was written and diverged on the next.

---

## 2026-08-21 — a cursor and a selection are two values, and one of them is a lie

> **The code this describes has been deleted** along with the booking-mode month
> grid, so `MiniCalendar` uses one value again — correctly, because every day in it
> is selectable once more. Kept because the lesson is about the CONDITION, and the
> condition will recur the next time a grid has unselectable cells.

`MiniCalendar` used `selectedKey` for both "which day is chosen" and "where the
keyboard is". That is correct exactly while every day is selectable.

The moment some days are not, the conflation forces a choice between two bad
behaviours: arrow keys that skip closed days (so the grid's spatial model breaks —
ArrowDown stops meaning "a week later"), or arrow keys that select whatever they
land on (so exploring the month books days by accident).

The fix is a third state, and its default is what makes it cheap:

```ts
let cursorKey = $state<string | null>(null);
const activeKey = $derived(cursorKey ?? selectedKey);
```

`null` MEANS "the selection". So the cursor only exists on the exceptional path,
the parent can still move the selection from outside and have the tab stop follow
with no effect to synchronise them, and `/calendar` — where everything is
selectable — never writes it at all.

**The companion rule:** a disabled cell in a composite widget takes
`aria-disabled`, not `disabled`. A `disabled` button cannot receive focus, so a
keyboard could not cross a shut weekend to reach the Monday behind it. Playwright
enforces the same reading — it refuses to click `aria-disabled` without `force`,
which is how the gate ended up proving the handler refuses the click rather than
the browser doing it.

---

## 2026-08-21 — a React idiom can dissolve instead of porting

MIGRATION §8.5 asked whether `BookingPanel`'s adjust-during-render becomes a
`$derived` or an `$effect`, and noted the current code deliberately does both:
derive `dayKey` from a changed prop, and clear `slotId` as a side effect.

The answer was neither, and the reason is that **the idiom existed to reconcile
two owners of one value.** Once the month calendar became the only day picker,
the day stopped being panel state — it is a prop — and there was nothing to
reconcile.

The side effect went the same way. `selectedSlot` is derived by looking the chosen
id up in *this day's* slots, so a day change makes the lookup fail and the stale
choice drops out on its own. The `seenExternal` shadow, the comparison and both
setState calls have no replacement because they have no job.

**Before translating a framework-specific mechanism, ask what problem it solves in
the source and whether the port still has that problem.** Three of MIGRATION §8's
twelve items have now dissolved rather than translated.

---

## 2026-08-21 — "no localStorage" is a design constraint, not a limitation to work around

Ask THRIVE's history could not be a persisted store: conversations are large, they
grow without bound, and a student on a second laptop would find an empty history
indistinguishable from never having asked anything.

The tempting move is to persist a little anyway — the last N messages, a draft, a
"recent" list. All of it would have to be torn out, and worse, all of it would be
*wrong in a way a student cannot see*: a history that is complete on one machine
and empty on another is not a smaller feature, it is a misleading one.

So the split is by honesty rather than by convenience:

- **Saved conversations** come from a provider. Real shape, mock body.
- **A message sent now** lives in component state, is gone on navigation, and the
  page says so BEFORE anything is typed.

The gate asserts the second half: sending writes no `localStorage` key. That is
the assertion that stops the constraint eroding, because eroding it would be one
convenient line.

**And the composer is live, not disabled.** A disabled control would have been a
fifth inert control in an app that has deliberately removed four — and "you cannot
type here yet" is less informative than a reply that explains what is missing.

---

## 2026-08-21 — a scroll container that cannot take focus is not navigable

Two rules disagree about the chat log and only one of them is about a student.

axe's `scrollable-region-focusable` says a region with overflow must be focusable,
or its content is unreachable by keyboard. Svelte's
`a11y_no_noninteractive_tabindex` says a non-interactive role must not take a
non-negative tabindex. Both are describing the same element.

The tabindex won, suppressed at that one site with the reason in the markup. But
the more useful finding is the one underneath it: **the tabindex was guarding
nothing until the panel got a definite height.**

`flex-1 min-h-0` with no height anywhere up the chain resolves to the content's
own height. So the log never overflowed, the document grew instead, and the
composer walked off the bottom as the conversation lengthened. The gate said so by
skipping — "this conversation fits without overflow" — and a permanently skipped
keyboard-scroll assertion is exactly the one you least want skipped.

**A `min-h-0` chain makes a child ABLE to shrink. Something still has to give it a
height to shrink within.**

---

## 2026-08-21 — raising chroma moves a colour toward its NEIGHBOURS, not just away from grey

The dots pass. The brief was "push chroma, hold luminance", which is the right
instruction and is only half the constraint.

Holding lightness keeps the contrast ratio, so a saturation bump looks free. It is
not: in a perceptual space, chroma is a radius and every hue has two neighbours at
the same radius. Pushing a colour out moves it AWAY from grey and TOWARD whatever
sits either side of it in hue.

Concretely: `needs-help` violet sat at H 288, between the reserved indigo at 273 and
civic plum at 323, and was already only dE 0.072 from indigo. Raising its chroma
along its own hue took that to **0.047 — worse than the worst pair on the grid
before the pass** — and indigo and the Rady dot both appear on the month grid at
once. The gate could not see it: every contrast ratio stayed green, because contrast
against the BACKGROUND was never the problem.

**Re-centring the hue in the corridor between its two neighbours bought the
saturation for nothing.** 288 → 296, 1.37× the chroma, and separation from both
neighbours marginally BETTER than before.

Two things to carry:

- **Check a saturation change against every RESERVED colour**, not only against the
  one you are trying to separate from. Contrast is a relationship with the surface;
  distinguishability is a relationship with the rest of the palette, and nothing
  measures the second automatically.
- **Compute the pairwise distances before and after.** It takes ten lines in oklab
  and it is the only way to know whether a palette change helped or moved the
  problem.

---

## 2026-08-21 — the cheapest legibility lever is often size, not colour

Same pass, reported honestly because the conclusion was not the one being looked
for: **6px → 8px did more for the dots than five retuned colour tokens did.**

1.8× the area is 1.8× as much of any colour to see, and it costs one token.

The colour work had a hard ceiling nobody could have guessed without measuring:
**teal and amber were already at the sRGB gamut boundary for their lightness.**
Available chroma was 1.07× and 1.15×, and the only route to more is to move
lightness, which is exactly what the contrast floor forbids. Two of the eight
streams simply cannot be made more vivid.

**Measure the headroom before spending the effort.** A ten-line script that reports
"maximum in-gamut chroma at this L and H" would have said in one run that three
tokens had room and two did not.

---

## 2026-08-21 — capture the artefact, not the event

The `.ics` gate could have asserted that clicking "Add to calendar" fired a
download. That proves the button is wired and nothing else — and "wired" was never
the interesting claim, because **the output is read by software rather than by a
person.** A calendar file with an unescaped comma, a bare LF, or a placeholder
DTSTART imports "successfully" and is wrong, and a download-fired assertion is green
for every one of those.

So the gate wraps `URL.createObjectURL` before the page loads, keeps the blob's
text, and asserts the CONTENT: one valid VCALENDAR, the event the row is showing, a
real DTSTART, and the UID.

**The UID assertion is the one that earns its place.** It must be the raw
`Event.id` — the same id the join store keys on. If Home exported the calendar's
doubly-prefixed form, importing the same event from the two surfaces would create
two entries in the student's real calendar instead of updating one. That is a
key-space bug whose consequence is outside the app entirely, where no test can
reach it.

Generalises past `.ics`: whenever a control produces a FILE, a request body, or a
clipboard payload, assert the payload. "Something happened" is the weakest possible
form of the check and it is usually the easiest one to write.

---

## 2026-08-21 — two small mappers beat one function with a discriminant

`icsFromItem` and `icsFromEvent` do the same job from two inputs, and the instinct
was to share them.

They should not be shared. An `Event` has a real `location` and a REQUIRED `start`.
A `ScheduleItem` has a `detail` that means a location on an event row and a course
code on a task, and an OPTIONAL `startISO` because a recurring class is a weekday
rule with no instant — so one mapper can fail and the other cannot. Sharing means
widening one type or narrowing the other to a lowest common shape, plus a
discriminant, plus a nullable return the `Event` path never needs.

Five lines each, and the duplication is the honest description of two genuinely
different shapes.

**What makes it safe is testing the shared RULE on both.** The single thing they
have in common — no distinct end means a marker at the start — is asserted in both
suites. That is what stops parallel mappers drifting, and it is cheaper than the
abstraction would have been.

---

## 2026-08-21 — a prop's declared type does not survive the parent revoking it

Phase 7c, and the most transferable thing in it.

In Svelte 5 a prop is a **getter** over the parent's state. `ItemDetail` declares
`item: ScheduleItem`, and that type is true of the VALUE. It is not true of the
getter: the parent closes the dialog by writing `null` into `detail`, and the
`{#if}` tears the subtree down a beat later. In between, the getter returns null
while the component's handlers still exist.

Which is not theoretical. Closing with focus in the label field fired the input's
`onblur` **during teardown**, `commitLabel` read `item.id`, and the page threw.

**The rule: any handler that can fire during teardown is reading a prop that may
already be gone.** Blur is the obvious one; so is anything on a `pointerup`, a
transition end, or an `IntersectionObserver`.

Two fixes, and the second is better:

1. Guard the handler — `if (!item) return`. Fixes one site, and the type says the
   guard is dead code, so review will eventually delete it.
2. **Latch the value at mount** — `const row = untrack(() => item)`. Fixes the
   whole class, and says out loud what the component already assumed.

The latch is only correct when the prop genuinely cannot change for the lifetime
of the instance, which is worth stating rather than assuming. Here it can be
argued: `detail` is a snapshot, the dialog is modal so nothing can swap the row
underneath it, and the two things that CAN change while it is open are read from
their stores instead. Where a prop really does change, guard the handler.

Same family as 6b's `derived_inert` — a handler on a row that a drop destroys
reading a dead derived. Both are "the DOM outlives the state for one tick".

---

## 2026-08-21 — a test that shares a transformation with the code cannot catch a key-space bug

7a fixed a store keyed through a normaliser applied on both sides. Two tests
passed the entire time it was broken, because a store that mangles on write and
mangles identically on read is perfectly self-consistent — about a key nothing else
in the app uses.

7c had the same decision to make in a second store, so the test shape was the
deliverable as much as the fix:

- **Assert the STORED KEY**, read straight out of the fake `localStorage` and
  compared to a hard-coded literal. Never through the store's own getter.
- **Or write through one surface's real path and read through the other's.** The
  calendar writes `setEventJoined(eventIdOf(item.id))`; Home reads
  `isEventJoined(event.id, joins)`. Neither side shares a step with the other.
- **Hard-code the id on the reading side.** Deriving it would reintroduce exactly
  the shared transformation being tested for.

And then **verify it fails**: reinstating the bug turned 7 cases red. A test
written against a known failure mode is worth little until it has been shown to
notice that failure.

---

## 2026-08-21 — extract the part that fails silently, not the part that is complicated

`AddItemForm` is a radio group and three inputs. Nothing about it is hard. The one
thing in it that can be wrong invisibly is WHICH STORE each kind lands in — a to-do
filed as a task turns up on Home under a heading claiming everything there was
"pulled from every source"; a task filed as an event cannot be ticked, so a
deadline quietly stops being one. Neither throws, neither fails a type check, and
neither is visible on the day it happens.

So `addCalendarItem` is a module and the form is markup around it. The heuristic
generalises past this repo's "nothing renders in a test" constraint: **extract by
failure mode, not by size.** The complicated part of a component is usually the
part you would notice breaking.

Third time in three phases: `calendarDay.ts` in 7a, `calendarViews.ts` in 7b,
`calendarAdd.ts` and `calendarEvents.ts` in 7c.

---

## 2026-08-21 — a confirmation step that keeps the button in the same place is not one

The delete control in `ItemDetail` replaces itself with a question. Two decisions,
both about the SECOND press:

1. **"Keep it" takes the position "Delete" occupied.** A student who double-taps,
   or whose finger is already moving, hits the safe control. A confirm button
   rendered where the trigger was reintroduces exactly the accident the step exists
   to prevent.
2. **Focus lands on "Keep it" too**, so Enter and Space agree with the pointer. The
   keyboard path must not be the dangerous one.

Also worth keeping: **Escape peels one layer.** With the confirmation up, Escape
cancels the confirmation and not the dialog — otherwise the key that means "back
out of this" skips past the question being asked and the student cannot tell
whether the delete happened.

---

## 2026-08-21 — a forward-looking claim decays into a false claim about the present

The most useful thing regenerating CONTEXT.md after two deferred phases turned up,
and it is not the stale counts.

A snapshot doc naturally contains sentences about what will happen next. Three of
them had come true **differently**, and each had silently become an assertion about
the present that was simply wrong:

| The claim | What happened |
|---|---|
| "`nowMinutes()` — the calendar's sanctioned client clock read" | The calendar declined it and reads the server's clock. The function still has no caller |
| "the calendar's 'next up' is `arriveAtRow`'s third caller and lands with the calendar" | It never became one. The line is static in the source, so there is nothing to jump to |
| "`ignoredEvents` — normalised through `eventIdOf()`" | Now exactly backwards. The store normalises nothing; that was the fix |

### Why this class is worse than a stale count

**A stale count is obviously a count.** "451 tests" next to a suite of 507 is wrong
in a way anybody spots, and nothing downstream depends on believing it.

These three read as *design*. Each was written as a considered decision, in the
register the rest of the file uses for considered decisions, and each would have been
followed. The second one in particular would have sent the next session hunting for a
call site that does not exist — or worse, adding one, which needs a third
`RevealKind` and an id-space decision nobody wanted to make.

### The rule

**When a doc predicts, mark the prediction, and re-check every one of them when the
phase it predicted lands.** Not just the numbers.

And the corollary for regeneration: **this is exactly what a patch cannot fix.** A
patch updates the paragraphs you thought of; it leaves the forward-looking sentences
elsewhere in the file sitting beside fresh text with nothing marking which is which.
The three above were in §7, §13 and §8 — three sections a calendar patch would have
had no reason to open.

### The sibling, from the same regeneration

**A verification claim decays the same way.** TESTING.md said the suite was green in
all seven timezones. It was not, and had not been for weeks, because that line was
written before the test that broke it. Same shape: a true statement about the past
presented as a standing property.

---

## 2026-08-21 — a computed style read at t=0 is a reading of the transition, not the value

Cost about twenty minutes and nearly produced a "fix" for a bug that did not
exist.

`KeyBar`'s stream chips hide their checkbox with `sr-only` and move the focus ring
out to the chip with `has-[:focus-visible]:outline-primary`. Driven in the built
page, `getComputedStyle(label).outlineColor` came back `rgb(58, 59, 66)` —
`--thrive-body`, the chip's own text colour, i.e. `currentColor`. The reading said
the colour utility had not applied.

It had. The CSS rule was in the bundle, correctly generated, and the class was on
the element — both checked. **Tailwind v4's `transition-colors` includes
`outline-color`**, so the probe was reading 0ms into a 120ms fade from
`currentColor` to navy. A `waitForTimeout(400)` returns `rgb(24, 43, 73)`, which
is `--thrive-primary` exactly.

### What to do instead

**Wait past the longest transition on the element before reading a computed
style**, or read the CSS rule rather than the computed value. Both probes in this
repo's by-hand passes now do the former.

### Two things this nearly cost

A replacement of `outline-primary` with an arbitrary-property form that would have
been permanent noise in the class string, justified by a comment stating a
measurement that was wrong. And the near-miss is the point: **the wrong reading
was self-consistent and specific** — a plausible colour, from a plausible source,
on the one element in the component with an unusual focus mechanism. Nothing about
it looked like an artefact.

### The sibling worth knowing

`transition-colors` animating `outline-color` also means every focusable element
carrying it has a focus ring that FADES IN over 120ms rather than appearing. Minor
— and `Button.svelte` already avoids it by enumerating
`transition-[background-color,color,border-color,opacity]` instead of reaching for
`transition-colors`. That enumeration is now known to be load-bearing rather than
fussy. Not swept repo-wide; recorded so the next person choosing between the two
knows what the shorthand includes.

---

## 2026-08-21 — a cross-surface test can be vacuous in one direction

Sibling of the lesson below, and the sharper version of it.

The ignore store's HIGH defect hid behind **two one-sided tests that both
passed**: one asserted the map was keyed `"3-1"`, the other fed `filterSchedule`
ids keyed `"evt-3-1"`. Each was true of its own surface. Together they could not
both be right, and nothing looked at both at once.

So the fix came with a deliberately cross-surface test: write through the path one
surface really uses, read through the path the other really uses. Home writes
`ignoreEvents.ignore(event.id)`; the calendar reads
`filterSchedule(data, { ignoredEventIds })`. And back the other way.

**One direction of that pair still passes with the bug reintroduced.** Reverting
the fix leaves `"the calendar ignoring an event hides it on Home"` green, because
`setEventIgnored(eventIdOf(itemId))` and `isEventIgnored(rawId)` then apply the
*same* mangling — write `"3-1"`, read `"3-1"`. Self-consistent, and wrong.

### The rule

**"Crosses two surfaces" is not the property that makes a test catch a key-space
split. Not sharing a transformation is.**

A test is only load-bearing here if one side's path applies a normalisation the
other's does not. Measure it the same way as the lesson below: revert the fix and
count which assertions actually go red. Seven did, across two files — the four
that mattered were the ones asserting the *stored key* rather than a round trip.

---

## 2026-08-21 — an assertion whose expected value came from the thing under test

The gate check for "copy-to-list only renders when `FEATURES.floatingTodo` is on"
needed to know the flag. It inferred it from the page: look for the floating To-do
launcher, and treat its presence as the flag being true.

The selector was `/to-?do list$/i` over every button and link. It matched the copy
button's own accessible name — **"Copy X to your to-do list"**. So the check asked
"is the gate open?" and answered it by finding the thing the gate controls.

It passed with the guard in place. It also passed with the guard removed. A
green check asserting nothing.

### Why it survived writing and review

It reads correctly. "The launcher is what the flag mounts, so its presence IS the
flag's value" is a true sentence, and the selector looks like it is about a
launcher. Nothing about the shape of the code says the two selectors overlap;
you have to know both strings.

It was caught by the one habit that catches this class of thing: **breaking the
feature on purpose and checking the count goes red.** The verified-to-fail step
is not ceremony for a check you are confident in — it is the only thing that
distinguishes a passing check from a check that cannot fail.

### The rule

**An assertion's expected value must not be derived from the thing under test.**

The fix was to parse `features.ts`, which is the same move `check-contrast.py`
makes with `app.css` and `arrive.ts` makes with `--thrive-arrival-duration`: read
the source of truth, never a restatement of it and never the output.

Worth noticing that the repo already had this pattern for *values* — durations,
tokens, counts — and this was the first time it was needed for a *condition*. The
shape generalises: if a check has to know what state the system is in, it asks
the state's own source, not the rendering of it.

### The tell to grep for

A check whose expected side is computed from the same DOM, response or file as its
actual side. Especially when both are found by a text or pattern match, because
two patterns written months apart can quietly describe the same string.

---

## 2026-08-21 — Phase 6b: four lessons worth keeping

### `await tick()` flushes what you already wrote, not what you meant to

The 6a worry about `arriveAtRow` was framed as "will the regrouping take two
flushes?" That turned out to be the wrong question, and asking it that way would
have produced the wrong fix (a second `tick()`).

Svelte's deriveds are **pull-based**: reading one after a state write recomputes
it *synchronously*, with no flush at all. So a handler can untick a task, read
the resulting list, decide the card must expand, expand it, and *then* await one
tick — and everything is in place. One flush, three writes.

The failure mode is not "too few ticks", it is **a write that has not happened
yet** because it was left to an effect. Reframed that way the rule is simple and
has nothing to do with counting:

> Make every state change the row's existence depends on before you call
> `arriveAtRow`.

**Measure the counterfactual, not just the fix.** Confirming the good version
works says nothing about *why* it works. Breaking it on purpose — moving the
expansion into an effect — is what showed that the ordering is load-bearing and
that the failure is silent. Without that step this would have been recorded as
"one tick was fine", which is true and useless to the next caller.

### Fixing one bug can promote another from unreachable to certain

Unparseable due dates rendered nowhere in the Next app. 6a gave them their own
group at the top of the list, which was the right call — a deadline that silently
does not exist is worse than one shouting for attention.

It also made a latent crash reachable. Every date converter read
`new Date(fromISO).getHours()`, which is `NaN` for those rows, and the resulting
Invalid Date **throws** on `toISOString()`. The controls for fixing such a row
are exactly the controls that would have thrown.

The lesson is not "guard your dates". It is: **when you make a previously
invisible state visible, audit every path that state can now reach.** The
fixtures contain no unparseable date, so no amount of using the app would have
found it.

### A gate that fails on console noise covers only the gestures it makes

`check:interaction` ends with "nothing threw or warned anywhere on the way", which
reads like a blanket guarantee over the page. It is not. It is a guarantee over
the interactions the script actually performs.

A `derived_inert` warning sat in the production build with all six gates green,
because nothing in any gate ever dragged a row. It was found by dragging one by
hand.

Same family as the earlier note below about a check appearing to cover what it
cannot — and the same remedy. When a feature adds a *gesture*, the gate has to
make that gesture, or its warning assertion silently narrows.

### `blur` fires before `click`, so Cancel saves

Adding commit-on-blur to an inline editor quietly breaks its Cancel button: focus
leaves the field on the way to Cancel, blur commits the draft, and then `cancelEdit`
restores a variable nothing reads any more.

Both halves of the guard are needed, and each covers what the other cannot:

- a `pointerdown` flag on the Cancel button — catches mouse and touch, and catches
  **Safari**, where clicking a button does not focus it and so leaves
  `relatedTarget` null;
- a `relatedTarget` check in the blur handler — catches the keyboard, where Tab
  moves focus to Cancel with no pointer event at all.

The general shape: **a control whose job is to discard has to out-race every
autosave path that fires on focus loss.** Worth checking the moment "save on blur"
appears next to anything called Cancel.

---

## 2026-08-21 — a gate that cannot see what it looks like it checks

### The shape of the problem

`check:interaction` was extended to fail on console warnings, right after
`arriveAtRow` gained a `console.warn` for the row it could not find. Reading the
two together, it looks like the warning is covered.

It is not. The gate drives a **production** build (`build-node/index.js` since the
Netlify work; `build/index.js` when this was written) and the warning is behind
`import.meta.env.DEV`, so the branch does not exist in the artifact being
measured. The check is real and useful for anything that warns in
production; it is simply blind to the one thing it appears to have been added for.

**Nobody would have noticed.** Both halves are correct in isolation, they landed
in the same commit, and every gate stayed green. The next person reading the
warning would reasonably assume a regression in it would be caught.

### What to do about it

Two things, and the second is the one that generalises.

**Say it at the assertion, not in a doc.** The comment naming the blind spot sits
on the `check(...)` line, because that is where somebody stands when they are
deciding whether to trust it. A doc three files away does not reach them.

**Verify the uncovered branch by hand, and record how.** A `vite dev` run,
stripping a row's `id` so `getElementById` misses while `planReveal` still reports
`found` — because that reads data, not the DOM. Both directions, so the
observation is not vacuous:

```
control   arrival succeeded=true  warnings=0
missing   marked=1 activeElement=BODY  warnings=1
```

### Generalisable

**A check that appears to cover something it cannot is worse than no check**, and
worse in a specific way: it converts an unknown into a false known. The absent
check leaves you cautious; the misleading one makes you confident.

So when a gate's reach stops short of what it seems to include, that boundary is
part of the gate and belongs inside it. The three properties this repo asks of a
gate — measures the thing, reads from the source of truth, verified to fail — are
worth a fourth: **it says what it does not cover.**

### The related trap: dev-only code has no gate by construction

Anything behind `import.meta.env.DEV`, `if (dev)`, or a `NODE_ENV` check is
invisible to every gate that measures a build. That is usually the point. But it
means the guard rails and diagnostics — the code most likely to be wrong, because
it is the code nobody exercises — are exactly the code least covered. Verify those
by hand when they land, or accept they are decoration.

---

## 2026-08-21 — a correct action that shows nothing reads as a failure

### The bug was that it worked

Choosing an item in a stat pill's popover moved focus to the row and scrolled it
into view. Both correct, both what the spec asked for, and on a page where
everything is already visible the whole gesture was **indistinguishable from
nothing happening**. A student clicked "Submit peer review" and concluded the
click had failed.

The focus ring is not the answer. `:focus-visible` is exactly the thing that does
not render for a pointer user, which is the user who just clicked.

**Generalisable:** if an action changes state the student cannot see, the action
is not finished. "It works" and "it appears to work" are different acceptance
criteria, and only one of them is the product.

### Picking a treatment by what it cannot fight

The arrival mark had to work on a task row and an event row, which have different
shapes, different radii, and — in the task row's case — a background wash and a
left border already carrying priority. Working through what each option collided
with is what chose it:

- **A background tint** loses the cascade. `bg-urgent-soft` is a Tailwind utility
  and utilities beat the components layer, so a normal declaration would not
  paint. A keyframe *would* (the animation origin outranks normal author rules),
  but only where motion is allowed — and it would paint over the priority the wash
  exists to state.
- **A border** changes the box and moves the layout.
- **A box-shadow** is out by standing decision: this system is light-only, no
  shadows.
- **An outline** cannot affect layout, does not contest any property the rows
  already use, and follows the element's own `border-radius` — so one rule fits
  `radius-lg` and `radius-xl` with nothing per-shape.

### The reduced-motion trap in a global reset

`app.css` ends with the usual blanket `animation-duration: 0.01ms !important`. So
a mark **painted by a keyframe** appears and vanishes within a hundredth of a
millisecond under `prefers-reduced-motion` — visually never happening, with no
error and nothing to see in a diff.

**So the mark is the static declaration and the animation only takes it away.**
Reads backwards; is the only arrangement where turning animation off leaves the
cue on. Reduced motion then gets `animation: none`, which clears the animation
NAME so the global `!important` duration has nothing to apply to, and a timer
still removes it on the beat.

Worth checking any other "flash to acknowledge" for the same inversion.

### Re-adding a class in the same task is not a change

Jumping twice to the same row has to show the cue twice. Removing the class and
adding it back inside one task is not a mutation the browser ever observes, so the
animation does not restart. Reading `offsetWidth` between the two forces a style
recalculation, which is what makes the re-add real. Old trick, still the answer.

### A dwell is not a transition

The three motion tokens (120/160/260ms) are how fast a thing changes. How long a
state persists is a different kind of number — the toast's 3000ms is the existing
sibling. Sharing a token would have tied the fade's speed to the mark's lifetime,
so the next person tuning one would silently retune the other.

The duration is read from the stylesheet by both the component and the gate, so
there is one copy of it and no drift.

---

## 2026-08-21 — hover-plus-click is two states, and only a browser says so

### A hover-opened popover swallows its own click

The first version of `StatPopover` held one boolean. Click toggled it, hover
opened it, a pointer leaving closed it. Every gate passed — 389 tests,
`svelte-check` clean, build clean — and **pressing the pill did nothing at all**.

A mouse click is preceded by a pointer entering. Hover had already opened the
panel, so the click arrived to find it open and closed it again. The same boolean
had a second fault behind it: clicking to open and then moving the mouse closed
it, because a pointer leaving cannot tell a hover it started from a click it did
not.

**The first fix was to record WHY it is open**, not just whether:
`openedBy: 'pointer' | 'command' | null`. Hover opens only what is shut, hover
closes only what hover opened, a click on a hover-opened panel pins it, and
tabbing into one pins it too.

**The second fix, the next day, was to delete hover.** Three pills sit in one row,
and in use a cursor crossing that row opened and closed panels the student never
asked for. The state machine was correct and the interaction was still wrong. With
one way in, `openedBy` had nothing left to distinguish and collapsed back to a
boolean.

Both are worth keeping written down, because they are two different lessons and
the second does not retire the first:

**Any control with two ways in has more states than it has booleans.** If two
input methods can produce the same visible state, the state has to remember which
one produced it, or the second method will undo the first.

**A correct implementation of a bad interaction is still a bad interaction.** The
`openedBy` work was real engineering spent making hover behave, and the right
answer was that hover should not have been there. Worth asking earlier whether the
second way in is wanted, before building the state that reconciles it.

**And: an interaction that is removed needs an assertion that it stays removed.**
Hover is the only route back to the swallowed-click bug, so `check:interaction`
asserts that hovering a pill does NOT open it — with a companion assertion that
the driving browser can hover at all, or the absence proves nothing.

### The gate that could not see it

`npm test` renders nothing (a standing decision), `svelte-check` is not a render,
and `check:layout` measures heights. None of the five gates can press a button.
The bug was found in the first thirty seconds of driving the built page in
Playwright, which is the same lesson as the layout work one session earlier:
**measure the thing, not a model of it.**

### A probe's own selectors need the companion assertion too

Three of the browser probe's checks failed on correct code. The probe asked
`document.querySelector('button[aria-expanded="true"]')` for "is a popover
open" — and `ShowMore` carries `aria-expanded` as well, so once the reveal had
expanded a card its own control matched. Scoping the query to `.thrive-popover`
fixed it.

Worth the note because the failure looked exactly like a product bug, and the
instinct was to change the product. What settled it was a four-line probe that
printed the state at each step instead of asserting on it.

### Silencing an a11y check versus satisfying it

`a11y_no_static_element_interactions` fires on a `<div>` carrying
`onpointerenter`. The wrapper around a pill and its panel has no honest ARIA
role, and `svelte-ignore` would have been the first in the repo. Moving the
listeners into a `hoverIntent` action removed the warning because the check reads
markup — which is, strictly, silencing it.

It is defensible here on the merits: the interactive element is the button
inside, correctly marked up, and hover is redundant with click. It is worth
writing down as the reasoning rather than the outcome, because the same move
would be wrong for a `<div>` whose click is the only way to do something.

---

## 2026-08-21 — measuring layout, and the properties of a good gate

### Measure the page, do not reason about it

Every layout number this session came off `getBoundingClientRect` in a real
browser. Three separate times, arithmetic would have produced a wrong answer:

- **`flex-1` silently defeated a `height`.** The card cap was set to 248px and
  the body rendered 423px, because `flex: 1 1 0%` in a flex column beats
  `height`. No error, no warning, and the cap "worked" in the sense that the CSS
  was present and valid.
- **A predicted 24px saving measured 8px.** That 16px gap is the only reason the
  phantom scroll below was ever found.
- **A 500px estimate of the header block was actually 375px.** Estimating in the
  right direction is not the same as estimating usefully.

**The habit:** build first, then drive the built page, then set the number. Not
the other way round, and never from a mental model of the box model.

### `scrollHeight` is an unreliable narrator

`documentElement.scrollHeight` reported 1275px while every element in the
document rendered at or above 1238px and `body.scrollHeight` agreed at 1238.

The ground truth for "can this be scrolled" is to try:

```js
window.scrollTo(0, 1e6);
const maxScroll = window.scrollY;   // 37 -> yes, and by how much
```

Everything downstream of the wrong number was wrong: the "shortest viewport
where Home fits" was 1275px for a whole phase, and no amount of header
compression was going to move it, because 37px of it was not content.

**When a height does not add up, stop and find the discrepancy.** It is a bug
roughly as often as it is a rounding error.

### A fixed-height scroll container needs `contain: paint`

A card with `height` + `overflow-y: auto` whose content overflows can leak its
scrollable overflow out to the document, giving the page dead space at the bottom
that nothing renders into. `contain: paint` stops it. `overflow: hidden`,
`overflow: clip` and `overflow-x: hidden` were all measured and all left it in
place.

It is also just *true* of a scroll container, so it is a declaration rather than
a workaround — and it costs nothing visually, because `overflow-y: auto` already
clips at the box edge on both axes.

### Three properties of a gate worth having

The session added one gate and leaned on two existing ones. What separated the
useful from the decorative:

1. **It measures the thing, not a model of the thing.** `check-layout.mjs` drives
   a browser because jsdom does no layout and reports every height as zero. A
   gate built on a model inherits the model's blind spots — which is exactly how
   `documentElement.scrollHeight` would have written a green test for a broken
   page.
2. **It reads its inputs from the source of truth.** `check-contrast.py` used to
   mirror the palette by hand, and during the repalette it was checking green
   values against a navy app and reporting 43/43. It parses `app.css` now.
3. **Prove it fails.** Every gate added this session was verified against the bug
   it was written for: commenting out `contain: paint` gives
   `renders 1238, scrolls to 1275, FAIL 37px of empty scroll` and exit 1.
   An untested gate is a comment with a run time.

### A gate that cannot run should skip loudly, not fail

`check-layout.mjs` needs a browser and `playwright-core` ships none. It exits 0
with `check-layout: SKIPPED` and the install command when it cannot find one.
A gate that fails for reasons unrelated to the code gets ignored, and an ignored
gate is worse than no gate because it looks like coverage.

It also hunts for a cached chromium from a *different* playwright version, since
skipping on the one machine where the check matters would defeat the point.

### `npm run check` is not a render

`svelte-check` passed, 0 errors, on a component that threw
`ReferenceError: meta is not defined` on every request. The prop was added to the
`$props()` TYPE but not to the destructuring pattern, and an unknown identifier
in a Svelte template is not a type error.

**A typecheck proves the types agree. It does not prove the page renders.** Serve
the route. This cost a build-and-serve cycle to find and would have shipped
otherwise.

### Extract strings on the way past, not afterwards

`messages.ts` was written before the components that use it, and the discipline
held for nine components with no retrofit. Two things made it work:

- **Anything carrying a value is a function**, not a template assembled at the
  call site. `showMore(count)` lets a translation move the number; `{count} more`
  in markup bakes English word order in.
- **Where a value is styled differently from the words around it**, the split is
  exposed as two message entries with the limitation written down, rather than
  hidden as string concatenation in the component. Two places needed it: the
  timeline's percentage and the course card's "Next:".

### Furniture competes with content for a cap

Home's Tasks card carried ~190px of fixed furniture — a progress bar, three group
headings, a Done heading, section gaps — before its first task row. Under a
height cap, that furniture was spending three and a half rows' worth of the
budget, and no cap that let the grid fit a laptop could show more than one task.

Moving the progress bar into the card's header band (outside the scroll area) and
dropping group headings while collapsed took the overhead to one heading. Same
information, four rows visible instead of one.

**Under a cap, ask what the furniture costs in rows.** The answer is often "more
than the thing it labels".

---

## 2026-08-22 — porting a provider boundary

### Diff the port, do not review it

A 2,000-line port is exactly the size where reading the diff stops working: too
big to hold, too repetitive to stay alert through. Two mechanical checks found
more confidence than an hour of reading would have:

```bash
# 1. Signatures identical?
grep -oE "export (async )?function [a-zA-Z]+\([^)]*\)[^{]*" providers.ts

# 2. What actually changed, ignoring every reflowed comment?
python3 strip-comments.py old.ts > a; python3 strip-comments.py new.ts > b; diff a b
```

The second is the useful one. Comments were rewritten heavily and formatting
differs; stripping both to bare code turned "did I change anything I did not mean
to" from a judgement call into a five-line diff that could be checked against the
list of intended changes. Eight of thirteen fixture files came out
**byte-identical**, which is a stronger statement than any amount of "looks
right".

**Do this before claiming a port is faithful.** "I was careful" is not evidence.

### The migration doc is a lead, the source is the answer

`MIGRATION.md` §2 described `buildSlotsFor` as having "deterministic ids and
deterministic availability". The ids are. Availability is
`!inThePast && !isTaken(...)` — and `inThePast` reads the clock, so the whole
window shifts at midnight and today's slots drop out one at a time.

Had I trusted the doc, the determinism test would have asserted something false
and then been "fixed" by loosening it until it passed. Reading the source first
meant the test freezes the clock and asserts the real property.

The doc was written from the same source three commits earlier by someone with
the same intentions. It still drifted. **Where a doc and the code disagree, the
code wins, and the doc gets corrected in the same session.**

### A test-only export is permanent

The three stores are module-scope, so tests need isolation. The convenient fix is
`export function resetStores()`. The cost is a function in the production surface
that only tests call — and it does not leave when the reason for it does. It
would still be exported long after Django made the stores irrelevant, and by then
nobody would remember whether the app relied on it.

`vi.resetModules()` + `await import()` per test costs a helper in the spec file
and nothing in the shipped module.

**The general form:** when a test needs a seam, first ask whether the seam can
live entirely on the test's side of the wall.

### Fake only the clock you need

`vi.useFakeTimers()` deadlocks every provider in this layer: they resolve through
`setTimeout`, so faking all timers means nothing ever resolves and every test
times out with no useful message.

```ts
vi.useFakeTimers({ toFake: ["Date"] });  // setTimeout stays real
```

**Anywhere a delay is part of the mechanism, fake `Date` and leave the timers
alone.**

### A source-scanning test must prove it is not vacuous

A test asserting "no `Math.random()` in this directory" caught two files
immediately — both of them **comments** naming `Math.random()` as the thing the
hash functions exist to avoid. The obvious fixes are both wrong: deleting the
comments removes the best explanation in the file, and dropping the test removes
the guard.

Strip comments, then scan. But a comment-stripper is exactly the kind of code
that can silently return nothing and turn the test permanently green:

```ts
expect(corpus).toContain("function isTaken");   // the strip did not eat the code
expect(offenders).toEqual([]);                  // and there is no Math.random
```

**Any test that asserts an absence needs a companion assertion that it can still
see a presence.** Otherwise it stops being a test and nobody notices.

### `import.meta.glob` beats `node:fs` in a Vite repo

Reading source files with `node:fs` passed under Vitest and failed
`svelte-check` — no `@types/node` in this project, and the typecheck is a gate.
`import.meta.glob(["./**/*.ts", "!./**/*.spec.ts"], { query: "?raw", import:
"default", eager: true })` needs no new dependency, is typed already, and is
relative to the spec file rather than to `process.cwd()`.

**Adding `@types/node` to satisfy one test would have been the wrong trade** — a
dependency for a convenience, in a repo whose whole point is to stay portable to
a Django-backed future.

### Comment the hazard at the hazard

The id generators (`nextRequestId`, `nextVersionId`) count independently of what
the seed functions inserted. They work only because someone numbered the seed
`req-000` and set the resume counter to 4 by hand. Nothing enforces it.

That was recorded in a migration doc. A migration doc is read once. The note now
sits on the generator, and it spells out the failure: seed a `req-001` and the
student's first request silently shares its id, after which `submitRequest` flips
whichever record `find()` reaches first. No error, no log.

**A hazard documented somewhere else is a hazard documented nowhere.** The test
that pins `req-001` is the other half — it fails the moment someone adds a seed
without moving the counter.

---

## 2026-08-21 — porting a React app to Svelte 5

### Probe before asserting. Every time.

Every test suite this session was written against **observed output from a
throwaway probe spec**, then the probe was deleted. Not once was it wasted, and
twice it changed what I wrote:

- **V8 is inconsistent about invalid ISO dates.** `new Date("2026-13-01")` is
  `Invalid Date`, but `new Date("2026-02-30")` silently **rolls forward** into
  March and parses fine. I would have written a wrong test from first
  principles, and I would have believed a guard was tighter than it is.
- **`Intl` output is not guessable.** `toLocaleDateString("en-US", {weekday:
  "long", month: "short", day: "numeric"})` gives `"Monday, Aug 17"`. Close
  enough to guess wrong.

**The pattern:** write a spec that only `console.log`s, run it with
`--reporter=verbose --silent=false` (Vitest hides stdout on passing tests),
read the real values, write the real spec, delete the probe.

### A test that only exercises one side of a symmetry proves nothing

The ignore store's key-space defect survived because the prototype's two test
files each exercised one surface — and they encode **contradictory** key
conventions. `isEventIgnored("evt-3-1", {"3-1": true})` assumes one; the
`filterSchedule` cases assume the other. Both pass. Together they cannot both be
right.

**The pattern:** when two callers are supposed to agree, test the round trip
between them, not each one against a fixture. The first cross-surface test found
it in one run.

### Timezone-dependent tests are invisible until they are not

A `TZ=` sweep across the suite caught one of my own new tests hardcoding a
UTC-dependent date. Cheap to run, and the only thing that finds this class of
bug:

```bash
for tz in UTC America/Los_Angeles Asia/Tokyo Pacific/Kiritimati \
          Pacific/Midway Australia/Lord_Howe Asia/Kathmandu; do
  TZ=$tz npx vitest --run
done
```

Lord Howe has a **30-minute** DST offset and Kiritimati is UTC+14 — the two that
break naive arithmetic.

**The rule that prevents it:** build every fixture instant from **local parts**
(`new Date(y, m, d, h)`) and only then `toISOString()`. Never
`new Date("2026-08-17")`, which parses as UTC. The one test that *had* to pass a
malformed ISO string is exactly the one that failed the sweep.

### `NaN` is a `number` to the type system, `null` is not

The single most useful thing learned this session. An unparseable date used to
produce `days: NaN`, which typechecks in `a.days - b.days` and `days <= WEEK`
and poisons both silently. Changing it to `days: null` inside a discriminated
union turns every arithmetic call site into a **compile error** the author has to
answer for.

**The pattern:** when a value can be "absent", make the absence a type the
compiler cannot ignore. A sentinel that shares its type with the valid case is
not a guard.

### Widen the type instead of smuggling a sentinel into a field

`describeDue` needed a fourth outcome. The temptations were `urgency: "upcoming"`
with a magic label, or `days: -1`. Both would have read as a real deadline
somewhere downstream. A discriminated union on `urgency` gave detection with no
string matching, kept `DueUrgency` meaning only "how urgent is this real
deadline", and made the invalid state unrepresentable by accident.

Deliberately kept `"unknown"` **out** of `DueUrgency`, so every
`Record<DueUrgency, Tone>` map in the UI stays exhaustive over real statuses.

### Run the existing suite *before* adding new tests to a fix

After adding both guards, I ran the 159 existing tests and only then wrote the
16 new ones. That ordering is what makes "all 159 pass unmodified" a real claim
about the guard rather than an artifact of tests written alongside it.

### Pure logic ports across frameworks for free — and that is a testable claim

All 83 tests moved from React to SvelteKit with **only an import-alias change**
and passed on the first run. Nothing behavioural was touched. That is the
strongest available evidence the logic really was pure, and it is worth
structuring a port to produce that evidence.

---

## Svelte 5 specifics worth remembering

### `$state` in a plain `.ts` file is silently inert

Svelte only processes runes in `.svelte.js` / `.svelte.ts`. A plain `.ts`
containing `$state` compiles, runs, and is not reactive — no error, no warning.
The worst failure mode available.

**The rule:** if a file declares a rune, it gets the `.svelte.ts` suffix.
Files that only *read* reactive state from such a module stay `.ts` — reactivity
is tracked at property access, so it works from anywhere.

### Most React caching has no reason to exist here

Six workarounds dropped, all for one underlying reason: **Svelte tracks the
signal, not object identity.** `useMemo` for referential stability,
`useCallback` for stable function identity, a frozen shared `EMPTY` snapshot —
all of it existed so downstream memos would not bust. There are no downstream
memos.

The one that had teeth: `useCalendarPrefs`'s memo was genuinely load-bearing in
React (a fresh `prefs.hidden` array every render busted the schedule filter over
42 grid cells). It is *pointless* here. Porting it mechanically would have been
cargo-culting a fix for a problem that no longer exists.

**Corollary:** a 9-dependency `useMemo` becomes a plain function the caller
wraps in `$derived`. The caller is the only place that knows what to key the
caching on, and there is no dependency array to drift from the body.

### The `use*` prefix is itself a React-ism

`useTaskDoneOverrides` is not a hook in Svelte: no call-order rules, callable
outside a component, callable conditionally. Keeping the prefix would have been
cargo-culting the *naming* of the very thing being removed. Stripped
mechanically across ~20 exports.

### Actions replace effects that manage a listener

The React version of escape-to-dismiss was a `useEffect` keyed on `open` that
re-checked `open` inside itself, with a dependency array keeping the listener in
step. As a Svelte action on an element inside `{#if open}`, the listener's
lifetime **is** the element's. Nothing to keep in step.

### `bind:this` deletes a whole category of React ceremony

`useFloatingGeometry` took a ref as a parameter specifically because returning
it would have tripped the React Compiler's render-phase rules. That constraint,
and the shape it forced, simply do not exist.

### Snippets are the right answer for "two lists that must not drift"

`RailLink` and `BarLink` were components in the prototype for exactly one
reason: the rail renders two lists and they must look identical. A snippet does
that without leaving the file that uses it.

### Small mechanical notes

- Render a component from a variable with `{@const Icon = item.icon}` then
  `<Icon />`. Not `<svelte:component>`, deprecated in Svelte 5.
- A polymorphic tag is `<svelte:element this={as}>`. Keep the union narrow
  (`'h2' | 'h3'`) so it cannot quietly leave the document outline.
- `{@const}` must be an immediate child of a block — it cannot live inside an
  element.
- Reading a `$props()` value at init warns `state_referenced_locally`. Use
  `$derived.by()`; a throw inside it lands on first read, which is during
  render — the same moment React threw.
- SvelteKit ≥2.12: `page` from `$app/state`, not `$app/stores`.
- Some SvelteKit versions ship **no `svelte.config.js`** — adapter and compiler
  options live in `vite.config.ts`.

---

## Testing infrastructure

### A fake `localStorage` beats jsdom

Deciding "am I in a browser" by asking whether `localStorage` **exists** — not
via `$app/environment` — means the entire persistence layer is testable in the
Node environment the suite already uses. A ~40-line `fakeStorage` with
`installStorage()` / `uninstallStorage()` covers the server case (delete it),
the quota case (`failWrites()`), and assertions on what was actually persisted
(`dump()`).

It also covers the nastiest case: storage that **throws on property access**,
which happens in sandboxed and cookie-blocked contexts. Guard with `try/catch`
around the *access*, not just the call.

### Module singletons need `vi.resetModules()` per test

Stores are created at import. `vi.resetModules()` then `await import()` gives a
fresh graph per test. Install the fake storage before the import for tidiness,
though it is read lazily so it does not strictly matter.

**Do not mix** `vi.resetModules()` with static imports of the same module in one
file — the static import is a different instance. That is why store tests live
in their own spec files rather than being appended to the existing pure-logic
ones.

### Document an out-of-scope defect as a test, named as one

Three tests now exist whose names begin `DEFECT:` or `DOCUMENTS A GAP:`, each
with a comment saying it records current behaviour rather than desired
behaviour, and why it was not fixed. This keeps the suite green, makes the defect
impossible to lose, and means the fix arrives as a **failing test** — which is
the right signal.

The alternative, leaving it untested, is how the ignore store's split survived
this long.

### Do not write a test that pins garbage output

`describeDue("not a date")` used to return `"in NaN months"`. Writing
`expect(...).toBe("in NaN months")` would have entrenched it. Flagging it and
leaving it uncovered was correct — and it became a real fix one phase later.

---

## Process

### Verify against the artifact, not the source

Checked the *compiled* CSS for `--thrive-control-stroke:1.5px` and for the
absence of the dropped tokens, rather than trusting that the source said so. Two
of my greps failed because the output is minified (`control-stroke:1.5px`, no
space) — a tooling artifact that briefly looked like a missing token.

### Kill stale dev servers before believing a 404

Two orphaned `node build/index.js` processes on port 3000 made a verification
return 404, and I nearly concluded a route was not being matched. `lsof -ti:3000`
first.

### A brief's counts can be wrong; check them and say so

Three numbers in the original inventory brief were wrong (21 providers, 61
tests, the location of `todayKey`). Running the suite and grepping the exports
took two minutes and corrected all three. The old repo's own `CODEMAP.md`
undercounts providers the same way, which is probably the source.
