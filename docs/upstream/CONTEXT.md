<!-- updated-at: 613668d -->

# CONTEXT

The living context file. Read this and you should be able to pick up the work
without asking anyone.

**Regenerated in full every handoff.** Never patch it — a partial edit leaves
stale claims sitting beside fresh ones with no way to tell them apart.

This one covers **Phases 8 and 9, four follow-on redesigns, a Netlify deploy and a
typography pass**, regenerated end to end. The previous version was two phases
behind and had been patched twice in-session; this is the first clean pass since
`695dbb2`.

---

## 1. What this is

**THRIVE** — an AI coworker and knowledge platform for the UC San Diego Rady
School **MSBA** program. One calm surface replacing the hunt across fragmented
systems (Canvas, TSS/EASy, the CMC, email, a dozen PDFs).

This repo is the **rebuild**. A working Next.js prototype already exists and is
now frozen; this is the SvelteKit + Django version of it.

- **Repo:** `rsm-msaad/thrive`, private, GitHub. Default branch `main`.
- **Owner:** one developer, working solo. Teammates are about to get repo access
  to build the Django backend.
- **Local path:** `~/code/thrive`
- **Deployed:** Netlify, from `main`. **No authentication** — see §20.
- **No PRs.** Everything goes direct to `main`. Commit hashes stand in for PR
  links throughout the docs.

### The frozen prototype

`~/Desktop/Test 1/Thrive-msba-brain` — Next.js 16 / React 19, at commit
`4e0a65b`. **READ-ONLY REFERENCE. Never write to it.** Its uncommitted working
tree has been left exactly as found and verified untouched after every phase.

Everything worth knowing about it is inventoried in `MIGRATION.md` (§3), so in
practice you read that rather than the old tree.

**Phase 9 was the first surface with no prototype at all.** Ask THRIVE does not
exist in the old tree — the closest thing is a floating assistant panel behind a
feature flag, read for tone rather than ported. From here some phases are design
rather than migration, and the docs should say which.

### A note on dates in this repo

Several entries and `app.css` comments are stamped **2026-08-22**, a day ahead of
the real date, from a mis-stamp during the repalette. **Commit hashes are the
reliable ordering.** Dates here are ±1 day; do not use them to reason about
sequence.

---

## 2. Repo layout

```
thrive/
├── BACKEND.md       the contract Django has to satisfy — the backend's entry point
├── CONTEXT.md       this file — the snapshot
├── HANDOFF.md       the diary — what happened, per session
├── MIGRATION.md     the map of the frozen prototype, and the port spec
├── CONVENTIONS.md   the rules the tooling does not enforce
├── CODEMAP.md       navigation map for this repo
├── CHANGELOG.md     dated session summaries, newest first
├── FINDINGS.md      reusable patterns and lessons
├── BUGS.md          defects found and fixed
├── DEPENDENCIES.md  packages and why each is here
├── TESTING.md       coverage and gaps
├── setup_info.md    environment, versions, and how to run things
├── README.md        the public-facing explanation, and the doc guide
├── netlify.toml     the deploy config, at the root because Netlify reads it there
├── frontend/        the SvelteKit app
├── backend/         Django — not started, README only
└── scripts/
    ├── check-contrast.py       58 assertions over the palette and app.css
    ├── check-layout.mjs        17 targets x 3 viewports, in a real browser
    └── check-interaction.mjs   190 assertions: the popovers, task editing, the
                                calendar, booking, Ask THRIVE, the nav
                                disclosure, and the page measure
```

`MIGRATION.md` is also the **only surviving copy** of the prototype inventory —
it was never committed to the old repo.

**`BACKEND.md` is new and is where a backend contributor starts.** The README's
doc guide now routes by side and says honestly which files are frontend build
history that a backend engineer can skip.

---

## 3. MIGRATION.md is the spec, and it is now partly historical

1,457 lines, nine sections, written by reading the prototype at `4e0a65b`.

| § | Contents |
|---|---|
| 1 | Route inventory — 13 routes, which are real, which return `PagePlaceholder` |
| 2 | The data layer — provider signatures and the three module-level stores |
| 3 | Date and time handling — the timestamp rule as actually implemented |
| 4 | Component inventory — 75 components, shadcn/Radix wrappers marked |
| 5 | Design system — every token, and the conventions a port must preserve |
| 6 | State and stores — 14 `localStorage` keys, four properties |
| 7 | Tests — all 83, file by file |
| 8 | React-specific code needing a real decision, not a translation |
| 9 | Known defects, on a "build correctly, do not reproduce" list |

**It documents the PROTOTYPE, not this repo**, and the two have now diverged
enough that four of its claims are stale about the current tree. `BACKEND.md` §9
lists them: the provider count is 27 rather than 25, `cancelAppointment` releases
by slot id rather than by start time, slot availability also depends on the clock,
and a `DegreeProgress` field it warns about has been removed.

### The standing rule, and the four shapes it has taken

**Where MIGRATION.md and the prototype source disagree, the source wins, and it
gets reported.** Exercised repeatedly.

**Shape two: sometimes the source is simply WRONG, and porting it verbatim is the
bug.** Every date converter in the Next `taskBoard.ts` throws a `RangeError` on a
due date that will not parse. The agenda rendered all three groupings identically.

> **The right instinct when the source is wrong is to improve on it, not to port
> the mistake** (owner, 2026-08-21).

**Shape three: sometimes the source contradicts ITSELF.** MIGRATION §4 and
`WeekView.tsx`'s own comment both say week view is not rendered below `40rem`;
`CalendarView.tsx` renders it at every width with a horizontal scroll, which that
same comment calls the wrong answer.

> **A source that contradicts itself is not a source to follow** (owner).

**Shape four, found in Phase 8: sometimes the source declares a coupling and never
builds it.** `BookingPanel.tsx` takes a `selectedDayKey` prop documented as "day
chosen elsewhere on the page (the mini calendar)" and carries a full
adjust-during-render mechanism to adopt it — but `BookingArea.tsx` never renders a
calendar. The month calendar Phase 8 was asked to build was a coupling the
prototype had already declared and left dangling.

This is the mildest shape and the most encouraging: **a dangling declaration is a
design intention with the plumbing already in place.** Worth grepping for before
assuming a change is new.

---

## 4. Stack

**Frontend** — SvelteKit 2.63 · Svelte 5.56 (runes, forced outside
`node_modules`) · TypeScript 6 strict · Vite 8 · Tailwind v4 · Vitest 4 · npm.

Note this SvelteKit version has **no `svelte.config.js`** — the adapter choice,
the runes setting and the Vitest projects live in `vite.config.ts`.

**Two adapters, and an environment variable picks one.** `@sveltejs/adapter-netlify`
by default (what a push to `main` deploys); `@sveltejs/adapter-node` under
`ADAPTER=node`, which is what the two browser gates spawn — they drive a real
long-running server and a bundle of serverless functions is not that. Out
directories are separate: `build/` for Netlify, `build-node/` for the gates.

Nothing about the app differs between them, and that was checked rather than
assumed: there is no `prerender`, no `ssr = false` and no `csr = false` anywhere in
`src/routes`, so every route is server-rendered per request either way. That
property is load-bearing — `new Date()` inside a `load` is this app's one answer to
"what is today", and a prerendered route would stamp every relative fixture date at
build time.

**Backend** — Django, not started. **Nothing here talks to it.** The provider
signatures are the only contract it has to honour; see `BACKEND.md`.

**`ORIGIN` is an adapter-node requirement**, not a Netlify one. Without it every
form POST is a 403, and the dev server is unaffected — so it worked in dev and
failed only in the build. See §20 and `setup_info.md`.

**No shadcn-svelte and no bits-ui yet.** Deferred deliberately. The stat pill
popover, the due-date editor, the calendar's key bar, the add form's kind picker,
`ItemDetail`, and the nav rail's disclosure are all hand-built; the agenda's
grouping control is a deliberately native `<select>`. Phases 8 and 9 added no new
primitive — the booking panel's choices are buttons with `aria-pressed` and Ask
THRIVE's composer is an `<input>` in a `<form>`.

**Dependencies added since Phase 1: two.** `playwright-core` (2026-08-21) for the
two browser gates, and `@sveltejs/adapter-netlify` (2026-08-21) for the deploy.
Between them the browser gates have caught a dead button five other gates called
green, a `derived_inert` warning live in production, the undo arrival's silent
no-op, an unclamped `line-clamp`, a TypeError on every dialog close with focus in a
field, a 403 on every form submission, and a chat log that stopped being a scroll
container. `@types/node` was rejected in Phase 5 and stayed rejected when the
adapter switch wanted `process.env` — see §9.

---

## 5. Where the port has got to

| Phase | What | State |
|---|---|---|
| — | Inventory the prototype → `MIGRATION.md` | done |
| 1 | Scaffold + design system | done |
| 2 | Pure logic + its 83 tests | done |
| 3a / 3a-fix | `format.ts` suite; input guards on `describeDue` | done |
| 3b | Browser persistence layer → Svelte 5 runes | done |
| 4 | App shell, navigation, root layout | done |
| 5 | Data layer — providers, fixtures, three stores | done |
| — | Repalette to campus brand; tighten the two-face type rule | done |
| — | Trim navigation to four destinations | done |
| 6a | Home — the page, four cards, fit-on-one-screen | done |
| — | Stat pill popovers, the reveal channel, the arrival cue, `check:interaction` | done |
| 6b | Task editing — tick, undo, rename, priority, notes, due date, reorder, add | done |
| 7a | Calendar spine — `buildScheduleData`, month grid, selected day, day sections | done |
| 7b | Calendar views + filter — switcher, week, agenda, key bar | done |
| 7c | Calendar editing — item detail, add form, the events section | done |
| **8** | **Appointments — cards, chip strip, booking panel, "Your day", a clickable month** | **done** |
| **9** | **Ask THRIVE — a history rail, a chat window, three destinations in the nav rail** | **done** |
| — | **Page measure and gutters; the calendar's Key beside the grid** | **done** |
| — | **Netlify deploy, adapter-node retained for the gates** | **done** |
| — | **Typography: the top four steps shrink above 40rem** | **done** |
| **next** | `/assignments` — the same `TaskRow`, no groups | not started |
| then | The retrieval service behind Ask THRIVE | needs a backend |
| later | **Group Projects — the first shared surface** | scoped, not built |
| later | Floating widgets, behind `FEATURES` | not started |

**640 tests, 29 spec files, all passing**, green in **all seven timezones**.
`svelte-check` clean over 459 files, 0 warnings. Build clean. Contrast **58/58**.
Layout **51/51**. Interaction **190/190**. 112 commits, all pushed.

**179 files under `frontend/src`** — ~30,755 lines, 22,458 source / 8,297 test.

**Four destinations are built:** `/`, `/calendar`, `/appointments`, `/ask`. That is
the whole of `primaryNav` — **every visible navigation item leads to a real page**,
which has not been true before.

### The four follow-on changes, and why three of them were reversals

Worth reading before touching either new surface, because the churn is the record.

1. **Booking flow measured and rearranged**, then reverted. The month grid read
   backwards; a day list fixed that; the owner reverted to the chip strip.
2. **Ask THRIVE's destinations moved into the nav rail**, and the page's second
   rail was removed as almost-empty — then brought back as a **history** rail,
   which is a different thing with one job.
3. **The page container** went 72rem → 96rem → 80rem plus a 40px gutter, with
   `/calendar` alone on 96rem. Both extremes were wrong and the fix needed two
   knobs.
4. **The month grid on `/appointments` became clickable**, which deleted the
   read-only mode added a change earlier.

**What that cost:** two components written and deleted, three pure functions
written and deleted with their tests, `MiniCalendar` given and then stripped of two
modes, and a fixture constant moved 5 → 25 → 5. All of it deleted rather than left
unreachable.

**What it bought:** every reversal left a residue that was never about the design
being reverted — `publishedByDay`, the per-chip open count, and `BookingDayView`
all survive because they answer questions the chip strip has too. See FINDINGS.

---

## 6. The design system

`frontend/src/app.css` is the single source of truth. **Never hardcode a colour,
size, radius, or duration in a component.** `designSystem.spec.ts` fails the
build on a hex or a font name in markup — and, since 2026-08-21, on a
`.thrive-*` class used from TypeScript that `app.css` does not define.

Three layers: raw `--thrive-*` tokens → shadcn semantic vars remapped onto them →
`@theme inline` exposing both as Tailwind utilities.

**Direction: soft cream, hairline, Rady navy with a yellow accent.**

### The palette is the campus brand

Official values from `brand.ucsd.edu/visual-brand/color`, not approximations:

| Token | Value | Notes |
|---|---|---|
| `primary` | `#182b49` | **UC San Diego Navy, PMS 2767.** 14.18:1 on card |
| `primary-hover` / `-active` | `#22395e` / `#101d33` | Hover **lifts**, active **presses** — inverted from the green's ramp, because darkening navy twice heads to black |
| `yellow` | `#ffcd00` | **UC San Diego Yellow, PMS 116.** Accent only |
| `primary-soft` | `#e9edf3` | Partial-progress fill |
| `primary-fill` | `#9dbcdb` | Light fill, 1.97:1 — **cannot hold its own edge, stays ringed** |

**Yellow is constrained by measurement, not taste.** 1.50:1 on card, 1.43:1 on
cream, 1.31:1 on sunken. WCAG 1.4.11 asks 3:1 of a graphic that carries meaning,
so on every light surface here yellow is **decoration** and cannot be the only
thing saying something — the same standing as a hairline. Its one legible home is
against navy at 9.45:1, which is the campus pairing anyway. Enforced by three
**ceilings** in the contrast gate: if it ever clears 3:1 someone will promote it
to an indicator and get away with it.

**Yellow is not a locator.** "You are here" stays `indigo`. Two colours meaning
"here" is how a reservation dies.

**Gold `#c69214` (PMS 1245) was measured and rejected** at 2.79:1. `watch`
already covers a legible warm accent.

### Reserved colours

| Token | Value | Reserved for |
|---|---|---|
| `indigo` | `#4c5bd4` | **"You are here" and nothing else** |
| `urgent` | `#b8462f` | Overdue and genuinely urgent only |
| `on-track` | `#00716c` | Status only. **Teal** — see below |
| `watch` / `needs-help` | `#946000` / `#7851c2` | Status only |
| `civic` / `later` | `#994ea3` / `#4c74ad` | Categorical only, never status |

**`indigo` has three consumers, and they are all the same sentence.** "You are
here" in the navigation, `.thrive-arrived` (the ring on a row something has just
moved the student to), and the calendar's two markers: today's date in a week
column, and the "next up" item — named in the header's line and outlined in the
square strip so the two agree. An arrival cue and a "this is next" marker *are*
"this is where you are now", so this widened indigo's use without weakening its
meaning. Anything else wanting indigo has to make that same argument.

**`categoryDot` / `categoryTag` are the one place hues are used CATEGORICALLY
rather than as status**, and they are exempt from the reservations by construction:
eleven calendar streams need more distinct dots than the reserved palette supplies,
which is why the categorical `civic` plum and the neutral `later` slate exist.
Every dot is paired with a written label in the key and in every row, so no meaning
there rests on colour alone. **Coral is deliberately absent from that map** — a
month grid dotted coral on every assignment day would drain "overdue" of meaning,
so assignments take amber, which already means "due soon" on a `DueChip`.

**`on-track` is the only reserved colour whose MEANING has changed.** It moved off
green on 08-15 because green had become "an action you can take" and a green chip
beside a green button read as one signal. A blue chip beside a **navy** button is
that same collision, so it moved again, to teal.

### The chroma pass (2026-08-21) — saturation held at fixed lightness

Five status hues gained chroma and **not** lightness, because the month grid's
dots read muted and muddy and they are the only thing on that grid carrying stream
identity.

**The constraint that shaped it:** each of these is used as TEXT somewhere as well
as as a fill (see `tones.ts`), so each must clear 4.5:1 on card. Vibrance could not
come from lightening them. Each was converted to oklch, its chroma raised at its
own L and H, and capped below the gamut maximum where the maximum was garish.

| Token | Before | After | Chroma | Card | Cream | Sunken |
|---|---|---|---|---|---|---|
| `on-track` | `#14706b` | `#00716c` | 0.0803 → 0.0856 (1.07×) | 5.90 → 5.87 | 5.60 → 5.57 | 5.13 → 5.11 |
| `watch` | `#8f6220` | `#946000` | 0.0988 → 0.1137 (1.15×) | 5.34 → 5.34 | 5.06 → 5.07 | 4.64 → 4.65 |
| `needs-help` | `#6a5fb0` | `#7851c2` | 0.1240 → 0.1697 (1.37×) | 5.42 → 5.59 | 5.14 → 5.31 | 4.71 → 4.87 |
| `civic` | `#8a5f8f` | `#994ea3` | 0.0884 → 0.1497 (1.69×) | 5.10 → 5.29 | 4.85 → 5.02 | 4.44 → 4.60 |
| `later` | `#64748b` | `#4c74ad` | 0.0407 → 0.1001 (2.46×) | 4.76 → 4.76 | 4.52 → 4.52 | 4.14 → 4.15 |

Every ratio moved by at most 0.19 and none moved down past its floor. **Contrast
stayed 58/58 with no threshold touched.**

**What it bought, honestly: very little for teal and amber.** Both were already at
the sRGB gamut boundary for their lightness, so "push chroma, hold luminance" gave
them 1.07× and 1.15×. That is a real limit rather than a tuning failure — the only
way to make those two more vivid is to move lightness, which the contrast floor
forbids. **The size change below did more than the colour did.**

**The collision it fixed.** `later` and `muted` were the two least distinguishable
dots by a wide margin — OKLab dE **0.039**, about half the next-closest pair — and
between them they carried FOUR of the eleven categories (to-do and San Diego on
`later`, custom and UCSD on `muted`). `muted` cannot move: it is the colour of all
secondary text and must stay neutral. `later` can, and nothing about "later"
requires grey, so it now reads blue. **dE 0.039 → 0.094, and the worst pair on the
whole grid went 0.039 → 0.078.**

**The collision it avoided, which is the more useful lesson.** Violet is boxed in
between indigo at H 273 — RESERVED — and civic plum at H 323, and **both indigo and
the Rady dot appear on the month grid at once**. `needs-help` sat at H 288, nearer
indigo, and was already only dE 0.072 from it, so raising chroma along its own hue
walked it *into* the reserved colour (dE 0.047 at C 0.175 — worse than the worst
pair before the pass). Re-centring the hue at **296** buys 1.37× the chroma for
nothing: separation from indigo 0.0723 → 0.0727 and from civic 0.0744 → 0.0777,
both marginally better. **It is the one hue that moved, and the shift is what paid
for the saturation.**

> **Raising chroma moves a colour toward its neighbours in hue as well as away from
> grey.** Check a saturation change against every RESERVED colour, not just against
> the ones it is meant to separate from.

### Surfaces, ink, lines

Surfaces `bg #faf9f5` cream / `surface #fff` / `sunken #f1efea` (also the row
hover fill, and the fill of every editor panel a row opens). Ink `ink #17181c`,
`body #3a3b42`, `muted #6b6c72`, `faint #85868c` — **only the first three may
carry text**, and `faint` is held below 4.5:1 by a ceiling so words placed in it
fail a check.

**`muted` and `ink` were deliberately NOT touched by the chroma pass.** `muted` is
the colour of every piece of secondary text in the app and `ink` is every heading;
tinting either would tint the whole interface to make two dots better.

**A 1px decorative hairline and a 1.5px control boundary are different things,
carried by different tokens, and must never collapse.** Control boundaries owe
3:1 under WCAG 1.4.11 because the boundary is the only thing marking where the
control is. Only `.thrive-checkbox` and `--input` consume the 1.5px stroke.

**There is a third ring width, and it is deliberately not either of those.**
`--thrive-arrival-ring: 2px` matches the focus ring in the base layer, because
both draw a ring around something you have just arrived at and two ring weights
would read as two kinds of thing. It is not the 1.5px control stroke: that one
exists because a control's boundary is the only thing saying where the control
is, and a row is not a control.

### Type: two faces, and the rule is tight now

**DM Sans for everything. JetBrains Mono for NUMBERS ONLY.**

The old rule ended "…and any label that is a system value", and almost any label
can be argued into that, so mono spread to eyebrows, view switchers, chips,
stream names and tags. A face used for a third of the interface is not an accent,
it is a second body font.

- **Mono keeps:** clock times, counts, unit totals, percentages, fractions, IDs —
  values a person *scans or compares*, where digits lining up is the point.
- **Mono loses:** anything made of words. A date in prose is words and takes DM
  Sans; the time inside it is a value and stays mono.
- **The test:** would you ever want this to line up in a column with the thing
  above it? Column → mono. Sentence → sans.

Expressed as two classes so a component asks for a **treatment**, not a font:
`.thrive-numeric` (mono + tabular figures together) and `.thrive-eyebrow` (size,
case, tracking, weight for a small label). A component that writes `font-mono`
fails `designSystem.spec.ts`.

**The calendar was the rule's largest single test, and it is the biggest visual
difference from the prototype.** The Next calendar set the day figure, the
breakdown line, the whole "next up" sentence, every category tag, the view
switcher, the key bar's chips, the weekday initials, the agenda's group headings
**and every label in the detail dialog and the add form** in mono. Here only the
values are: the day figure, the `n of m done` fraction, the clock times, the day
numbers, the `+n` overflow, the group counts, and the add form's time input.
Everything made of words is DM Sans.

**Weight is not in the type scale.** Set it at the call site or you get 400. Only
400/500/700 load, so `font-semibold` (600) synthesises — never use it.

### The top four type steps are responsive (2026-08-21)

`lg`, `xl`, `2xl` and `3xl` shrink above `40rem`: 22→20, 27→24, 34→28, 40→32.
`base` (18) and below do not move, because 16px body is the readability floor and
there is nothing to give back down there. Ratios between the big steps tighten from
~1.24 to ~1.16, which is what a display scale wants — a page title is still twice
body.

**What was NOT responsible, checked rather than assumed.** The 106.25% root bump is
`@media (width < 40rem)`: a MOBILE bump raising a 15px body to 16px on a handset.
The type renders identically at 1512 and 1920, so nothing was scaling with the
viewport; the top steps were simply drawn large for a 72rem page, and a wider
container gave them room to look it.

**Why an override rather than editing the tokens.** Editing them would shrink the
phone too, because the root bump multiplies whatever it is given, and mobile is
deliberately unchanged. 40rem because that is the boundary the root bump already
uses, so the system has one type breakpoint rather than two.

**And one thing that had to be read out of the compiled CSS.** The first attempt
overrode `--text-3xl` in a media query and changed nothing measurable: **`@theme
inline` BAKES a literal theme value into the utility** — `.text-3xl{font-size:2.5rem}`
— so there is no variable left at runtime. A theme value that is itself a `var()`
is inlined as the reference instead, which is why `--thrive-topbar-height` has
always been overridable. The four steps now read from raw `--thrive-text-*` tokens.

Type scale 12/13/14/**16 body**/18/22/27/34/**40**, tracking on the top three
steps only plus `.thrive-eyebrow`. Radii 4/6/8/10/**16**. Motion 120/160/260ms.
Light-only, no shadows. Below `40rem` the **root** goes to 106.25%.

### The component classes

Nine, and each exists because Tailwind cannot express it at the call site:
`.thrive-numeric`, `.thrive-eyebrow`, `.thrive-panel`, `.thrive-row`,
`.thrive-checkbox`, `.thrive-strike`, `.thrive-card-body`, `.thrive-popover`,
`.thrive-arrived`.

**Still nine after 7a, 7b, 7c, 8 and 9**, which is worth noting: five phases and
twenty-eight new components added no new treatments. **`ItemDetail` in particular
did not earn a `.thrive-dialog`** — its scrim is `fixed inset-0 bg-ink/20` and its
panel is a `.thrive-panel` with a max-height, all of which Tailwind expresses. Nor
did the chat window earn a `.thrive-chat`: what it needed was a HEIGHT, which is a
token, not a treatment.

- **`.thrive-popover`** carries only a WIDTH:
  `min(--thrive-popover-width, 100vw - 2 * --thrive-popover-viewport-inset)`. The
  clamp is what stops a pill near the right edge opening a panel off the screen.
  Not a `max-width`, or three pills would open three different-width lists.
- **`.thrive-arrived`** is the arrival ring. See §13, and note it is the only one
  of the nine applied from TypeScript rather than markup — which is why
  `designSystem.spec.ts` scans `.ts` files too.
- **`.thrive-checkbox` did not grow for 6b.** A 17px box is below the 24px WCAG
  2.5.8 pointer target the Next row cited when it built a 24px skin. Rather than
  change a design-system size, the row makes its **title** the checkbox's
  `<label>`, so the tick target is the width of the row.

### The layout tokens, and why each is one

**Four separate questions, never solved with each other**, learned by getting two
of them wrong in turn:

| Token | Utility | Answers |
|---|---|---|
| `--container-page` (80rem) | `max-w-page` | how wide may a page get |
| `--container-wide` (96rem) | `max-w-wide` | …and `/calendar`, which wants more |
| `--thrive-page-gutter-x` (2.5rem) | `lg:px-page-x` | how far off the edges does it sit |
| `--container-measure` (68ch) | `max-w-measure` | how long may a LINE OF TEXT get |

**The shell no longer owns the width.** `max-w-6xl` used to sit on `AppShell`'s
`main`, so one number governed every route and a page that wanted more could not
have it without widening Home by accident. The shell provides the gutters; each
page names its own measure.

**The gutter and the cap are two knobs and you need both.** 72rem left ~120px of
dead margin at 1512px, so it went to 96rem — and then the cap stopped biting at
that width entirely, the gutter collapsed to the shell's 20px of padding, and
content ran to the edge. A gutter alone does not solve a 2560px monitor; a cap
alone does not solve a 1512px one.

At 1512 every route is gutter-limited to 1192px, so the two caps are
indistinguishable there and only separate on a bigger screen: at 1920 the page
stops at 1280 and the calendar at 1536.

**The line length is separate from all of it.** A paragraph at 1500px is not
readable, so containers fill their allowance and TEXT does not. `ch` rather than
`rem`, because the constraint is characters per line and `ch` tracks the font.
**Put the cap on the element that OWNS the text** — a full-width `<p>` wrapping a
capped `<span>` looks identical and is not the same thing.

### Three size tokens, and why each is a token

**`--thrive-checkbox-size: 17px`** (7a) replaced that number written in two
places. `.thrive-checkbox` sizes itself from it, and any row rendering a **spacer**
where a checkbox would go reaches for the same value via `size-checkbox` — the
calendar's `ItemRow` does, which is what makes a list of classes and tickable tasks
align in one column instead of two ragged ones. The Next version hardcoded
`size-[17px]` there: a literal that agrees with the stylesheet only until somebody
resizes the control.

**`--thrive-cal-dot: 8px`** (7c follow-on), up from a hardcoded `size-1.5`. Same
argument in a sharper form: the dot and the row that reserves its height have to
agree, because the row's height is what stops the grid reflowing between a day with
dots and a day without. A `size-2` paired with a hand-picked `h-1.5` clips
**silently**.

**8px was measured, not chosen.** Three dots plus two 2px gaps is 28px; the "+n"
overflow case is two dots and a count in 36px; the narrowest cell the grid draws is
38px at a 320px viewport. No clipping, no reflow and no horizontal overflow at any
of six widths, with 5px of slack at the 375px this app actually supports. **It is
1.8× the area of the 6px dot, and that is most of the legibility the whole dots
pass bought — more than the saturation did.**

**`--thrive-chat-height: 34rem`** (Phase 9), applied above `xl` only. This one is
a token for a different reason from the other two: not because two places have to
agree on a number, but because **the number is what makes a layout work at all.**

Without a definite height on the chat panel, the log's `flex-1 min-h-0` resolves
to its own content — there is no height to divide up — so the document grows
instead of the log scrolling, the composer walks off the bottom as a conversation
lengthens, and the log's `tabindex` guards an overflow that never happens. The
gate said so by permanently skipping its own keyboard-scroll assertion.

**34rem rather than a viewport calculation**, and both alternatives were
considered: `calc(100dvh - topbar - gutters - header)` is brittle in two
directions, since the header above it wraps to two lines at some widths and `dvh`
moves under a mobile browser's collapsing chrome. A fixed panel that fits the
shortest desktop viewport this app targets (1052px) is calmer, and the document
scrolls past it the way it does past any other panel.

**Deliberately not applied below `xl`.** On a phone the whole page scrolling is
the right behaviour, and a 544px box inside an 812px screen gives a student two
nested scrollbars to fight.

> **A `min-h-0` chain makes a child ABLE to shrink. Something still has to give it
> a height to shrink within.**

**And `flex-1` on that panel is gated on `xl`**, which is the other half of the
same lesson. In the row it governs WIDTH; in the column below `xl` it governs
HEIGHT and silently beats the token beside it. That shipped for one commit and the
only signal was `check:interaction` SKIPPING its own keyboard-scroll assertion.

**`--thrive-chat-measure: 65ch`** caps the message text so a 90rem panel does not
mean a 140-character line. Each bubble is `min(85%, that)` — the percentage still
wins on a phone, and it is what keeps the inset that makes a conversation read as
two voices.

### Durations: motion versus dwell

Three motion tokens (120/160/260ms) are **transition lengths** — how fast a thing
changes. `--thrive-arrival-duration: 1200ms`, the toast's 3000ms, the undo's
6000ms and the live region's 4000ms are **dwells** — how long a state persists.
They are different kinds of number and must not share a token: reusing
`--thrive-motion-slow` for the arrival mark would have tied the fade's speed to
how long the mark lasts, and the next person to tune one would silently retune the
other.

The three dwells that are not in `app.css` live at their definitions
(`UNDO_MS` in `userEdits`, `VISIBLE_MS` in `toast`, `ANNOUNCE_MS` in `TasksCard`)
because nothing in CSS reads them. The arrival duration is in `app.css` precisely
because two things do.

`arrive.ts` READS `--thrive-arrival-duration` from the computed root style rather
than repeating it, so the timer that removes the mark and the animation that fades
it cannot drift apart. `check-interaction.mjs` reads the same token for the same
reason.

**1200ms is a judgement, not a measurement**, and it stands until a real student
says otherwise (decided 2026-08-21).

### `transition-colors` includes `outline-color`, and that has two consequences

Found in 7b while verifying the key bar's focus ring.

**One: a computed style read immediately after a state change is a reading of the
transition, not the value.** `getComputedStyle(chip).outlineColor` the instant
focus lands returns the *starting* colour — `currentColor`, i.e. the chip's text —
and settles on `--thrive-primary` 120ms later. It nearly bought a permanent change
to a class string justified by a comment stating a wrong measurement. **Wait past
the longest transition on an element before reading a computed style.** In
FINDINGS.

**Two: every focusable element carrying `transition-colors` has a focus ring that
FADES IN.** Minor, and `Button.svelte` already avoids it by enumerating
`transition-[background-color,color,border-color,opacity]` rather than reaching for
the shorthand — an enumeration now known to be load-bearing rather than fussy. Not
swept repo-wide; recorded so the next person choosing between the two knows what
the shorthand includes.

### The one responsive token

`--thrive-topbar-height` is **56px on mobile, 48px above `lg`**, overridden in a
media query on the raw token rather than by a class. `SideRail` draws its brand
band at `h-topbar`, so the rail's edge and the bar's edge continue one line — one
token means they cannot fall out of step at the breakpoint. `@theme inline` is
what makes it work: the utility inlines the `var()` expression instead of
resolving it once.

### `/swatch`

Renders every token, both border weights, the brand values with their PMS
numbers, the yellow constraint shown legible-on-navy beside decorative-on-cream,
and the two-face rule as a table of worked pairs. Throwaway; delete before
Release 1.

**It does not show the popover, the arrival ring, the dialog, or anything the
calendar added, and that is a decision** (owner, 2026-08-21): it is slated for
deletion, so it is not worth the time. Note it therefore did **not** need updating
for the chroma pass — it reads the tokens.

---
## 7. Dates: the rule the framework no longer enforces

**Components never see a raw timestamp.** Dates are classified and formatted on
the server inside `load` functions; components receive pre-formatted strings.

Full statement in `CONVENTIONS.md`. The short version:

- Read the clock in a `load` function. **Once.** Home's `+page.server.ts` calls
  `new Date()` a single time and every classification measures against it — two
  calls are two answers, and a task classified against 11:59:59 while the next
  line reads 12:00:00 is somehow both today and overdue. The calendar's load does
  the same and takes **three** values off that one instant: `todayKey`,
  `nowMinutes` and `nowISO`.
- **`describeDue(iso, now)` stays pure and keeps its `now` parameter.** That
  parameter is what makes the narrowed exception possible.
- **The narrowed exception:** anything the student can edit gets `nowISO` as a
  prop and re-runs the pure `describeDue` against it. The server still decides
  what "now" is; only the recomputation moved.
- **`dayKeyOf(value: Date | string)`** is the only place a local day key is built.
- **The week window is a date question and is answered on the server.** Each
  `EventRowData` carries a `thisWeek` boolean, not an ISO string the client
  compares — see §13.

**Nothing enforces this, and that is the point of writing it down.** In Next the
`"use client"` boundary enforced it at compile time. SvelteKit has no such wall:
a component can `import { describeDue }` and call it with no `now`, and the
default parameter is `new Date()`, so it compiles, renders something plausible,
and is wrong in another timezone. **Review is the enforcement.**

### The sanctioned client reads — and the calendar DECLINED one

1. **`nowMinutes()`** in `calendarSources.ts` — minutes past midnight. **Still
   has no caller**, through three calendar phases. It was written for the "next up"
   line and the calendar reads the server's clock instead, via `nowMinutesAt(now)`
   in `buildSchedule.ts`.

   **Why it was declined.** In Next, `CalendarView` was a `"use client"` component,
   so its memo could only ever run in a browser. The Svelte component renders on
   the SERVER first, so a `$derived` calling `nowMinutes()` would run during SSR:
   the server would paint one "next up" row and one ringed square, and the browser
   would silently replace both a beat after hydration. That is the quiet drift this
   whole rule is about. The value freezes at page load either way, so the client
   read costs a visible flip and buys nothing.

   Kept on the list for a caller that genuinely runs only in a handler.
2. **`matchesWide()`** in the floating-panel geometry — listed, and **not ported
   yet**; the floating panels are a later phase. Note 7b did NOT become its first
   consumer: see the viewport rule below.
3. **`TaskNotes`' autofocus gate** — `matchMedia('(hover: hover)')`, added in 6b.
   Opening the note panel is an explicit request to write, so focus lands in the
   field, but only where a keyboard will not cover the screen.

**Phases 8 and 9 added none.** `$lib/availability` takes no clock and, after the
chip strip came back, takes no "today" either — the published set IS the window, so
there is nothing to compare a day against. Phase 9's is the stronger result: `/ask` renders a
timestamp on every message and every rail entry, and **`ConversationView` carries
no ISO field at all** — there is not a timestamp available to a component that
wanted to format one. `ask.spec.ts` asserts that absence. Where a phase can reach
that shape it should, because it is a property rather than a discipline.

**7c added a fourth, and it is a clock read of a different kind.** `downloadIcs`
in `$lib/ics` reads `new Date()` for the `.ics` file's `DTSTAMP` — "when this file
was made". It is inside a click handler, it can never run on the server (there is
no `document` there, so a server call throws rather than producing a wrong file),
and **the pure builder takes the instant as an argument** precisely so the whole
thing stays testable without faking a global. The Next version read the clock
inside `buildIcs`, which is what made it neither.

**Read (3) against the deleted one, because they look identical and are not.**
`hoverIntent` read `(hover: hover)` to gate hover-to-*reveal*, which is CSS —
Tailwind's `hover:` utilities compile to that media query with no JavaScript
needing an opinion. `TaskNotes` decides whether to move **focus**, and there is no
CSS form of that to prefer. That is the whole test: *could CSS have done this?*

**A `Date.now()` used as an id nonce is not a clock read** in the sense this rule
is about. `quickList.ts`, `taskBoard.ts`'s `mintTaskId` and `calendarAdd.ts`'s
`own-${Date.now()}` all use one; none is ever parsed back into a day. A nonce is
not a date.

**Phase 9's chat composer does not even need a nonce.** Its ids key an `{#each}`
for the lifetime of one tab, nothing stores them and nothing reads them back, so
it uses a plain incrementing counter. Reaching for `Date.now()` there would have
been the weaker choice for the same reason: it invites a reader to think the value
means something.

### A viewport question that CSS can answer belongs in CSS

7b is where the hover rule was first tested on something other than hover, and it
held.

The week-to-agenda fallback (§14) is **two media-gated wrappers**, not a
`matchMedia` read. Three reasons, in order of weight: CSS has an exact equivalent
so the JS form buys nothing; a `matchMedia` read has to GUESS during SSR, so one
width of student watches the wrong view paint and be replaced after hydration; and
the cost is only that both subtrees build, which is cheap and keeps the hidden one
out of the accessibility tree via `display: none`.

**Pick the breakpoint by measuring, not by naming a size.** 40rem was built first
because that is the number MIGRATION and the Next comment both use. Measured, it
gave 71px columns — correctly clamped and still not readable — so it moved to 48rem
and 89px. "Fits" and "is legible" are different bars. **And the knob is always the
breakpoint:** a min-width would put back the horizontal scroll the fallback exists
to remove, which is what the source did.

### The accepted client-side formats

Locale-formatting differences, never date drift. Every one of these formats a day
key already built from local parts.

| Where | Why it cannot move to the server |
|---|---|
| The calendar's day heading | The day is chosen in the browser |
| The agenda's group headings | The range is walked client-side |
| `taskToItem` / `todoToItem`'s `timeLabel` | Their source rows are `localStorage`-only |
| `MiniCalendar`'s month label and each day cell's accessible date (7a) | The grid pages to ANY month with no round trip — the whole point of keeping classes as weekday rules — so there is no finite set of months a `load` could pre-format |
| `WeekView`'s weekday abbreviations (7b) | Same: the week is chosen client-side |
| The agenda's per-row date (7b) | Same: the thirty-day range is walked client-side |
| `customEventToItem`'s `timeLabel` | A custom event is `localStorage`-only, and it stores a wall clock rather than an instant |
| `MyDayPane`'s day heading | The clickable month can point that pane at ANY day in any month it pages to, so the set really is unbounded |

**`BookingPanel` was briefly on this list and came off.** While a month grid was
the day picker it formatted its own `dayLabel`; the chip strip carries every day's
finished labels from the server, so the panel takes a PROP and formats nothing.

**Nothing from Phase 9 is on this list at all.** `/ask` formats every one of its
dates on the server, including the "Today" / "Yesterday" relative labels, because
the day a conversation was last touched is a fact the server can decide once —
and `ConversationView` carries no ISO field, so there is not a timestamp available
to a component that wanted one. `ask.spec.ts` asserts the absence.

### `describeDue` has four states, not three

`DueDescriptor` is a **discriminated union**: `overdue | today | upcoming` plus
`unknown` for a date that will not parse, which carries `days: null` rather than
`NaN`. **`NaN` is a `number` to the type system** and flows silently into
`a.days - b.days`; `null` does not typecheck there, so a caller must narrow.

**`unknown` is deliberately NOT in `DueUrgency`** — "how urgent is it" has no
answer for a date that does not exist.

**Where an unknown row goes is decided** (2026-08-21): its own group, **first in
the list**, headed "Needs a date". Loud is correct, invisible is not — a deadline
that silently does not exist is worse than one shouting for attention, and it is
the only group a student can actually fix. It is not tinted `urgent`: that tone is
reserved for real deadlines, and a missing date is a data problem.

That ordering has two consequences, one found per phase. **In 6a:** four undated
rows fill the collapsed slice on their own and push the overdue task off screen;
`reveal.spec.ts` pins that path. **In 6b: making those rows visible made a latent
crash certain** — every date converter read `new Date(fromISO).getHours()`, which
is `NaN` for an unparseable date, and `Invalid Date.toISOString()` **throws a
RangeError**. All three converters now guard it via one `clockFrom` helper.

**The lesson generalises and is in FINDINGS:** when you make a previously
invisible state visible, audit every path that state can now reach.

### The timezone sweep is part of the definition of green

Seven zones from UTC+14 to UTC−11, including Australia/Lord_Howe's 30-minute DST
offset. **Run it after touching anything date-shaped**, and it has now caught two
real failures.

The second, in 7a, is the instructive one. `reveal.spec.ts` had `NOW` as a `Z`
instant with `Z` due dates beside it — the exact shape TESTING.md forbids two
paragraphs above the sweep command. `tsk-today` at `2026-08-21T23:00:00Z` is
already *tomorrow* anywhere east of UTC+2, so the "every overdue and due-today task
stays reachable" property counted one row instead of two. Red in Asia/Tokyo,
Asia/Kathmandu and Australia/Lord_Howe; green in the other four including both
extremes.

**The bug was the FIXTURE, not `describeDue`.** A task due at 23:00 local on the
21st really is due today. Reaching for the classifier would have broken correct
behaviour to make a wrong test pass. And the file had never been swept: TESTING.md
claimed the suite was green in all seven zones and it was not, because that line
was written before that test was. **A verification claim decays exactly like a
comment does.**

**7c's date-shaped additions were swept and are green.** `calendarAdd.spec.ts`
asserts local parts rather than ISO strings for exactly this reason — comparing an
ISO string would pin the runner's timezone instead of the behaviour.

---

## 8. The persistence layer

`frontend/src/lib/overrideStore.svelte.ts` is the one mechanism. 14
`localStorage` keys sit on it, plus `taskNotes` and `toast`.

**This is browser state, and a different thing from the three server-side mock
stores in §12.** Same word, opposite properties: this one is per-student and
survives a restart; those are shared by everyone and do not.

**And it is the layer that runs out first.** Everything persisted so far is one
student's private view of their own data, which is exactly what `localStorage` is
for.

**Phase 9 is where it ran out, and the answer was not to stretch it.** Saved chat
history is too large, grows without bound, and — the deciding argument — a student
opening THRIVE on a second laptop would find an empty history *indistinguishable
from never having asked anything*. A history that is complete on one machine and
empty on another is not a smaller feature, it is a misleading one. So conversations
are provider data from the start (§12), and a message sent before the backend
exists lives in component state that is gone on navigation, with the page saying so
BEFORE anything is typed.

`check:interaction` asserts sending writes **no** `localStorage` key. That
assertion is what stops the constraint eroding, because eroding it would be one
convenient line.

Group Projects, still queued in §18, is the same wall for a different reason:
shared between people by definition.

### Four properties that must survive

1. **Overrides keyed by id, never the whole truth.** `undefined` means "never
   touched, use the source value". A bare set of done-ids cannot express *"I
   unticked something that ships as done"*.
2. **Empty on the server, real after mount.**
3. **Corrupt input cannot take the page down.**
4. **A write matching the source value forgets the override.**

All four pinned by tests. **Hydration is one explicit `hydrateStores()`** in the
root `+layout.svelte` inside `$effect`, and nowhere else. Storage presence, not
`$app/environment`, decides browser-vs-server — which keeps the whole layer
testable in Node with no jsdom.

**Property 2 is visible on the calendar and is correct there.** `mergedSchedule`
reads nine stores, all empty until `hydrateStores()` runs, so the server and the
first client render both show "no personal items" and the student's own tasks,
to-dos and custom events land on the render after mount. A saved filter appearing
a beat after load is the same property and is expected.

### Resolve overrides ONCE per page, not once per consumer

Home has two things reading the same task list: the stat pills and the Tasks card.
`+page.svelte` calls `resolveRows` and hands the same array to both. If the card
resolved its own, moving a due date would restyle the list while the coral pill
above it went on counting the server's stale `due.urgency`.

**The calendar's form of the same rule is "one filter, applied once"** — see §14.

### Three key spaces, never merge them — and BOTH defects are now closed

| Space | Module | Keyed on |
|---|---|---|
| Task id | `userEdits.svelte.ts` (6 of its 7 stores) | the task's own id |
| Calendar item id | `calendarItems.ts` | `asg-12`, `apt-3`, `task-7`, `todo-x`, `custom-…`, `evt-evt-3-1` |
| Raw `Event.id` | `ignoredEvents.ts` **and `thrive:event-joins`** | `evt-3-1` — **stored verbatim** |

**Still three spaces, not four — through two more phases.** The test for whether a
new store needs a new one is: *is this a fact about the EVENT, or about the ROW?* A
join and an ignore are facts about an event. A label and an urgent flag are facts
about a row — which is what lets a student flag an assignment or label a booked
appointment, neither of which they own and neither of which has an event behind it
at all.

**Phases 8 and 9 both introduced ids and neither introduced a key space**, which
is worth being explicit about because the count has bitten this project twice:

- **Slot ids and appointment ids** (`slot-adv-gsa-0-0`, `apt-001`) live in the
  server-side mock store, not in `localStorage`. Nothing browser-side is keyed by
  them. `Appointment.slotId` is a server-to-server reference.
- **Conversation and message ids** (`conv-001`, `conv-001-m1`) are provider data.
  There is no conversation store of any kind.
- **The chat composer's ids** are a counter scoped to one component instance.

The rule the count actually tracks is *persisted browser key spaces*, and both
phases added zero stores.

**Defect one, fixed in 7a: the ignore store.** `eventIdOf` strips exactly one
leading `evt-`. Given a calendar item id (`evt-evt-3-1`) that recovers the raw id.
Given a RAW id — which begins with `evt-` too — it *mangles* it to `3-1`. And **the
store was normalising its own arguments**, so Home's write to `evt-3-1` landed
under `3-1` while the calendar's landed under `evt-3-1`. Each surface
self-consistent, neither able to see the other.

**The fix is that the store normalises NOTHING it is handed.** It keys on precisely
the string given, and the one surface holding a prefixed id — the calendar — calls
`eventIdOf` once at its own boundary. `filterSchedule` was always in the raw space,
so **Home was the broken side**, and no Home component changed.

**Defect two, fixed in 7c: `thrive:event-joins`.** MIGRATION §9 defect 13 — the
same bug, in a second store, and invisible because the store had exactly one
consumer, and one consumer is self-consistent under any key space at all.

7c built that consumer and decided it with the consumer on screen:

- **One `DayEventsSection` row offers "count me in" and "ignore" side by side.**
  Under the old shape that component holds two ids for one event and has to
  remember which control takes which — not a rhyme with the 7a defect, the same
  arrangement.
- **Home already held the other id, and said so in a comment.** `EventRow`'s "count
  me in" had been inert since 6a *because this key space was unsettled*.
- **Nothing argued the other way.**

`calendarEvents.ts` is now the calendar's one boundary: `dayEventRows` calls
`eventIdOf` once and hands the raw id back with each row, for **both** stores.

**`eventIdOf`'s doc comment used to claim "passing a raw id through twice is
safe".** That false sentence is why the bug was written twice, and it is gone.

**Old keys are inert, not migrated** (owner, both times). An event ignored or
joined before the fix is asked about once more. Absence means "never touched" in
both stores, so a stale key is harmless rather than corrupt, and a migration shim
whose only input is a browser nobody can inspect is worse than the one-time
reappearance.

**The double prefix itself is deliberate and stays.** Every calendar item id names
its stream, and events are the one stream whose source ids share that prefix.
Dropping it would make the space non-uniform — `asg-12`, `apt-3`, `task-7`, then a
bare `evt-3-1` — and the label and urgent stores are keyed on that space.

**Student-created task ids are prefixed `own-`** so they cannot collide with a
fixture's. `removeAddedTask` clears the five sibling overrides too, and
`deleteCustomEvent` does the same for a custom event's label and urgent.

### How to test a key space, because the obvious way does not work

**Pin the STORED KEY. Never round-trip.**

A store that mangles on write and mangles identically on read is perfectly
self-consistent about a key nothing else uses. That is what 7a's bug was, and two
round-trip tests passed the whole time it was broken.

So a key-space test must not share a transformation with the code:

- read the string straight out of the fake `localStorage` and compare it to a
  hard-coded literal, **or**
- write through one surface's real path and read through the other's, with the
  reading side's id hard-coded rather than derived.

Then break it on purpose and count the reds. `calendarEvents.spec.ts` goes **7 red**
with `eventId = item.id` reinstated.

**And a unit test still cannot prove the two SURFACES share it**, because it
renders neither. That half is `check:interaction`: join on the calendar, navigate
to Home, and the same event says so — nothing in between but a page load and
`localStorage`.

### What is deliberately NOT persisted

Card collapse state, and the reveal channel that can drive it (§13). Also: the
drag in progress, the open editor, the note draft before it commits, the live-region
sentence, **the detail dialog's open item and its delete-confirmation step**, and
the calendar's `selectedKey` / `monthKey` — a selected day is a momentary place,
not a preference. **The calendar's FILTER is persisted**, through `calendarPrefs`,
because a filter that resets on every navigation is a filter nobody uses twice.

### `.svelte.ts` is not decoration

Svelte only processes runes in `.svelte.js` / `.svelte.ts`. A plain `.ts` with
`$state` is **silently inert**. Six files carry the suffix: `overrideStore`,
`userEdits`, `taskNotes`, `toast`, `ignoreUndo`, `reveal`.

**And the suffix is a claim, so it has to be true in the other direction too.**
`arrive.ts` is DOM code with no runes and is a plain `.ts` for exactly that reason.
Three calendar phases added eight pure modules and **no seventh rune file** —
`ics.ts`, `calendarEvents.ts` and `calendarAdd.ts` are all plain `.ts`, and
`actions/focusTrap.ts` is DOM code like `arrive.ts`.

**Still six rune files after Phases 8 and 9.** `availability.ts`,
`appointmentsView.ts` and `ask.ts` are all plain `.ts` and hold no state at all —
the booking surface's state lives in `BookingArea`, and Ask THRIVE's lives in the
URL. A surface whose state is a route is a surface with no store to declare.

---

## 9. React-isms deliberately dropped

Each because the constraint behind it does not exist in Svelte. Recorded so
nobody reintroduces them thinking they were an oversight.

| Dropped | Why it existed in React |
|---|---|
| `useCalendarPrefs`'s `useMemo` | A fresh object per render busted every downstream memo |
| The frozen shared `EMPTY` | `getServerSnapshot()` had to return the *same object* |
| `useMergedSchedule`'s 9-dependency `useMemo` | Hooks cannot know their own dependencies |
| `useCallback` on `isDone` / `resolve` | Referential stability for memoizing callers |
| `useEffect` timer cleanup | A module singleton has no unmount |
| The `use*` prefix on every reader | Signalled call-order rules that do not apply |
| `useFloatingGeometry`'s ref-into-a-hook | A React Compiler render-phase rule; `bind:this` removes it |
| `useState` + `useRef` for the More sheet | Moot — the sheet is gone (§11) |
| `useTaskBoard`'s two `useMemo`s and three `useCallback`s | Deriveds recompute on read |
| `TaskNotes`' `latest` ref + syncing `useEffect` | `onDestroy` reads the draft directly |
| `MiniCalendar`'s `gridRef` + `requestAnimationFrame` | A ref to query the grid, and a frame's guess at when the month had re-rendered. `bind:this` plus `await tick()` is the flush, not a guess |
| `CalendarView`'s five `useMemo`s | Same as above: filter, labels, next-up, squares, day groups all recompute on read |
| **`ItemDetail`'s two `useEffect`s and a `useRef`** | A ref for the close button, an effect to focus it on mount, and an effect adding a `window` keydown listener keyed on `onClose`. All three are **one action** here — `focusTrap` plus `escapeKey`, whose lifetimes ARE the element's |
| **`AddItemForm`'s three `useId()`s** | Only one add form is ever mounted, so plain ids match the repo's rule: per-instance ids for per-instance components, plain ones for singletons |

**Two collapses were requested and made:** `localDayKey(iso)` folded into
`dayKeyOf(value: Date | string)`, and `CalendarView`'s
`view === "agenda" ? <Agenda/> : <dayPanel/>` became a **snippet** rendered by two
branches — the ternary read as "agenda is the odd one out" and hid that the day
panel is shared by month and week.

**One hook was split rather than translated.** `useTaskBoard` did resolution,
grouping, counting and mutation in one place; here grouping and counting are
`homeGroups.ts` (6a) and resolution plus the date arithmetic are `taskBoard.ts`
(6b).

**Hooks that became module singletons:** `useTaskToggle` → `taskToggle`,
`useIgnoreEvents` → `ignoreEvents`. One undo slot app-wide rather than one per
calling component. **The reveal channel is deliberately NOT one** — see §13.

**`onDestroy` is not a `useEffect` teardown, and 6b needed the difference.**
`TaskNotes` commits its draft on destroy; written as an `$effect` returning a
cleanup it would commit on every keystroke.

### A prop is a getter, and 7c learned that the hard way

**In Svelte 5 a prop is a getter over the parent's state, so its declared type has
a lifetime.** `ItemDetail` declares `item: ScheduleItem`, and that is true of the
VALUE. Closing writes `null` into `CalendarView.detail`; the `{#if}` around the
component tears the subtree down a tick later. In between, the getter returns null
while the component's handlers still exist.

It threw, in production, on an ordinary dismissal: closing with focus in the label
field fired the input's `onblur` **during teardown**, `commitLabel` read `item.id`,
and the page logged `Cannot read properties of null (reading 'id')`.

**The remedy is to latch the value at mount** — `const row = untrack(() => item)`
— which fixes the whole class rather than one handler, and states the assumption
out loud. It is only correct when the prop genuinely cannot change for the
instance's lifetime, and that has to be arguable: here `detail` is a snapshot, the
dialog is modal so nothing can swap the row underneath it, and the two fields that
CAN change while it is open are read from their stores instead. Where a prop really
does change, guard the handler instead.

Same family as 6b's `derived_inert` — a `dragend` on a row a drop destroyed. Both
are "the DOM outlives the state for one tick".

---

## 10. The shell

`frontend/src/lib/components/shell/` — `AppShell`, `SideRail`, `TopBar`,
`BottomNav`.

- **`nav.ts` is the single source** for the rail and the bottom bar, and it is a
  TREE now: the `/ask` item carries `children`. `flattenNav` is what keeps it
  single — `allNav` and `isBuiltRoute` are DERIVED from the tree, so a child
  cannot exist in the rail and be missing from the lookup, because there is no
  second list to add it to. `PagePlaceholder` resolves its own `href` against
  `allNav` and **throws** when there is no match.
- **The top bar is 48px above `lg`, 56px below.** The CONTROLS change size — 44px
  touch, 36px pointer — and the bar's height follows from them. WCAG 2.5.5 asks
  44px of a touch target and 2.5.8 asks 24px of a pointer one. The stat pills, 6b's
  editor buttons, 7b's view switcher and key-bar chips, and 7c's register and
  dialog controls all follow the same pair.
- **`--thrive-page-gutter-bottom`** is the page's bottom breathing room, used
  twice: on mobile added to the bottom nav's height, and above `lg` it is the whole
  padding.
- **Icons are component references held as values.** Not `<svelte:component>`,
  deprecated in Svelte 5.
- **A nav item with `children` is a DISCLOSURE**, and the rail owes it the whole
  contract: the link navigates, a SEPARATE button carries `aria-expanded` and
  `aria-controls`, collapsing REMOVES the children from the DOM rather than hiding
  them, the group opens itself when a child is current, and `aria-current` lands on
  the child only. A parent whose child is current takes full ink rather than the
  solid fill — prefix matching would otherwise paint two rows as "here".
- **Accessibility:** skip link, `main` landmark with `tabindex="-1"`,
  `aria-current="page"` on the active item, and **one `nav` landmark per purpose**
  — see the note below.
- **`Toast` is mounted here**, once, for every route.

### The `nav` landmark rule, as it actually settled

The old statement — "exactly one `nav` landmark in the a11y tree at a time" — did
not survive Ask THRIVE, and the honest version is more useful.

`SideRail` and `BottomNav` both carry `aria-label="Primary"`. That is CORRECT:
whichever is displayed IS the primary navigation, and they are never displayed
together (`hidden lg:flex` against `lg:hidden`). But **both are in the DOM at every
width**, which is not the same thing — `display: none` removes an element from the
accessibility tree and not from `querySelectorAll`. A gate scoping by that label
matched both and counted one `aria-current` twice, which is why they now carry
`data-nav="rail"` / `data-nav="bottom"` hooks.

`/ask` has up to three `nav` landmarks, each named and each with one purpose: the
primary rail, the destination band (`lg:hidden`, for widths with no rail), and the
conversation history. Never two with the same name in the tree at once.

**The second rail Ask THRIVE was expected to want** turned out to be two separate
questions. The destinations are navigation and moved into the nav rail as the
disclosure group above; the page's own rail holds the conversation history and
nothing else.

### The app-wide toast

`toast.svelte.ts` shipped in Phase 3b with six tests and **no consumer**. 6b's
copy-to-quick-list was the first caller and would have been the worst possible one
to leave unrendered: the floating quick list is feature-flagged off, so the copy
had no visible destination either.

`role="status"` rather than `alert`: a confirmation is not urgent and must not
interrupt a screen reader. The region is **mounted always** and only its text
changes, because a live region created and populated in the same tick announces
unreliably. `pointer-events-none` so a confirmation can never swallow a press.

**7c gave it three live callers, so it is no longer flag-dependent.** Adding an
item ("added to your to-do list" — naming WHICH list, because that is the whole
point of the kind picker), deleting a custom event, and ignoring an event from the
calendar.

### The three actions

`frontend/src/lib/actions/` — `escapeKey`, `clickOutside`, and **`focusTrap`**
(7c). Svelte actions rather than translated `useEffect`s, and the shared shape is
that **the listener's lifetime is the element's**: put one inside an `{#if open}`
and it exists exactly when the thing it dismisses does.

Callers: `StatPopover` and `DueDateEditor` for the first two, and **`ItemDetail`
for all three** — the third caller 7a and 7b predicted and did not produce.

`clickOutside` takes `alsoInside` because a disclosure's own trigger is not inside
its panel but *is* inside its widget. Without it, pressing the trigger to close
fires the dismissal, the panel unmounts, and the trigger's own click reopens it.

**`focusTrap` is one action for three obligations, and that is deliberate.** Move
focus in, keep it in, put it back. They are one contract, and the first and third
are two halves of a single fact — the element focused at mount is the element that
gets it back at destroy. Split across two actions, that fact would live in neither.

It does **not** close anything and does **not** decide what a dialog is: Escape,
an outside press, `aria-modal` and the scrim are separate decisions a caller can
make differently, and a non-dismissible dialog is a real thing. It also does not
make the rest of the document `inert`, which would mean an action reaching outside
its own node.

**Its focusable set is queried LIVE on every Tab**, not captured at mount, because
`ItemDetail`'s delete control replaces itself with a two-button confirmation while
the trap is up. A list captured at mount would hand Tab to a button that no longer
exists.

**The same shape, one level up.** `TasksCard` clears its drag state from a
`document` `dragend` listener inside an `$effect` keyed on `drag !== null`. Not an
action, because no element's lifetime matches — the drag outlives any one row.

**`hoverIntent` existed and was deleted**, same day. See §16.

### Feature flags

`FEATURES.floatingTodo` and `FEATURES.floatingAssistant`, both `false`. Mount
points exist in `AppShell`, gated.

**`floatingTodo` gates a second thing: the task row's copy-to-list control.** The
quick list is the only surface where a copied item is visible, so with the flag off
the copy succeeded, persisted, and showed the student nothing.

**A flag that gates a destination should gate the routes INTO it.** That is the
generalisable form.

**The calendar sharpens a note here twice over.** The quick list's *items* surface
somewhere the flag does not gate: the agenda renders undated to-dos, which are
`QuickItem`s, and they are tickable there. **And 7c's add form can now CREATE
one** — "to-do" is one of its three kinds and it writes `thrive:quicklist`. That is
deliberate on both counts — the agenda is the only view that can carry undated
to-dos and they would otherwise be invisible forever — but it means the store has
two visible consumers and a writer while its panel does not exist.

---

## 11. Routes and navigation

13 routes plus two nested under `/ask`. **Four destinations are in the
navigation:** Home, Calendar, Appointments, Ask THRIVE — in that order. **All four
are built**, which has not been true before: every visible navigation item now
leads to a real page.

Ask THRIVE's three subjects are `children` of its nav item — real routes
(`/ask/resources`, `/ask/courses`, `/ask/career`) with their own hrefs, labels,
icons and descriptions, rendered as a rail disclosure. `/ask` itself redirects to
the first of them.

Nine of the previous eleven destinations were placeholders, and a nav that is
four-fifths stubs reads as broken rather than unfinished.

**A fifth nav item is coming.** Group Projects (§18) will be the first addition
since the trim to four — and the first time the four-slot bottom bar has to hold
five things.

### Parked, not deleted

`/classes`, `/syllabi`, `/assignments`, `/degree`, `/events`, `/career`,
`/resources` and **`/settings`** live in `parkedNav` — a list **no surface
renders**. The routes, files, icons and descriptions are intact and reachable by
URL; the only thing removed is the way in.

**Why a separate list rather than a `hidden` flag:** a flag needs every surface to
remember to filter on it, and the failure mode of forgetting is a parked item
silently reappearing in one place.

**`allNav`** is the lookup list — visible plus parked. `PagePlaceholder` resolves
against it, so parking a route does not start it throwing.

**Settings is parked and stays parked** (confirmed 2026-08-21). It was also the
reason the mobile **More sheet** could go.

**Two parked routes share a NAME with an Ask THRIVE destination and are not the
same thing.** `/resources` and `/career` are parked stubs; `/ask/resources` and
`/ask/career` are built chat surfaces. The overlap is a naming collision to be aware
of, not an absorption — nothing about the parked routes changed.

### A card links out only when its destination is built

`isBuiltRoute(href)` asks `primaryNav`, and `SectionCard` renders its "View all"
only when the answer is yes. **`primaryNav` membership IS the definition** of a
real destination, so moving a route out of `parkedNav` restores every card's link
with no further edit.

Decided in `SectionCard` rather than per card: four cards link out and three
pointed at parked routes, so the alternative was four places to forget.

**Which cards lost their link:** Tasks (`/assignments`), My Classes (`/classes`),
Upcoming Events (`/events`). Today's classes keeps `/calendar` — and that link now
lands on a real and complete page.

**`isBuiltRoute` is flattened**, so a nested destination counts as built. A card
linking to `/ask/career` keeps its link; the route being nested is not a reason to
withhold one.

**`isKnownRoute` is the companion**, separating a parked route from a mistyped one.
`SectionCard` warns in development on an href in neither list. A warning and not a
throw: taking Home down over a "View all" would be worse than the missing link.

**`/classes` will not be built, and its card stays link-less indefinitely**
(owner, settled — do not revisit). The card IS the feature.

**`/assignments` is parked and is the next real consumer of a 6b component.** It
renders the same `TaskRow` with no `reorder` prop, and **owes that row a
`role="list"` container**.

`pageTitle()` in `lib/title.ts` reproduces Next's `"%s · THRIVE"` template.

---

## 12. The data layer

`frontend/src/lib/data/` — 20 files. **This is the seam.** `BACKEND.md` is the
contract written out for whoever implements it.

**Built against the same mock fixtures the Next app uses.** No HTTP client, no
API layer, no Django integration. Django replaces the provider *bodies* later;
the signatures are the contract and do not move.

### The public surface

`data/index.ts` re-exports exactly three modules: `types`, `providers` (**27**
functions + `SlotUnavailableError`), and `labels`. **`mock/` and `latency` are
private** — a component that needs something from either has found a gap in the
provider surface. Widen the surface, do not reach through it.

### Four properties, each pinned by a test

1. **Every provider returns a `Promise`.**
2. **Every provider returns copies.** *The copies are shallow*, as in the
   prototype — see §18.
3. **Deterministic generation. Never `Math.random()`**, which desynchronises
   server from client. A test scans the whole directory.
4. **Fixtures dated relative to now**, so a demo never looks stale.

### The three module-level stores

`mock/appointments.ts`, `mock/requests.ts`, `mock/resume.ts`. Lazy seeding,
because their dates are relative to "now" and module load may be hours earlier.

**The id generators count independently of the seeds.** They work only because
somebody numbered the request seed `req-000` by hand and set the resume counter to
4. Commented at the generator, and pinned by a test.

### Five providers have a calendar consumer

`buildScheduleData()` was the gating unported piece from Phase 2 to 7a. It reads
**`getCourses`, `getAssignments`, `getEvents`, `getMyAppointments`, `getAdvisors`**
in one `Promise.all` — see §14 for what it does with them.

### Four MIGRATION §9 defects built correctly rather than reproduced

| # | Defect | What this repo does |
|---|---|---|
| 8 | `cancelAppointment` released by matching start time | `Appointment.slotId`; one exact delete |
| 11 | A page imported a label map from `lib/data/mock/requests` | Both maps in `data/labels.ts`, public side |
| 15 | Four providers returned fixtures by reference | All 27 return copies |
| 9 | `expectedCompletion` hardcoded vs a derived finish term | Field dropped; read `expectedFinishTerm` |

### The fixture student

`mock/student.ts`. One MSBA student · **17 month** track · goal "Data Scientist" ·
Fall 2026 · `programStart: 2026-08-03` · standing `onTrack`. `programStart` is a
**start** date; the finish term and the percentage are both derived.

Two advisors, and the pair matters rather than the people: **a graduate student
advisor** (an on-campus room in Rady) and **a career coach** (the CMC, or Zoom). One
in-person-only and one with a remote mode, which is what the booking panel's mode
filter exists to distinguish. Their names are fixture data and live in
`mock/appointments.ts`.

**There is exactly one student, and Group Projects is the first thing that breaks
that assumption** — see §18.

### The fixture's shape, measured

**10 tasks** (8 open, 2 done — 1 overdue, 2 due today, 5 upcoming), and **159
upcoming events, 21 of them inside seven days**, generated 2–4 per day across a
rolling horizon. That 21-against-4 is what forced the events card decision in §13.

**Event ids are `` `evt-${dayOffset}-${i}` `` — already `evt-`-prefixed**, which is
the root of both key-space defects in §8. Verified at `mock/events.ts:287`.

**The eight open tasks are why the collapse matters and why one gate check can run
at all.** Four are shown collapsed, so `check:interaction` can tick the last of the
eight, collapse the card, and undo into a row that is genuinely not rendered.

**No fixture task has an unparseable due date**, which is why the crash in §7
survived to be found by reading rather than by using the app. **And no fixture item
carries a label**, which is why the calendar key's labels dimension had to be
exercised by seeding the store by hand (§14).

**The month the calendar opens on has 36 days with something on it and 14 with
events**, which is what makes 7c's day-figure gate non-vacuous — see §14.

---

## 13. Home

The dashboard, and the only editable surface besides the calendar.
`+page.server.ts` awaits **six providers in one `Promise.all`** and calls
`new Date()` once. Four cards in a **2×2 grid** at `lg`, one column below it.

**What is deliberately not computed on the server:** the three stat counts. They
have to see the student's persisted ticks, edits and ignores, which only exist in
the browser. What goes down is the classified rows and, on each event row, a
`thisWeek` flag: the data to count, not the count.

**`+page.svelte` resolves the task rows once**, for both consumers. See §8.

### The fit-on-one-screen behaviour

- **Desktop: a FIXED height per card body, scrolling inside.** Fixed, not
  `max-height` — with a maximum, a short card still *grows* when expanded, moving
  its grid row. Fixed means expanding can only ever scroll.
- **Mobile: no cap at all.** A nested scroll region inside a page that already
  scrolls eats the swipe meant for the page.
- **The state does not persist.** An expanded card is a momentary intent.
- **`contain: paint`** on the card body — load-bearing, see BUGS.md.

**Cap: `--thrive-card-body-cap: 18.75rem` (300px)**. Collapsed row COUNTS live in
`$lib/cardLayout`: **4** task rows, **2** course cards, **4** class rows,
`VISIBLE_EVENTS = 4`. **`COLLAPSED_TASK_ROWS` stays at 4** (owner, settled).

### Tasks is flat when collapsed, grouped when expanded

The one real design decision in 6a, and it came from measuring: the card carried
~190px of fixed furniture before its first row. So the progress bar moved into the
header band and the collapsed view shows a flat list of the next four things.
Headings come back on expand.

**6b inherited a consequence: reordering is offered only when EXPANDED.**
Collapsed, the rows are a flat slice spanning several groups, and sort keys are read
*per group* — so "move this up" across a group boundary would persist a key and
change nothing on screen.

### Task editing (6b)

| Component | Role |
|---|---|
| `TaskRow` | The row. Checkbox, title-as-label, chips, due chip, 44px controls, two disclosure panels |
| `UndoBar` | Fixed at the TOP of the list. Deliberately **not** a live region |
| `DueDateEditor` | The due chip as a button opening a native `<input type="date">` plus three shortcuts |
| `PriorityPicker` | Three radios, not a select. Deliberately uncoloured by its own value |
| `TaskNotes` | Draft local, committed on blur, on close, and on destroy — never per keystroke |
| `AddTaskForm` | Collapsed to one button. Title the only required field |

**A native date input rather than a hand-rolled calendar.** Keyboard-operable and
screen-reader-labelled for free, and on a phone it raises the platform's own picker.

**Three radios rather than a select**, because there are exactly three values.
**`AddTaskForm` keeps a native `<select>`** and that is not an inconsistency: on a
row, priority is one of three values being *changed* in a strip where all three
should be visible; in the form it is one of four fields being *filled*.

**Notes commit on blur, on close, and on destroy.** The third matters: ticking a
task elsewhere regroups the row and can unmount the panel mid-sentence. Escape
**closes without discarding** — the opposite of the title editor, because a title
has an original to restore to and prose does not.

**The title commits on blur too, which the Next source did not do.** That forced a
guard: `blur` fires *before* `click`, so pressing Cancel would have committed the
draft. Both halves are needed — a `pointerdown` flag for mouse, touch and
**Safari** (where clicking a button does not focus it, leaving `relatedTarget`
null), and a `relatedTarget` check for the keyboard.

**That Safari note came back in 7c**, one layer up: a pointer press does not
reliably leave focus on a button, so `ItemRow` focuses its details trigger before
opening the dialog, or `focusTrap` has nowhere to put focus back (§14).

**"Needs a date" accepts no drops**, enforced as a type:
`DatedGroupKey = Exclude<GroupKey, 'unknown'>`.

**No `justChanged` ring.** This app has ONE arrival treatment. A tick is answered
by the row striking through, moving to Done, the undo strip, and the live sentence.
The ring is spent on the **undo**.

**One live region, and the undo strip is not a second one.** The sentence is cleared
after 4s so the *same* move announced twice is announced the second time too.

### The row's structure, and defect 3 twice over

MIGRATION §9 defect 3 — "the worst thing in the app" — was every task title
wrapping to roughly one character per line at 375px. It had **two** causes and 6b
would have reintroduced the second.

**Cause 1, fixed in 6a:** a flex item's default `min-width: auto` refuses to shrink
below its longest word. **Cause 2, dormant because a read-only row had no
controls:** several 44px buttons beside the title is ~220px against a 343px card,
so the controls **wrap to their own line below `sm`**.

**And a third thing, exposed only by adding the due chip.** `flex-1` on a `min-w-0`
title means the TITLE gives way, not the chips. Measured at 375px mid-build the
title box was **90px**. The title now takes a line of its own.

Measured after: **303px and one line at 375px, 339–385px at 1512px.**

**The row is a `<div>`, not a `<label>`.** It holds several controls and a label
wrapping all of them would make pressing the note button tick the task off. The
**title** is the checkbox's label instead. **The calendar's `ItemRow` follows the
same rule for the same reason**, and 7c's details button is why it matters there
too.

**The control strip is right-anchored (`ms-auto`).** The invariant: a conditional
control appears and disappears at the strip's leading edge, and nothing already on
screen moves. **`ItemRow`'s details control follows it** — last in the strip, so
adding it moved nothing.

**The row renders `role="listitem"`, and every caller owes it a `role="list"`
container.**

### The stat pill popovers

Each pill opens a popover listing the actual items behind its number, clickable and
jumping to the row.

**Click, and only click.** Hover-to-open was built, gated, tried, and **rejected**:
three pills in one row meant a cursor crossing it opened and closed panels nobody
asked for.

**A count of zero is not a control.** No button, no `aria-expanded`. It keeps
`min-h-11` so a row of pills is never two heights.

**The count and the list are one expression** — each pill's number is
`items.length` of the list it opens.

**A list, not a menu.** `role="menu"` brings a single tab stop and Tab-to-exit,
right for a command menu and wrong for jump targets.

**Dismissal has one focus rule:** restore focus to the pill **if and only if** focus
is currently inside the panel. Choosing an item is the named exception.

**21 items is a long popover** and it scrolls at `max-h-60`.

### Upcoming Events, and the join control that is finally live

The events pill counts events *this week* — 21 in the fixture — while the card showed
four *upcoming*, so seventeen popover items had no row to jump to.

The fix rests on both sets being **prefixes of the same list**.
`expandedEventLimit(collapsedLimit, weekCount)` returns `max` of the two, and a test
asserts the prefix property. The `max` is not decoration: on a quiet week the week
count is *shorter* than the collapsed slice.

**Filter FIRST, then slice** — ignored events are removed before the slice, which is
what makes the next event move up instead of leaving a gap.

**"Count me in" was inert from 6a until the 7c follow-on**, with a comment beside it
saying exactly why: the join store was keyed on the calendar item id, so a write
from Home would have landed under a key the calendar never reads. §8 settled that,
and the control is now real.

**It renders the calendar's shape exactly** — "You're in" states the fact, "Remove
from my list" is the way out, and a joined row says nothing was sent anywhere — and
the register vocabulary moved to `messages.common.events`, because two live surfaces
rendering the identical words for the identical act should not be two strings for a
translator to keep in step.

**An inert control is a dead affordance, and Home has none left.** Four have been
removed: "View all" pointing at a parked route, copy-to-list with nowhere to copy
to, "count me in", and **"Add to calendar"** — which downloads an `.ics` through
`icsFromEvent`, Home's own mapper. Nothing leaves the browser: the student imports
the file or does not.

**`icsFromEvent` is a SECOND mapper rather than a shared one**, and that is the
decision worth recording. An `Event` has a real `location` and a required `start`; a
`ScheduleItem` has a `detail` that means a location on an event row and a course
code on a task, and an OPTIONAL `startISO` because a recurring class is a weekday
rule. Collapsing them means widening one type or narrowing the other, and the
fallbacks differ. The one rule they DO share — no distinct end means a marker at the
start — is asserted on both, which is what stops them drifting.

### The reveal channel: the page owns the intent, the cards own their state

- **`$lib/reveal.ts`** is pure and tested. `planReveal(ids, limit, targetId)` is the
  one question a card asks. `found: false` is kept distinct from "found, and already
  visible".
- **`$lib/reveal.svelte.ts`** carries the request. A popover calls
  `reveal.request({ kind, id })` and knows nothing else. Nothing outside a card ever
  writes a card's state.

**The channel lives in page CONTEXT, not at module scope.** That is what keeps
"collapse resets on navigation" true because of where the channel lives rather than
because something remembers to reset it. This is the one place the module-singleton
pattern of §9 was rejected.

**The nonce is load-bearing.** Two clicks on the same item are two requests, and
with only a target in the slot the second write is `target === target` and Svelte
makes it a no-op — precisely the click a student makes when the first did not seem
to work.

**Each show-more control governs its OWN region.** Two controls claiming one region
is a promise to a screen reader that neither keeps.

**`RevealKind` is a closed union — `'task' | 'event'` — on purpose.** Nothing in
7a, 7b or 7c needed a third, and it was checked rather than assumed each time: the
calendar's "next up" line is a static sentence, and 7c's add form deliberately does
not jump to what it created (§14). A third member would force an id-space decision,
which is why the union is closed. **The calendar has still added no arrival caller
at all.**

### Arriving is one function, and it is the standard

**`arriveAtRow` in `$lib/arrive` is how ANYTHING moves a student to a row.** Never a
hand-rolled `scrollIntoView`. Two arrival treatments on one page would be worse than
either alone.

Asking and doing are separate modules: **`$lib/arrive`** is "I know which row",
**`$lib/reveal.svelte`** is "something else has to find it".

**Two callers, still:** a popover item, and 6b's undo.

**Not every focus move is an arrival**, and 7c added two more counter-examples to
the list. Navigation inside a widget (`StatPopover` between its items,
`MiniCalendar`'s arrow-key grid movement). Focus recovery onto a container after
the row it was on stopped existing (`UpcomingEvents` after an ignore). **And now
`focusTrap`'s two moves** — into a dialog on open, and back to the opener on close.
None of them is "here is the row you asked for", which is the only thing the mark
means.

`MiniCalendar` is the clearest case for the distinction: it moves focus on every
arrow press, and marking each one would turn a wayfinding cue into a cursor.

#### Why the mark exists

Focus moved and the row scrolled, which was correct and **completely invisible** —
everything on Home is on one page. The focus ring is not the answer: a pointer user
does not get one.

`arriveAtRow` focuses the row, scrolls it with `block: 'nearest'`, and marks it with
**`.thrive-arrived`** — an indigo ring, solid for most of a 1200ms beat then faded.

- **Indigo** because it is the reserved "you are here" colour.
- **An outline**, because it cannot move the layout, does not collide with the row's
  own priority wash, and follows the element's own `border-radius`.
- **The ring is a normal declaration and the animation only takes it away**, because
  the global reduced-motion block forces `animation-duration: 0.01ms !important` and
  a mark *painted* by a keyframe would vanish instantly.
- **Exactly one row is ever marked**, document-wide.
- **Arriving twice at the same row forces a reflow** between removal and re-add.
- **The mark is unconditional**, including for a row that needed no scrolling.

#### The one-tick question, settled in 6b

`arriveAtRow` awaits exactly **one** `tick()`. **One tick is enough — but the flush
count was the wrong question.**

Svelte's deriveds are **pull-based**: reading one after a state write recomputes it
synchronously. So `undoTick` unticks, READS the resulting list, asks `planReveal`,
expands the card if it must, and only then arrives.

> **Make every state change the row's existence depends on BEFORE you call
> `arriveAtRow`. Never leave one to an effect that has not run yet.**

**Measured both ways.** With the expansion in an effect instead, the hard case lands
nowhere and logs **zero console warnings**, because the gate drives the production
build where the dev-only warn is compiled out.

### Measured heights

Header block **375px → 266px** (6a density pass). Document **1392px → 1238px** (6a)
**→ 1218px** (6b). **Home fits a 1218px viewport whole**, not 1052px, and the
decision is **do not cut card rows**. **The phone is 3235px** — the join control
added ~46px per joined row and nothing else.

### Strings

**`$lib/messages` holds every user-facing string.** English only, no library. Nested
by surface, and **anything carrying a value is a function**, not a template
assembled at the call site.

6b added a `taskEditing` group of ~45 entries. The calendar phases added a
`calendar` group of ~90, with the same property: `countPart(count, singular,
plural)` hands a translation both word-forms so it can pluralise its own way, and
`dayLabel(date, items, today)` decides what a day cell says and in what order rather
than letting markup concatenate it.

**`common.events` is the one group that is not owned by a surface** (7c follow-on).
Home and the calendar render the same eight strings for the same act against the
same store; two copies was survivable while Home's controls were inert and stopped
being so the moment both were live.

**This is a standing rule, not a Home thing.** Every surface extracts its strings as
it is built, or Mandarin stops being possible.

---

## 14. The calendar

**The second built surface, the largest, and as of 7c COMPLETE.** `/calendar` —
14 components, ~2,850 lines, plus nine pure modules. 7a built the spine, 7b the
other two views and the filter, 7c the three editing surfaces.

### The load: one clock read, three values, and no merge

`routes/calendar/+page.server.ts` awaits `buildScheduleData()` and `getTasks()` in
one `Promise.all`, calls `new Date()` once, and returns `todayKey`, `nowMinutes` and
`nowISO` off that single instant.

**Tasks are fetched here and deliberately NOT merged here.** A task's due date can
be moved by the student and stored only in `localStorage`; a student can add tasks
the server has never seen; a quick-list to-do has no server row at all. Merging
server-side would render a date the student has already changed.

### `buildScheduleData` returns two shapes, and that is the whole design

Five providers flattened into one `ScheduleData`:

- **Dated rows** — assignments (`asg-`), events (`evt-`), appointments (`apt-`) —
  each pinned to one `dayKey` with `timeLabel` and `sortMinutes` pre-computed.
- **Classes as WEEKDAY RULES** — `dayOfWeek` + a wall-clock `startTime` + a
  pre-rendered `timeLabel`, expanded onto whichever days a view is showing.

**That split is why the month grid can page to any month with no round trip.**
Pre-expanding classes would mean either choosing a horizon on the server and having
the grid go blank past it, or shipping every meeting of the term to render one month.
A wall-clock time carries no timezone, so expanding it is safe wherever it happens.

An event with no distinct `end` becomes `allDay: true` with `timeLabel: "All day"`
and `sortMinutes: 0` — a marker for the day rather than a slot on it.

### The three rules that hold it together

**1. ONE filter, applied once.** `filterSchedule` runs on the whole `ScheduleData`
in `CalendarView` before anything renders, and the month grid, the week columns,
the agenda, the day sections **and the events section** all read that one result.
**No view filters for itself.** The old failure — a dot on a day with no row beneath
it — is structurally impossible rather than something to remember.

The checkable consequence: **switching view does not change what a day COUNTS.**
The header figure, the `n of m done` fraction and the month dots are all derived
from the filtered data independent of `prefs.view`.

**2. ONE `selectedKey`.** Owned by `CalendarView`, read and written by every view,
so switching view never loses the student's place. Selecting a day from an adjacent
month pulls the view onto that month so the selection is never off-screen.

**3. The clock is the server's.** `nowMinutes` arrives as a prop. Nothing in the
subtree asks the browser what time it is — see §7 for why the sanctioned client read
was declined.

### The components

| File | Role |
|---|---|
| `CalendarView` (445) | **The only stateful node.** Owns `selectedKey`, `monthKey`, `detail`. Merges, filters once, and renders the day panel as a **snippet** shared by month and week |
| `ItemDetail` (371) | **The dialog.** Everything about one item plus label, urgent and delete. A real dialog — see below |
| `MiniCalendar` (360) | The month grid. Up to 3 category dots per day plus `+n`, a roving tabindex, full grid keyboard navigation |
| `ItemRow` (253) | One item in the shape every view renders it. Three shapes: full, `compact`, and full-with-a-date. Carries the details trigger |
| `AddItemForm` (251) | Add a task, a to-do or a custom event. Markup only — the routing is a module |
| `KeyBar` (240) | The key AND the filter. Two dimensions that never merge |
| `DayEventsSection` (234) | "Happening, register". Join, leave, `.ics`, ignore |
| `AgendaView` (150) | A flat grouped list over 30 days. **The only view that can carry undated to-dos** |
| `CalendarHeader` (123) | The day's summary: big figure, breakdown, `n of m done`, "next up", the square strip |
| `WeekView` (116) | Seven columns. Not rendered below `48rem` |
| `SquareGrid` (103) | A day's items as squares. Re-exports `SquareCell` / `SquareGroup` from `calendarDay` |
| `ViewSwitcher` (87) | month / week / agenda as a radiogroup, plus the **agenda-only** grouping select |
| `DaySection` (68) | One titled group on the selected day |
| `DayGroupToggle` (49) | Arrange the day by type (default) or time |

### The pure layer behind it

Everything that could be a decision rather than markup was extracted, because
**Vitest runs in Node with no jsdom, so logic inside a `.svelte` file is logic no
gate can see.**

| Module | Holds |
|---|---|
| `schedule.ts` | The vocabulary. Category maps, the three category sets and their guards, grid arithmetic, `filterSchedule`/`isVisible`, grouping, `nextUpItem` |
| `buildSchedule.ts` | `buildScheduleData`, `todayKey`, `nowMinutesAt` |
| `calendarSources.ts` | `taskToItem`, `todoToItem`, `mergedSchedule` |
| `calendarDay.ts` (7a) | The selected day: `sortDayItems`, `arrangeDay`, `squareGroupsFor`, `dayCountParts` |
| `calendarViews.ts` (7b) | The views: `agendaRange`, `showsRowDate`, `undatedTodoItem`, `visibleUndatedTodos` |
| `calendarEvents.ts` (7c) | **The event boundary.** `dayEventRows`, `joinedCount` |
| `calendarAdd.ts` (7c) | **The routing.** `addCalendarItem`, `instantFor` |
| `ics.ts` (7c) | `buildIcs` (pure, clock as an argument), `icsFromItem`, `icsFromEvent`, `downloadIcs`. **Two mappers, not one** — see §14 |
| `calendarPrefs.ts` | `normalisePrefs` + the persisted store |
| `calendarItems.ts` | Custom events, labels, urgent — keyed by calendar item id. Plus `labelFor` / `urgentFor`, the ONE resolution rule |
| `ignoredEvents.ts` | `eventIdOf`, `canIgnore`, the store — keyed on raw `Event.id` |
| `tickItem.ts` | `tickItem`, `isTickable` — dispatching on the attached source row |

**Each extracted function has a branch that has already been got wrong once:**

- **The two-slice concatenation.** `schedule` and `personal` are two filtered slices
  of an already-sorted day, and two sorted lists joined end to end are not sorted, so
  every task landed after every class regardless of when it was due. `arrangeDay`
  sorts again.
- **The tickable denominator.** A section's fraction used to read `done /
  items.length`, so a group holding one finished task and two classes rendered "1/3"
  and implied three things could be ticked.
- **"1 classes".** `class` is the only irregular plural in the category list.
- **The attached source row on an undated to-do.** Built as an object literal in the
  prototype's markup, which is exactly where a field gets dropped.
- **The three-store routing.** A to-do filed as a task turns up on Home under a
  heading that says "pulled from every source", which is then untrue; a task filed
  as an event cannot be ticked, so a deadline quietly stops being one. Neither
  throws, neither fails a type check, and neither is visible on the day it happens.
- **The event id boundary.** An id shedding a prefix it did not have, or not
  shedding one it did. Invisible to types, to `svelte-check`, and to any
  round-trip test.

> **Extract by failure mode, not by size.** `AddItemForm` is a radio group and three
> inputs — nothing about it is hard. The routing is the only part that fails
> silently, so the routing is the part that left the component. Third time in three
> phases.

### Ticking dispatches on the attached source row, never on a parsed id

`mergedSchedule` puts the resolved `Task` or `QuickItem` on each item and `tickItem`
reads it. `isTickable` asks that same question — is a writable source attached — not
whether `done` happens to be set, and never by slicing a prefix off an id.

The id-parsing version missed every task the student added themselves and every
undated to-do in the agenda. Both failed identically and **silently**: the guard
found nothing and returned, the checkbox appeared to tick, and the next render put
it back.

**7c extended the same rule to deletion.** `customEventToItem` now attaches the
`CustomEvent` to the row, so `ItemDetail` deletes by `item.customEvent.id` rather
than `item.id.replace(/^custom-/, "")` as the source did — doubly hazardous there,
because a custom event's item id carries the prefix **twice**.

### `KeyBar`: two dimensions that do not merge

```
STREAMS   where a thing came from      fixed, legendOrder, known at build time
LABELS    what the student called it   open-ended, appears as they use it
```

**One list of chips is the obvious simplification and it is the wrong answer.** A
stream is a KIND OF THING that every student has; a label exists only because this
student typed it. Mixed together, "Career" and somebody's "thesis" look like the same
kind of switch.

They are kept apart **structurally, not by styling**, so an edit cannot flatten them
by accident: separate headings, separate `<ul>`s each with their own
`aria-labelledby`, separate prefs fields (`hidden` / `hiddenLabels`), separate helpers
(`toggleCategory` / `toggleLabel`), different accessible-name shapes ("Hide Class" vs
"Hide items labelled thesis"), a dot on a stream and never on a label, and the labels
section absent entirely when nothing is labelled. **Nothing iterates a merged array.**

**`allLabels` runs on the UNFILTERED merge**, and that is load-bearing: from
`filtered`, switching a label off would remove its own chip from the key and leave no
way to switch it back on.

**Off reads as off, not as absent** — a hidden stream keeps its chip, dimmed and
struck through. `hide all` exists and so does the warning that follows it.

The three toggles are real checkboxes so keyboard and screen-reader behaviour come
from the platform. They are `sr-only`, and `has-[:focus-visible]` moves the focus
ring out to the chip at the same 2px primary outline the base layer draws.

**7c's add form uses the same construction** for its kind picker — a labelled radio
group with `sr-only` inputs — so arrow keys work, the group is one tab stop, and the
selected value is announced.

### `ItemDetail` is a real dialog, which the source was not

The Next version had `role="dialog"` and `aria-modal="true"` on a div that kept
three of the six promises those attributes make.

| Obligation | How |
|---|---|
| Named | `aria-labelledby` at the real heading |
| Announced as modal | `aria-modal="true"` plus the scrim |
| Focus moves in | `use:focusTrap`, `initial: '[data-dialog-close]'` |
| Focus is trapped | the same action |
| Focus returns to the opener | the same action, on destroy |
| Escape dismisses | `use:escapeKey` |

**Focus lands on CLOSE, not the label field.** The common case is reading, and
stealing focus into a text input makes Escape feel like it cancelled an edit that
never started.

**The opener must be focused before the dialog opens.** A pointer press does not
reliably leave focus on a button — Chrome does it, Safari on macOS does not — so
`ItemRow` calls `focus()` on itself in the handler before `onOpen`. Without it a
mouse user lands on `<body>` and the next Tab starts at the top of the page.

**The two live fields read their STORES, not the row.** `detail` is a snapshot, so
reading its `urgent` for the checkbox would show the value as it was when the dialog
opened and never move — which is what the source does. Label and urgent resolve
through the same `labelFor` / `urgentFor` the merge applies to every row, so the
dialog and the row behind the scrim cannot disagree.

**Delete asks first, and the second step's geometry is thought about.** Deleting a
custom event is irreversible — there is no undo slot for it. So: "Keep it" takes the
position "Delete" occupied, and holds focus, so neither a double-tap nor an Enter
can destroy anything. **A confirm button rendered where the trigger was reintroduces
the accident the step exists to prevent.** And Escape peels one layer: with the
question up it cancels the question, not the dialog.

**The dialog is mounted outside the view branches**, because the agenda has no day
panel and its rows open one too, and `dayPanel` is keyed on the selection — which a
student can change from the keyboard while the dialog is open.

### `AddItemForm`: three kinds, three stores

```
task   work with a deadline   -> thrive:task-added     joins Home's Tasks list
todo   a scratch item         -> thrive:quicklist      joins the quick list
event  something happening    -> thrive:custom-events  goes nowhere else
```

**Three departures from the source, each fixing something:**

- **A to-do is dated at the day's start, not the form's time.** The quick list never
  offers a time and `todoToItem` renders every one "All day", so storing 09:00 puts
  a number in the store that nothing reads and that contradicts the row it produces.
  The date still has to be the chosen day, or the item lands in the agenda's "No
  date" bucket, which is not what "add to this day" asked for.
- **Label and urgent go to the annotation stores only** — see §3, shape two.
- **The confirmation names the list.** Three kinds go to three places and a student
  who picked the wrong one finds out days later on another page.

**No arrival, and that is a decision.** `arriveAtRow` needs a row with a DOM id and
calendar rows carry none; the arrival mechanism exists for Home's popovers jumping
across a collapsed card. Nothing like that happens here — the form sits directly
above the list it just added to, on the day it added to. Giving every calendar row
an id to support a jump nobody asked for would add a second arrival surface with its
own gate, and for a to-do (which lands in a section rather than at the cursor) would
move the page under a student about to add a second thing.

**Default time is 9:00, not "now".** Adding something to next Tuesday at the current
wall-clock time is almost never what was meant — and it would make the module read
the clock for no reason.

**Plain field ids, not `useId()`.** Only one add form is ever mounted: the day panel
is built once per view, and the week view's mobile branch renders the agenda, which
has none. The repo's rule is per-instance ids for per-instance components (`TaskRow`)
and plain ones for singletons (`AddTaskForm`).

### `DayEventsSection`, and the day-figure gap that is now closed

**Its own section rather than a group in the day list, because opting in is a
different act from ticking off.** A class is something the student is already
committed to and an assignment is something they owe; these are invitations, and
they carry a blurb, a "for you" badge and three controls no other row has.

**Joining states a fact and leaving is a separate control.** It used to be one
toggle reading "You're in", which removed you when pressed again — an off-switch
nobody could discover.

**Nothing is sent anywhere.** "Count me in" is local intent; "add to calendar"
downloads an `.ics` the student chooses to import. Each joined row says so.

**The fraction counts the rows ON SCREEN**, not the store, which holds every event
the student has ever joined across every day. A numerator from the store against a
denominator from the list reads "4/2" on a Tuesday.

**THE 7a GAP IS CLOSED.** The header's figure counts everything on the day, events
included, so for two phases a day could read "12" above ten rows. Both alternatives
were worse — filtering events out of the count would also have taken them off the
month grid, breaking "one filter, applied once". With this section mounted, every
category the figure counts has rows beneath it.

**And it is gated rather than argued.** `check:interaction` walks **every day in the
month with anything on it** — 36 days, 14 of them rendering an events section — and
asserts the figure equals the rows rendered, then asserts it again after an add. The
whole-month walk matters: the mismatch was per-category, so a check that happened to
land on a Tuesday of classes would have passed throughout the two phases the gap was
open.

### The week-to-agenda fallback, at 48rem

Seven columns on a 375px screen gives each one about 50px, narrower than the word
"Assignment". So below `md` the week grid does not render and the agenda answers.

**The Next source never had this.** See §3, shape three.

**It is CSS** — two media-gated wrappers, for the reasons in §7. Below the
breakpoint, week renders **exactly what agenda renders** (list, no day panel); the
alternative, list plus day panel, is a shape no view has. And it **says so on
screen**: the switcher still shows "week" selected, because that is the student's
choice and it is honoured the moment the screen is wide enough.

**48rem, not 40rem, and the difference was measured.** 40rem gave 71px columns —
correctly clamped and still reading as three short stacks.

Re-measured after 7c (the add form and the events section live in the day panel
below the grid, so nothing in the columns changed):

| width | week columns | column | agenda | fallback note | h-overflow | tallest title |
|---|---|---|---|---|---|---|
| 1330px | 7 | 133px | — | no | 0px | 60px |
| 900px | 7 | 109px | — | no | 0px | 60px |
| 769px | 7 | 90px | — | no | 0px | 60px |
| 768px | 7 | **90px** | — | no | 0px | 60px |
| 767px | 0 | — | 28 groups | yes | 0px | — |
| 375px | 0 | — | 28 groups | yes | 0px | — |

Within 1px of 7b's table — the same element measured with a different rounding
method. No console output at any width.

**There is no min-width and no horizontal scroll in `WeekView`.** The fallback is
what guarantees the room, so a scrollbar would mean the fallback was doing nothing.
**The knob is the breakpoint, never a min-width.**

### The agenda is the only view that can carry undated to-dos

Which is the whole reason it exists rather than being a nicer month grid. They have
no day, so they are not in `ScheduleData` at all — they travel beside it as
`MergedSchedule.undatedTodos` and get their own section, because pretending they are
due today would be a lie the student did not tell.

**`filterSchedule` cannot reach them, so `visibleUndatedTodos` applies the two
dimensions that can, by the same rules.** `showDone` is obvious. **`urgentOnly` hides
all of them**, because urgent is applied by `mergedSchedule`'s `annotate` over
`data.dated` only, so an undated to-do can never carry the flag — and leaving them in
meant switching urgent-only on emptied the whole page except that one section, which
reads as a broken filter.

They render `allDay: false` with an empty time column, departing from the source's
`allDay: true` — which made `ItemRow` label every one "all day", a claim about a day
they do not have.

**They get the details trigger too.** The agenda is the only place an undated to-do
is reachable, so it is the only place one can be labelled or flagged urgent;
withholding the control there would make a whole class of row uneditable.

### Agenda rows name their own date when the grouping is not by day

Grouped by day the heading IS the date and repeating it is noise. Grouped by type or
by course, a row's time alone does not say which of thirty days it falls on — and **a
time without a date, in a list spanning a month, is the wrong half of the information
rather than less of it.** The prototype rendered all three groupings identically.
`showsRowDate` is the decision, in the pure layer. Kept on review (owner).

The range is **anchored on TODAY, not on the selection**: the agenda answers "what is
coming up", and an anchor that moved with the selection would answer a different
question every time a student touched the month grid.

### One deliberate absence: the agenda has no add form and no events section

**Settled by the owner, 2026-08-21.** The agenda spans thirty days, so there is no
day for a new item to land on, and both other views offer one. Matching the source
is right here. Do not revisit without a proposal for what day an agenda-level add
would add to.

### What still has no gate, and was verified by hand

`check:interaction` now covers the calendar's editing surfaces (§15), so the by-hand
list is shorter than it was. What remains:

- **`MiniCalendar`'s keyboard grid.** 42 cells, one tab stop, arrows in all four
  directions with focus and selection agreeing, Home/End six days apart,
  PageDown/PageUp moving the month while focus survives the swap **and the document
  does not scroll** — the Next version's shared `preventDefault()` sat after the
  branch that returns, so paging also scrolled the page.
- **The 48rem boundary**, the table above.
- **The filter end to end.** Hiding a stream took the month dots 57 → 40, persisted,
  survived a reload, and was restored by "show all". Urgent-only took 114 agenda rows
  to 0 and removed the undated section too.
- **The labels dimension**, which needed a seeded `thrive:item-labels` because **no
  fixture item carries a label**.
- **The dot geometry**, at six widths — see §6.

No console warnings or errors at any width, in any view.

---

## 15. The gates

| Command | What it proves |
|---|---|
| `npm test` | **640 tests**, 29 files. Pure logic and source scans. **Nothing renders.** |
| `npm run check` | Types agree over 459 files. **Does NOT prove the page renders** |
| `npm run build` | It compiles, with `adapter-netlify` |
| `python3 scripts/check-contrast.py` | 58 assertions: 42 pairs, 6 ceilings, 10 structural |
| `npm run check:layout` | **17 targets × 3 viewports** in a real browser |
| `npm run check:interaction` | **190 assertions** in a real browser: the popovers, task editing, the calendar, booking, Ask THRIVE, the nav disclosure, and the page measure |
| the timezone sweep | The suite in seven zones, UTC+14 to UTC−11 |

**Both browser gates build their own server first** (`npm run build:node`,
`adapter-node` into `build-node/`) rather than assuming one exists. That closed a
real hole: `check:layout` used to be able to measure yesterday's output and pass.

**And one of them can press a button and measure a layout.** `check:interaction`
now covers a two-page double-booking RACE, the negative assertion that clicking
the month grid does NOT move the booking chips, the nav disclosure's DOM-removal on
collapse, that Ask THRIVE writes no `localStorage` key, two independent scroll
containers, and the page measure at two viewport widths.

**Four properties every gate here has.**

1. **It measures the thing rather than a model of it.**
2. **It reads its inputs from the source of truth.**
3. **It has been verified to fail** on the bug it was written for.
4. **It says what it does not cover.** A check that appears to cover something it
   cannot is worse than no check, because it converts an unknown into a false
   known. Where a gate's reach stops short, that boundary belongs *inside* the gate,
   at the assertion.

**Property 2 has teeth.** Two gates parse a source file rather than restating it:
`check-contrast.py` parses `app.css` — which is why the chroma pass needed no gate
edit at all — and `check-interaction.mjs` parses `features.ts` for `floatingTodo`.

**`check:layout` asserts the page cannot scroll further than it paints.** It does
**not** use `documentElement.scrollHeight` — that is the property that reported
1275px while nothing rendered below 1238px.

**It covers the calendar three times, because the view is a persisted PREFERENCE
rather than a URL** (7c). `/calendar` alone only ever measured the month grid, so
7b's two views were invisible to every gate for the same reason they are invisible
to all the others: nothing navigates to them. The gate writes
`thrive:calendar-prefs` before each target and removes it when a target names none,
so a view cannot leak forward into whatever is measured after it. The agenda is
**15,528px on a phone**, the tallest thing in the app by an order of magnitude.

**`check:interaction` exists because the other five were all green on a version
where pressing a pill did nothing at all.** None of the others can press a button.

**Verified to fail, eleven ways**, each broken on purpose:

| Broken | Result |
|---|---|
| Hover reintroduced | 6 red, including the original bug reproduced |
| The arrival mark not applied | 4 red |
| The mark never cleared | 2 red |
| The undo's expansion moved into an effect | **1 red, and NO console warning** |
| The title field's `onblur` removed | 2 red |
| A `dragend` put back on the row | 1 red (`derived_inert`) |
| `{#if href}` restored, so every card links out | 2 red |
| The `floatingTodo` guard removed from copy-to-list | 1 red |
| **The ignore store's normaliser reinstated** (7a) | **7 red across two spec files** |
| `block` put back beside `line-clamp-3` (7b) | measured 140px vs 60px — no gate, found by hand |
| **`eventId = item.id` in `dayEventRows`** (7c) | **7 red in `calendarEvents.spec.ts`** |
| **`annotate`'s old `!label && !isUrgent` shortcut** (7c) | 1 red |

**The ninth and eleventh carry the same lesson, and it is about the shape of the
test rather than the bug.** One direction of a cross-surface test *still passes* with
the bug reinstated, because both sides then share the same mangling — write `"3-1"`,
read `"3-1"`. **"Crosses two surfaces" is not the property that catches a key-space
split; not sharing a transformation is.** The assertions that pin the STORED KEY are
what actually go red.

**The tenth had no gate at all**, which is the honest entry in this table.

### What 7c's extension found on its first run

Two real bugs, in code that was green on all five other gates:

1. **A TypeError on every dialog close with focus in the label field.** A prop is a
   getter; the parent nulls it and the `{#if}` tears the subtree down a tick later,
   and the input's `onblur` fired in between. **No unit test could have seen it** —
   the suite has no focus model, and the throw needs a real blur during a real
   unmount. It only surfaced because something finally opened the dialog: the same
   shape as 6b's `derived_inert`, where a warning sat in the production build until
   a gate performed the gesture.
2. **Focus not returning to the opener** after a pointer-opened dialog.

What it covers that nothing else can: a count of DOM nodes against a rendered
number (the day figure), `document.activeElement` (the whole focus contract), a
statement about two presses (the confirmation step), and a store write reflected in
rendered text on **another page** (the join round trip).

`check:interaction` reports **SKIP** rather than passing when the fixture cannot
produce the case an assertion needs. It also states its blind spot: it drives the
production build, so `arriveAtRow`'s dev-only warn is compiled out and invisible.

**Scope, revised three times.** 6a: "stay on the widget that broke". 6b proved
editing needed it. 7a and 7b did not extend it, by instruction and by judgement.
**7c extended it**, because the dialog's entire contract is behaviour no unit test
in this repo can see, and writing a weaker unit test that looks like coverage is the
one thing the fourth property forbids. The general question — component tests via
jsdom or `vitest-browser-svelte` — is still open.

**Anything behind `import.meta.env.DEV` has no gate by construction.**

Both browser gates **skip loudly and exit 0** when there is no chromium.

**`npm run check` is not a render.** `svelte-check` passed 0 errors on a component
that threw `ReferenceError` on every request. **And it is held at 0 warnings.**

---

## 16. Standing decisions

### Settled this session

- **Home keeps the 1280px cap** (owner, asked and answered). Do not pin it
  narrower. Home was 1152 before the width work and 1280 is one step up, not a new
  problem. If Home should ever be narrower than the rest, that is an explicit
  decision about Home rather than a leftover.
- **The cold-start note goes in the README**, beside the no-authentication note,
  because a vanished booking reads as data loss and is not (§20).
- **The chip strip is the day picker on `/appointments`**, and the month grid beside
  it is a browse surface that moves "Your day" only. Booking and browsing are two
  questions; the coupling runs one way.
- **The booking window IS the published fixture.** Five business days. The separate
  one-calendar-month rule existed only while a grid could show days the fixture had
  not published, and went with it.
- **`--container-wide` is `/calendar` alone.** Every other route takes
  `--container-page`.
- **Both adapters stay** (§4, §20). `adapter-node` is what the browser gates spawn.
- **`@types/node` stays rejected**, even though the adapter switch wanted
  `process.env`. One narrowed property read is not worth reversing a recorded
  decision; the read goes through a narrowed `globalThis`.
- **`/ask` redirects rather than offering a landing page**, the conversation is a
  search param rather than a nested route, and a real conversation opened under the
  wrong destination is a 404.
- **The Ask history rail shows ONE destination's conversations**, not all three
  grouped, because the loader 404s a mismatch — a mixed list would mostly be 404s.
- **There is no chat store in the browser and none may be added** (§8).

**One still wants a second opinion:** a single
`svelte-ignore a11y_no_noninteractive_tabindex` on the chat log. axe's
`scrollable-region-focusable` requires the tabindex; Svelte's rule forbids it on
`role="log"`. Accessibility won, at one site, with the reason in the markup —
without it a long conversation is mouse-only.

### Standing

- **The old repo is read-only.** Verified untouched after every phase.
- **Django is not being written here** — and it is now on the critical path rather
  than merely queued (§18). `BACKEND.md` is the contract written out for whoever
  picks it up.
- **Measure layout in a real browser.** Never reason about pixels.
- **Drive interaction in a real browser too.** Anything a person presses gets
  pressed; anything a person *gestures* gets gestured.
- **A gate must be verified to fail** on the thing it guards. This is the only thing
  that distinguishes a passing check from a check that cannot fail.
- **An assertion's expected value must not be derived from the thing under test.**
- **"Crosses two surfaces" does not make a test non-vacuous.** Not sharing a
  transformation does. Count which assertions go red, do not trust the shape.
- **Pin the STORED KEY, never a round trip**, for anything key-space shaped.
- **Measure the counterfactual, not just the fix.**
- **Say when a check cannot see what it looks like it checks**, at the assertion.
- **A silent no-op is the worst failure mode this app has.** The reveal reading as a
  dead click, an id-parsing row lookup, a hover-swallowed press, an undo arrival
  without its expansion, a checkbox with nothing to write to, an unclamped
  `line-clamp`, and **an urgent flag that will not clear because it is stored twice**
  are all the same failure.
- **A control with two ways in has more states than it has booleans.**
- **A correct implementation of a bad interaction is still bad.**
- **Delete an abstraction that loses its last caller**, unless a specific named
  surface wants it. `hoverIntent` went the day hover did.
- **Moving a student to a row goes through `arriveAtRow`**, and **write everything
  before you call it**. **Not every focus move is an arrival** — a dialog's focus
  in and out is not one.
- **`RevealKind` is closed on purpose.** A third member forces an id-space decision,
  so it is made deliberately or not at all.
- **Resolve persisted overrides once per page**, and **apply the calendar's filter
  once per page**. Two views of one list that can disagree is a bug waiting for the
  first edit.
- **Never resolve a row by parsing its id.** Attach the resolved source object at
  merge time and dispatch on that — for ticking, and for deleting.
- **A normaliser that cannot distinguish its input cases is a defect, not a
  helper.** `eventIdOf` cannot tell a raw event id from a calendar item id, so both
  event-scoped stores normalise nothing and the one prefixed surface converts at its
  own boundary, once.
- **Is this a fact about the EVENT or about the ROW?** That is the test for whether
  something belongs in a new key space. It is why joins and ignores share one and
  labels and urgent flags do not.
- **A prop is a getter, so its declared type has a lifetime.** Any handler that can
  fire during teardown is reading a prop the parent may already have revoked. Latch
  it at mount where the value genuinely cannot change; guard the handler where it can.
- **A dialog owes six things and attributes are three of them.** Named, modal, focus
  in, focus trapped, focus returned, Escape. Focus the opener BEFORE opening.
- **A destructive step's second press needs its geometry thought about.** The safe
  control takes the trigger's position and holds focus. Escape peels one layer.
- **Extract by failure mode, not by size.** The complicated part of a component is
  usually the part you would notice breaking.
- **Feedback beats correctness.** "It works" and "it appears to work" are different
  acceptance criteria and only one of them is the product.
- **A control whose result is invisible is worse than no control**, and **a link to a
  page that is not built is worse than no link**, and **an inert control is a dead
  affordance** — three removed so far: the parked "View all", copy-to-list with
  nowhere to copy, and Home's "count me in".
- **If a fallback hides something the student explicitly chose, say so on screen.**
- **Making an invisible state visible means auditing every path it can now reach.**
- **A control's `aria-controls` must name the region it actually expands.**
- **Prefer a type to a rule someone has to remember.**
- **A discard control must out-race every save-on-focus-loss path.**
- **Durations are either motion or dwell**, and they do not share tokens.
- **A viewport question CSS can answer belongs in CSS.** The JS form is for cases
  with no CSS equivalent — moving focus, not choosing a layout.
- **Pick a breakpoint by measuring, not by naming a size**, and the knob is always
  the breakpoint. "Fits" and "is legible" are different bars.
- **Work colour in a perceptual space, and raise chroma at fixed lightness** when
  contrast is the binding constraint. **And check the result against every RESERVED
  colour**, because raising chroma moves a hue toward its neighbours as well as away
  from grey.
- **Size may be the cheaper lever than colour.** The dots pass got more from 6px → 8px
  than from five retuned tokens.
- **A utility that works by setting `display` conflicts silently with every
  `display` utility.** `line-clamp-*`, `truncate`, `sr-only`.
- **Wait past the longest transition on an element before reading a computed
  style.** `transition-colors` includes `outline-color`.
- **A verification claim decays exactly like a comment does.** Re-run the sweep on
  any date-shaped change, not just on new date-shaped code.
- **Where the source and MIGRATION disagree, the source wins.** Where the source is
  *wrong*, improve on it. Where the source contradicts **itself**, it is not a source
  to follow at all.
- **CONTEXT is regenerated in full every handoff** — with the owner able to defer it
  across a run of phases, which is what happened for 7a and 7b. A same-session patch
  is a sanctioned exception for a small delta.
- **`@lucide/svelte`, not `lucide-svelte`.**
- **`cn()` survives** for the `class`-override case only.
- **Vitest in Node, no jsdom.** Which is why logic gets extracted out of components.
- **Probe before asserting.** **Suspect the probe before the product** — several
  checks failed on correct code because `ShowMore` also carries `aria-expanded`, a
  synthetic `input` event left a submit button disabled, a computed style read at
  t=0 reported the wrong colour, and a programmatic `.click()` does not focus a
  button the way a real press does.
- **`npm run check` is held at 0 warnings**, and a warning is answered rather than
  suppressed.
- **Diff a port, do not review it.**
- **Any test asserting an absence needs a companion assertion that it can still see a
  presence.**
- **Extract strings as you build**, not afterwards. **And promote a string to
  `common` the moment a second surface renders it for the same act.**
- **No personal names in any doc.** Roles instead — "a teammate", "the faculty
  lead", "the owner". Fixture data is out of scope. Removing a name must not remove
  information: rewrite the sentence rather than dropping the fact.
- **Capture the artefact, not the event.** A gate asserting that a download FIRED
  proves a button is wired and nothing else. The `.ics` gate wraps
  `createObjectURL` and reads the file, because the output is consumed by software
  and a wrong DTSTART imports "successfully" and is wrong.
- **No Claude/Anthropic attribution anywhere** — commits, PRs, file headers.
  Verified clean across all 89 commits.

---

## 17. Voice and copy

Calm, plain, honest about what is simulated.

- Say plainly when something is a prototype or is not wired up. A placeholder that
  mimics a real answer teaches the student to trust something that is not there —
  which is why `AssistantConversation` has no brain and says so, and why
  `providers.ts` marks the request and resume flows **SIMULATED** in place.
- **Copy that apologises for an unfinished feature has to be deleted the moment the
  feature lands**, or it becomes a lie.
- **Sometimes the honest answer is to say nothing.** A "View all" pointing at a
  placeholder was replaced by no link rather than by a caption explaining why.
- **But sometimes it is to say exactly what happened.** The week fallback tells the
  student their screen is too narrow rather than silently showing a different view.
- **And sometimes it is to say where a thing went.** The add form's confirmation
  names WHICH list the item joined, because three kinds go to three places and
  picking the wrong one is otherwise discovered days later on another page.
- **State a promise where a student could reasonably assume otherwise.** Every
  joined event row says nothing was sent anywhere, and the detail dialog says
  everything typed into it stays in this browser. Those are the two surfaces where
  the controls look like they might contact somebody.
- Empty states are an invitation to act, never "No data". Never a dashed outline.
- "Overdue" alone, not "Overdue by 3 days" beside "3 days ago".
- Counts and timers in mono and tabular, so a row does not reflow.
- **If an action changes state the student cannot see, it needs a cue.** And if it
  changes state that then *removes the row*, it needs a sentence.
- **Say why a control is disabled.** The dialog's "add to calendar" is off for a
  recurring class and says so — a greyed button with no reason beside it reads as a
  bug.
- **Name the subject in an accessible label.** Five identical "Edit" buttons in a
  list are five buttons a screen-reader user cannot tell apart. The calendar's chips
  say what pressing them will DO — "Hide Class" — rather than what is currently true.
- Comments explain **why**, not what.

---

## 18. Open loose ends

**Blocking before any multi-person demo**

1. **The three mock stores are process-global.** MIGRATION §9 defect 1. Concurrent
   students book over each other and see each other's data; everything resets on
   restart. **Django is the fix**, and two queued features (4 and 5) now depend on it.

**Next up**

2. **`/assignments`** — the same `TaskRow` with no `reorder` prop. First outside
   caller of the row, and **owes it a `role="list"` container**.

3. **~~Appointments.~~ Built.** Cards, a chip strip, the booking panel, "Your day"
   and a clickable month. Includes the app's only form actions and the only
   double-booking path.

3b. **The real-phone pass**, now four items: touch drag on Home's task rows, the
   month grid at 375px, the 8px category dot against an actual thumb, and the Ask
   history strip against a thumb. All four were measured rather than felt.

3c. **A write path for conversations.** `/ask` reads real providers and can create
   nothing. There is no designed shape for "start a conversation" or "append a
   turn", and the read shapes were built around fixtures rather than a real
   service's response — so expect those two providers to change. `BACKEND.md` §8.

**Scoped, not built**

4. **Ask THRIVE as a full page.** **This replaces the earlier tabs-on-top idea** —
   do not build tabs.

   The shape: **a SECOND left rail, beside the nav rail**, holding three sub-items —
   **Resources, Course Recommender, Career** — plus a **chat window** and **saved
   chat history**.

   Two things to settle before building:
   - **Saved chat history cannot live in `localStorage`.** Too large, too long-lived,
     and the first persisted thing that is not a small override keyed by id. Needs
     **Django, or the RAG service a teammate is building**.
   - **Two rails and one `nav` landmark.** §10 keeps exactly one `nav` in the a11y
     tree at a time.

   Also unsettled: Resources and Career are the subjects of two PARKED routes (§11).
   And `FEATURES.floatingAssistant` still exists — a floating assistant plus a page
   with chat and history is two homes for one conversation.

   Wired to **a teammate's RAG service** later.

5. **Group Projects — a future FIFTH nav item.** Group members, a project holding
   tasks and subtasks, assigning a task to a person.

   **The first feature that is not one student's private view**, and that is the whole
   difficulty:
   - **Real accounts.** MIGRATION §9 defect 2 — no auth on any server action — stops
     being a note and becomes a blocker.
   - **A shared database.** Every persistence property in §8 assumes one person's
     overrides in their own browser.
   - **The fixtures model one student** (§12).
   - **The nav has four destinations by decision**, and the mobile bar has four slots.

**The real-phone list**

6. Two things wait on a session with an actual handset, because a simulated viewport
   cannot answer either:
   - **Touch drag on Home's task rows.** HTML5 drag does not fire on touch, which is
     why the keyboard move buttons exist — but no gate asserts those buttons are the
     only route on a phone or that they are reachable there.
   - **The month grid at 375px.** The cells are ~46px wide, at the touch-target
     floor, in a 7×6 grid, each holding a dot row that is now 8px per dot. Nothing
     measurable is wrong; it has never been touched by a thumb. **The dots pass makes
     this more worth doing, not less** — 8px was chosen against a measurement and
     should be confirmed against a finger.

**Carried**

7. **Provider copies are shallow.** `{ ...version }` shares nested arrays with the
   store. Pinned by a test that says why.
8. **`npm test` renders nothing.** `check:interaction` now covers Home and the
   calendar; it is still not a general answer.
9. **Home fits 1218px, not 1052px.** Accepted. Phone is 3235px. **The calendar's
   agenda is 15,528px on a phone**, which is a long list rather than a broken layout,
   and is now gated.
10. **Three dead providers:** `getSyllabi`, `getResources`, `getCurrentResume`.
11. **`requestTypeHelp` has no consumer** anywhere in the prototype.
12. **Two product decisions parked pending real screens:** the missing year in
    `formatShortDate`, and `countdownPhrase` counting to "13 months".
13. **`taskNotes` on `createOverrideStore`?** It duplicates the persistence logic.
    Three more phases have not needed the refactor, which is mild evidence against it.
14. **`format.ts` still emits `"Invalid Date"` from `formatShortDate`**, and a
    parseable-but-wrong date still gets through `describeDue`: V8 rolls `"2026-02-30"`
    into March.
15. **`matchesWide()` is still unported**, and no phase has become its first
    consumer — see §7.
16. **`calendarSources.nowMinutes()` has no consumer** and may never get one. See §7.
17. **MIGRATION §9 defect 14 — `custom-custom-…` ids.** Cosmetic and internally
    consistent, and now **harmless**: nothing parses them, because the row carries its
    own event. Changing the minted id would strand every stored event for no gain.
    Pinned by a test that says so.
18. **A task moved beyond seven days leaves Home's list.** Correct, and announced
    rather than silent. `/assignments` is where it lives (owner: accepted).
19. **`prefs.view` can hold a stale `week` or `agenda`** from a hand-edited store.
    Harmless — nothing but `ViewSwitcher` writes it.
20. *(closed this session)* Home's "Add to calendar" is wired. **There is no inert
    control left in the app.**
21. **Teal and amber cannot be made more vivid** without moving lightness, which the
    contrast floor forbids (§6). If the dots still read muted, the next lever is size
    or the surface behind them, not the tokens.

**Closed in 7a, 7b and 7c**

- **`buildScheduleData` is ported.** The gating piece since Phase 2.
- **BOTH event key-space defects are fixed** — ignores in 7a, joins in 7c — and both
  have cross-surface coverage that pins the stored key rather than round-tripping.
- **MIGRATION §9 defect 10 — `SquareGrid`'s white ring halo** — built correctly with
  an `outline` instead.
- **The 40rem week fallback**, which never existed in the source, is built at 48rem.
- **A pre-existing timezone bug in `reveal.spec.ts`**, found by running the sweep.
- **`line-clamp-3` silently unclamped** beside `block`.
- **The day-figure gap.** Closed by `DayEventsSection`, and gated across every day
  in the month with anything on it.
- **`check:layout` extended to the week and agenda views.**
- **`CalendarView.detail` is written.** It was declared in 7a and had no writer.
- **`ItemDetail` became the third caller** for `escapeKey` and `clickOutside`, and
  the first for `focusTrap`.
- **Home's "count me in"** — live, and its round trip to the calendar is gated.
- **Home's “Add to calendar”** — live, and the gate reads the FILE rather than
  asserting that a download fired.
- **The agenda's add form** — settled as deliberately absent (owner).
- **The calendar's "next up" arrival** — settled as NOT an arrival.
- **Agenda rows naming their own date** — kept on review (owner).
- **All nine of 7b's absence decisions** — approved (owner).

---

## 19. Timeline

Release 1 target was **end of August 2026**; a control group was planned for the
**last week of August**. Both dates come from the prototype's `REPORT.md` and
predate the decision to rebuild — **they need re-setting against the rebuild,
which is the largest open planning question.**

Note the interaction with loose end 1: a control group implies concurrent users,
and the process-global stores mean concurrent users see each other's data. Either
Django lands first or the control group is one person at a time.

**Two scoped features move Django from "later" to "on the critical path".** Ask
THRIVE's saved chat history cannot live in `localStorage`, and Group Projects is
shared between people by definition. Neither can be demoed on the mock layer at all,
which is a different situation from the appointment and request flows — those work
today and are merely process-global.

The prototype's Release 1 scope was: (a) the student dashboard, (b) appointment
scheduling with history/notes/summaries/topic tagging, (c) `/resources` as the
Resource Navigator surface, (d) per-task time estimates.

**(a) is complete.** Home is real and editable. **And the calendar — which was not
in that scope at all — is now COMPLETE and is the largest surface in the app**,
which is the thing most worth weighing when the dates are re-set: the rebuild has
two finished surfaces, and neither the appointment flow nor the resource navigator
is one of them. (b) is now real — **the appointment flow is built**, including the
double-booking path. (d) was never begun, and (c) exists in a different shape than
planned: `/ask/resources` answers questions from program material, while
`/resources` stays a parked stub. Those are two surfaces with one name, not one
absorbing the other.

**Four surfaces are finished now** — Home, the calendar, appointments and Ask
THRIVE — and the app is deployed. What is missing is not screens; it is a backend.


---

## 20. Deployment, and what a public URL changes

Deployed to **Netlify** from `main` since 2026-08-21, so teammates can open a link
instead of cloning the repo and getting onto Tailscale.

### The setup, and why it is committed

`netlify.toml` lives at the **repo root** with `base = "frontend"`, because the app
is not at the root and that is the only place Netlify reads the file from or accepts
`base`. `command`, `publish` and a pinned `NODE_VERSION = "22"` are all in it, so
the deploy is reproducible from a clone rather than from settings somebody typed
into a dashboard once. Nothing is configured in the UI.

**One expected line in the build log, recorded so nobody "fixes" it:**

```
Using @sveltejs/adapter-netlify
  No netlify.toml found. Using default publish directory.
```

The adapter looks for that file relative to its own working directory, which is
`frontend/`. It therefore never sees the root file and falls back to its default,
`build` — which is exactly what the root file declares. The adapter takes no
`publish` option (`{ split, edge }` only). A second copy inside `frontend/` would
silence the line at the cost of two files that can drift.

### Both adapters stay

See §4. `adapter-node` is not a fallback; it is what the two browser gates spawn,
and those gates have caught more real defects than everything else in this repo
combined. Deleting it to tidy up would have cost them.

### What the URL changes, which is nothing technical and everything socially

None of this is new. It has been true since the data layer was built against
fixtures. **A public URL is what makes it matter**, and it is written into the
README for that reason:

- **No authentication.** No login, no session, no per-student anything. Anyone with
  the URL is the fixture student.
- **The mock stores are process-global** (MIGRATION §9 defect 1, BLOCKING). Two
  people using the site at once book over each other and see each other's
  appointments.
- **The form actions have no auth check** and are reachable by direct POST
  (§9 defect 2).
- **A cold start silently wipes the stores.** Netlify sleeps the function after
  inactivity; waking it starts a fresh process and the stores live in that process.
  So the first visit after a quiet period is slow AND arrives to an empty
  appointment list. **Nobody cancelled anything.** This is the one that will be
  mistaken for data loss, so the README says to book what you need to demo in the
  same sitting.

**Do not share the link outside the team, and do not put anything real into it.**

### The UTC date question, settled

The deployed site can show a different day than a laptop in California, for the
hours between UTC midnight and local midnight.

**That is the date rule working, not a bug.** The server decides what "today" is,
once, and hands down formatted strings — which is the whole of §7. A viewer's clock
is deliberately not consulted, because consulting it is what produced the hydration
drift the rule exists to prevent.

If it should follow the viewer instead, that is a **product decision**, not a
formatting fix: it means storing a per-student timezone and reading it in the `load`
alongside `new Date()`. Nothing about the current behaviour needs changing to
support that later.

---
