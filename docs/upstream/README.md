# THRIVE

THRIVE is a single calm surface for students in the UC San Diego Rady School's
MSBA program. Right now the things a student needs are spread across half a dozen
systems — the course site, the advising tool, the career centre, email, and a pile
of PDFs — so a simple question like "what do I owe this week" means visiting all of
them. THRIVE pulls that into one place: what is due, what is happening, what the
student has set themselves, and what they could sign up for.

This repo is a **rebuild**. A working Next.js prototype exists and is now frozen;
this is the SvelteKit and Django version of it. Two surfaces are finished — the
dashboard and the calendar — and the rest of the routes render a placeholder page
on purpose, so the navigation tells the truth about what is built.

**The Django side has not been started.** See "For the backend" below; the seam it
plugs into is already built and documented.

---

## Where to start

**Building the backend? Read `BACKEND.md` and stop there for now.** It is the
contract — every provider, every type, and the rules behind them — and it is
enough to start. The doc guide below says which of the other files are frontend
build history you can skip.

**Working on the frontend? Read `CONTEXT.md` first.** It is the snapshot: what this is, how it works, and
every decision that has been made and why. It is written so that someone arriving
cold can pick up the work without asking anyone, and it is regenerated in full each
time rather than patched, so nothing in it is half-updated.

**Then `CODEMAP.md`** when you need to find something. It is a navigation map —
entry points, what each file is for, and which files answer which questions.
Reading it costs less than opening ten files to orient yourself.

**Then `CONVENTIONS.md`, before you write any code.** It holds ten rules that
**nothing in the tooling enforces**. Each exists because breaking it produced a real
bug that was hard to see — a checkbox that ticked and silently reverted, a store
that two pages each read correctly and differently, a date that was right in one
timezone. The type checker will not catch any of them. Review is the enforcement,
which only works if you have read them.

---

## Layout

```
thrive/
├── BACKEND.md    the contract Django has to satisfy — start here for backend work
├── netlify.toml  the deploy config, at the root because that is where Netlify reads it
├── frontend/     the SvelteKit app — everything that currently runs
├── backend/      the Django API — a README and nothing else yet
└── scripts/      repo-wide checks that belong to neither side
```

`frontend/` is the whole application today: UI, routing, and a data layer that
reads mock fixtures. `scripts/` holds three checks that need a real browser or a
real CSS parser and so cannot live in the test suite.

---

## Running it

**Node 20 or newer.** Developed on Node 24 with npm 11, but 20 is the floor the
toolchain actually needs and nothing below 24 has been tested — so if you are on
22, expect it to work and say so if it does not.

```bash
git clone git@github.com:rsm-msaad/thrive.git
cd thrive/frontend
npm install

npm run dev -- --open      # dev server on :5173
npm run build              # production build, for Netlify
npm run build:node         # production build, as a plain Node server
ORIGIN=http://localhost:3000 node build-node/index.js   # run it on :3000
```

**Two adapters, and the environment picks one.** `npm run build` uses
`adapter-netlify`, which is what a push to `main` deploys. `npm run build:node`
sets `ADAPTER=node` and uses `adapter-node`, which writes to `build-node/` and is
what the two browser gates spawn — they drive a real long-running server, which a
bundle of serverless functions is not. Neither adapter changes the app: nothing is
prerendered, so every route is server-rendered per request under both. See
`vite.config.ts` and `netlify.toml`.

`ORIGIN` is required by the Node build and not by Netlify — see `setup_info.md`.

If a page looks stale locally, something is usually holding the port:
`lsof -ti:3000 | xargs kill -9`.

---

## The deployed site is not private

There is a Netlify deploy so teammates can open a link instead of cloning the
repo or getting onto Tailscale. Treat that URL as **shared with everyone who has
it**:

- **There is no authentication.** No login, no sessions, no per-student data.
  Anyone with the URL sees the app.
- **The mock stores are process-global.** Appointments, course requests and
  resume versions live in module-scope objects on the server, shared by every
  visitor and wiped on restart. So two people using the site at once book over
  each other and see each other's bookings. This is `MIGRATION.md` §9 defect 1,
  graded BLOCKING, and it is inherited deliberately — Django is the fix.
- **The form actions have no auth check** and are reachable by direct POST
  (§9 defect 2).
- **A booking can vanish on its own.** Netlify runs the server as a function that
  sleeps after a spell of inactivity. Waking it starts a fresh process, and the
  mock stores live in that process — so the first visit after a quiet period is
  both slow AND arrives to an empty appointment list. Nobody cancelled anything;
  the store was reset. On the Mac Studio the same thing happens on a restart or a
  hot reload, just less often.

None of that is new; it has been true since the data layer was built against
fixtures. A public URL is what makes it matter. **Do not share the link outside
the team, and do not put anything real into it** — no actual names, no actual
questions you would not want a stranger to read.

**If you are demoing, book what you need to show in the same sitting.** Nothing
survives a cold start, so a booking made yesterday is very likely gone.

---

## Stack

SvelteKit 2 · Svelte 5 (runes) · TypeScript 6, strict · Vite 8 · Tailwind v4 ·
Vitest 4 · `adapter-node` · npm. No component library yet — the handful of
primitives are hand-built and live in `frontend/src/lib/components/ui/`.

---

## The docs

Twelve files at the repo root, which is a lot to arrive at. **What you read
depends on which side you are working on.**

### If you are building the backend, read two things

| File | What it answers |
|---|---|
| **`BACKEND.md`** | **Start here.** The contract: all 27 providers with exact signatures, every domain type written out, the date format, and the rules a signature does not show — what may be null, what an empty result means, where an error is thrown. Derived from the code, not from memory. |
| `README.md` § "How the data layer works" | The section below. The same thing in prose, read once. |

Then, when you need them: `CONVENTIONS.md` for the date rule in full, and
`MIGRATION.md` §2 and §9 for the prototype's provider inventory and its known
defects.

**You can skip these. They are frontend build history.**

`CHANGELOG.md`, `HANDOFF.md`, `FINDINGS.md`, `BUGS.md`, `TESTING.md` and
`CODEMAP.md` are all about how this frontend came to be the way it is — session
diaries, layout arguments, contrast measurements, Svelte reactivity lessons. They
are genuinely useful if you touch the frontend and near-useless otherwise. Nothing
in them is required reading to implement the contract.

`CONTEXT.md` is the full picture of the whole project. Worth an hour eventually,
not before writing your first model.

### The full list

| File | What it answers | Who needs it |
|---|---|---|
| `BACKEND.md` | The provider contract, the domain types, and the rules behind them. | **Backend** |
| `CONTEXT.md` | What this is, how it works now, and every standing decision with its reasoning. | Everyone, eventually |
| `CODEMAP.md` | Where things are. Entry points, file map, what each module is for. | Frontend |
| `CONVENTIONS.md` | The rules nothing enforces automatically. **Read before writing frontend code.** | Frontend; §1 matters to both |
| `MIGRATION.md` | The frozen prototype, inventoried: routes, providers with signatures, date rules, components, design system, stores, tests, known defects. | Both — it is the only copy |
| `HANDOFF.md` | The diary. What happened each session, what was decided, what is still open. | Picking up mid-stream |
| `TESTING.md` | What is covered, what is not, and why some things can only be checked in a browser. | Frontend |
| `BUGS.md` | Defects found and fixed, plus ones deliberately recorded and not fixed. | Frontend |
| `FINDINGS.md` | Reusable lessons, usually learned the hard way. | Frontend |
| `DEPENDENCIES.md` | Every package and why it is here, including rejected ones. | Frontend |
| `setup_info.md` | Environment, versions, how to run each gate, and the gotchas that cost time. | Setting up |
| `CHANGELOG.md` | Dated session summaries, newest first. | Catching up |

Only `CONTEXT.md` is regenerated in full. The rest are appended to, so their
history is intact.

**One caveat on `MIGRATION.md`:** it documents the frozen Next.js prototype, not
this repo, and it says 25 providers because that was true when it was written.
There are 27. `BACKEND.md` §9 lists every place the two disagree.

---

## How the data layer works

Django is not started. This is the least obvious part of the repo and the part a
backend engineer needs first, so it is worth being explicit. **`BACKEND.md` has the
detail; this is the shape, to read once.**

### One seam, 27 functions

Every screen gets its data from one layer at `frontend/src/lib/data/`. Its public
surface is `data/index.ts`, exporting exactly three things: the domain types, the
**27 provider functions**, and two label maps. Nothing in the app reaches past
that. The mock fixtures underneath are private, and a component that needs
something not on the provider surface has found a gap to widen rather than a file
to import.

**Every provider returns a `Promise`, including ones that could answer
synchronously today.** That is the whole point: when a body becomes a real HTTP
call, the signature does not change and no caller is touched. **Django replaces the
bodies; the signatures do not move.** That is why the UI will not change when the
backend arrives.

Sorting and filtering that every caller would otherwise repeat is already done
behind the seam, and should stay there. Six providers guarantee an order and their
callers do not re-sort — change one and the UI changes silently.

**About a third of them have no caller yet.** 14 of 27 are reached; the rest are
implemented and tested but the surfaces that would use them are not built.
`BACKEND.md` marks which.

### Dates: Django never formats one

Every provider returns **ISO-8601 strings** — `"2026-08-11T09:00:00-07:00"` for an
instant, `"2026-08-11"` for a calendar date. The frontend classifies and formats
every date **server-side, from a single clock read per page**, and components
receive finished strings like `"Overdue"` or `"2:30 PM"`.

This is the thing most likely to be got wrong, so plainly: **a string like `"Due
tomorrow"` or `"Aug 11"` is unusable here.** It cannot be reclassified, cannot be
compared, and is wrong for anyone in a different timezone from the server. Send the
instant and nothing else.

A consequence worth knowing before someone asks: because the server decides what
"today" is, a deployment running in UTC shows a different day than a viewer in
California for a few hours either side of midnight. **That is the rule working.**

### Three id key spaces, and no fourth

Browser-persisted state is keyed on three id spaces: the task's own id, a calendar
item id, and a raw event id. **Inventing a fourth has already caused two real bugs
here** — both times one surface wrote under a transformed key while another read
the untransformed one, each self-consistent and neither able to see the other, and
both invisible for weeks because round-trip tests passed throughout.

The test for a new space is: *is this a fact about the event, or about the row?*
When these move server-side, the identity each table keys on is that decision made
permanent. Ask before adding one. `BACKEND.md` §6.

### What is browser-only today and must move

All of this is in `localStorage`, so it is per-browser rather than per-student, and
wrong the moment there are real accounts:

- **The override stores** — task edits: done, titles, priorities, due dates, order,
  self-added tasks, and notes.
- **The ignore and join stores** — dismissed events, and "count me in".
- **Chat history**, which **cannot live in `localStorage` at all**: conversations
  are large, grow without bound, and a student on a second laptop would find an
  empty history indistinguishable from never having asked anything. It is already a
  provider for that reason.

One shape has to survive the move: **these record only what the student personally
changed, keyed by id, with "absent" meaning "use the source value".** A plain set
of done-ids cannot express *"I unticked something that ships as done"* — reload and
it silently re-ticks. `BACKEND.md` §7.

### What does not exist, and needs designing rather than porting

- **Authentication and per-user isolation.** There is no login, no session, and
  `getStudent()` returns one hardcoded record. The three mock stores are
  module-scope objects **shared by every visitor and wiped on restart** — so two
  people book over each other today. This is the blocking item and the main thing
  Django is for.
- **`StudentConsent` is modelled and unenforced.** The flags exist; nothing reads
  them before fetching. Where consent is checked is an open design question.
- **Group projects.** Scoped, not built, and the first surface that is shared
  between people by definition rather than being one student's private view. None
  of the existing patterns cover it.
- **A retrieval service behind Ask THRIVE.** Three destinations exist as shells.
  There is no write provider for conversations and no designed shape for one.

Start at `BACKEND.md`, then `frontend/src/lib/data/providers.ts`.

---

## The gates

Six checks. **All six must pass before anything is pushed**, plus the timezone
sweep below. They are run by hand — there is no CI yet.

```bash
cd frontend
npm test                              # the unit suite
npm run check                         # svelte-check, held at 0 errors AND 0 warnings
npm run build                         # it compiles
python3 ../scripts/check-contrast.py  # the palette
npm run check:layout                  # page height, in a real browser
npm run check:interaction             # behaviour, in a real browser
```

| Gate | What it catches |
|---|---|
| `npm test` | Logic errors in the pure layer. Runs in Node with **no jsdom, so nothing renders** — which is why logic is deliberately kept out of `.svelte` files, where no gate could see it. |
| `npm run check` | Type disagreements. It does **not** prove a page renders: it once passed cleanly on a component that threw on every request. |
| `npm run build` | It compiles, and the production build is what the two browser gates drive. |
| `check-contrast.py` | A colour that stops being legible. It **parses `app.css`** rather than keeping its own copy of the values, so a token edited there is checked there. Some assertions are ceilings — they assert a decorative colour stays *below* the text threshold, so putting words in it fails rather than quietly shipping. |
| `check:layout` | A page that scrolls further than it paints. Dead space at the bottom of a page is invisible in a screenshot and makes "does this fit" unanswerable. |
| `check:interaction` | Anything only a real browser can see: pointer events, focus, live regions. It exists because every other gate was green on a version where pressing a button did nothing at all. |

Plus **the timezone sweep**, which is part of the definition of green rather than
an extra — run it after touching anything date-shaped. The command is in
`setup_info.md`. It has caught two real failures.

The two browser gates need Chromium. They **skip loudly and exit 0** when there is
none, rather than failing for a reason that has nothing to do with the code. Install
one with `npx playwright install chromium`.

---

## Two things that will surprise you

**The design system is a single file and it is enforced.**
`frontend/src/app.css` holds every colour, size, radius and duration. Never
hardcode one in a component — a test scans the source and fails on a hex value or a
font name in markup. `CONTEXT.md` §6 explains the palette, including why the brand
yellow is decoration rather than an indicator.

**`/swatch` is a throwaway route** that renders every token on one page. It is a
comparison target for the port and should be deleted before release. It is not part
of the product.
