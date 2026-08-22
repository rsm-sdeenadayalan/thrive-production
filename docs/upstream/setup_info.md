# setup_info

Environment, versions, and how to run things.

**Last verified:** 2026-08-21 at `3d38df1`.

---

## Machine

| | |
|---|---|
| Platform | macOS (Darwin 25.5.0), Apple silicon |
| Shell | zsh |
| Node | **v24.14.1** |
| npm | **11.11.0** |
| Python | system `python3` — used only for `scripts/check-contrast.py`, which has zero dependencies |
| Package manager | **npm**. No pnpm/yarn lockfile; do not introduce one. |

No Docker anywhere yet. It will most likely arrive with the Django backend.

---

## Repos

| | |
|---|---|
| This repo | `~/code/thrive` → `git@github.com:rsm-msaad/thrive.git`, **private** |
| Default branch | `main` |
| Frozen prototype | `~/Desktop/Test 1/Thrive-msba-brain` → `thrive-msba-brain.git` |

**The prototype is READ-ONLY REFERENCE.** Never write to it, never touch its
remote. Its uncommitted working tree has been left exactly as found and verified
untouched after every phase. Everything worth knowing about it is in
`MIGRATION.md`.

`gh` is authenticated as `rsm-msaad`, git protocol **ssh**, token scopes
`gist, read:org, repo`.

Git identity for commits is the repo owner's, set in the local `git config`.
Check it with `git config user.name` and `git config user.email` rather than
assuming — a wrong identity on a commit is not worth fixing after the fact.

---

## Running the frontend

```bash
cd ~/code/thrive/frontend
npm install

npm run dev -- --open    # :5173, the one you want
npm run build            # production build for NETLIFY, into build/
npm run build:node       # production build as a Node server, into build-node/
ORIGIN=http://localhost:3000 node build-node/index.js   # run that, :3000
npm run preview          # vite's preview of the build, :4173
npm run check            # svelte-check
npm test                 # vitest run, 640 tests
npm run test:unit        # vitest watch
```

### Two adapters, picked by an environment variable (added 2026-08-21)

`vite.config.ts` selects `@sveltejs/adapter-netlify` by default and
`@sveltejs/adapter-node` when `ADAPTER=node` is set. `npm run build:node` sets it.

|  | adapter | writes to | who uses it |
|---|---|---|---|
| `npm run build` | netlify | `build/` + `.netlify/` | the deploy |
| `npm run build:node` | node | `build-node/` | `check:layout`, `check:interaction` |

The two gates spawn a real long-running server, which a bundle of serverless
functions is not — so they set the variable themselves and build before they run.
That means `npm run check:layout` can no longer measure a stale build, which it
previously could.

**The out directories are separate on purpose.** Two adapters writing `build/`
would mean whichever ran last decided what a gate was testing: a build-order bug
that presents as a flaky gate.

Nothing about the app differs between them. There is no `prerender`, no
`ssr = false` and no `csr = false` anywhere in `src/routes`, so every route is
server-rendered per request either way — which is what the whole date rule depends
on, since `new Date()` in a `load` is the one answer to "what is today".

### Deploying to Netlify

`netlify.toml` at the REPO ROOT holds everything: `base = "frontend"` (the app is
not at the root), `command`, `publish`, and a pinned `NODE_VERSION`. Nothing is
configured in the dashboard, so the deploy is reproducible from a clone.

**Expected line in the build log, not a fault:**

```
Using @sveltejs/adapter-netlify
  No netlify.toml found. Using default publish directory.
```

The adapter looks for that file relative to its own working directory, which is
`frontend/`; the file has to be at the repo root because that is the only place
Netlify reads it and the only place `base` can be declared. So the adapter falls
back to its default, `build`, which is exactly what the root file declares. It
takes no `publish` option (`{ split, edge }` only). A second copy inside
`frontend/` would silence the line at the cost of two files that can drift.

**`ORIGIN` is not needed on Netlify** — see the section below. The adapter derives
the origin from the request. It IS needed for the Node build.

**Cold starts wipe the mock stores.** Netlify sleeps the function after a spell of
inactivity; waking it starts a fresh process and the stores live in that process.
So the first visit after a quiet period is slow AND arrives to an empty
appointment list. Recorded in the README, because it looks like data loss and is
not.

### `ORIGIN` is required to run the NODE build (added 2026-08-21, Phase 8)

**Serving `build-node/index.js` without `ORIGIN` set breaks every form submission
with `403 Cross-site POST form submissions are forbidden`.** This is an
adapter-node problem only; `adapter-netlify` derives its origin from the request.

`adapter-node` cannot know the public URL it is reached on, and SvelteKit's CSRF
check compares a POST's `Origin` header against the URL it thinks it is serving.
Without the variable it guesses, the guess does not match, and the POST is
refused.

Two things made this invisible until now:

- **Nothing in the app posted anything.** Home and the calendar write to
  `localStorage`. `/appointments` is the first surface with a form action, so it
  is the first POST the app has ever made.
- **The dev server is unaffected**, because Vite serves the app on the origin it
  reports. So `npm run dev` books appointments fine and only the built server
  fails — the worst possible split.

It was found by `check:interaction`, which now sets `ORIGIN` when it spawns the
server (so does `check:layout`). That is not a workaround for the gates: it is
the same variable a real deployment must set, so the gates now run the app the
way it actually has to be run.

For a real deployment, set `ORIGIN` to the public URL. Behind a reverse proxy,
`PROTOCOL_HEADER=x-forwarded-proto` and `HOST_HEADER=x-forwarded-host` are the
alternative — see the adapter-node docs. Do not reach for
`csrf: { checkOrigin: false }`; the check is the only thing standing between the
form actions and a cross-site POST, and the actions have no auth yet
(MIGRATION.md §9 defect 2).

From the repo root:

```bash
python3 scripts/check-contrast.py    # must stay 58/58
```

### The timezone sweep

**Run this after touching anything date-shaped.** It is part of the definition of
green, not an extra, and it has caught two real failures — one in a test written the
same session, one in a test that had never been swept.

```bash
cd ~/code/thrive/frontend
for tz in UTC America/Los_Angeles Asia/Tokyo Pacific/Kiritimati \
          Pacific/Midway Australia/Lord_Howe Asia/Kathmandu; do
  TZ=$tz npx vitest --run
done
```

Seven zones, UTC+14 to UTC−11, including Australia/Lord_Howe's 30-minute DST
offset. Takes about 15 seconds. Note "date-shaped" means the change OR the test:
the second failure was in a spec that predated the sweep line in TESTING.md, so the
claim that the suite was green in all seven zones had been false for weeks.

### Gotcha: stale servers

If a page looks stale or a new route 404s, something is still holding the port.
This cost real debugging time — two orphaned `node build-node/index.js` processes
made `curl` hit an old build.

```bash
lsof -ti:3000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
lsof -ti:4173 | xargs kill -9
```

---

## Toolchain notes that will bite

**This SvelteKit version ships no `svelte.config.js`.** The adapter CHOICE, the
runes setting, and the Vitest projects all live in `frontend/vite.config.ts` under
the `sveltekit()` plugin. Looking for the missing config file is a wasted ten
minutes — and note it is a choice rather than a single adapter, since 2026-08-21.

**Runes only work in `.svelte.js` / `.svelte.ts`.** A plain `.ts` file containing
`$state` compiles, runs, and is silently not reactive. Four files carry the
suffix: `overrideStore`, `userEdits`, `taskNotes`, `toast`. Import them as
`$lib/overrideStore.svelte` — extensionless `.ts`, keep the `.svelte`.

**Vitest hides stdout on passing tests.** For a diagnostic probe you need
`npx vitest --run <file> --reporter=verbose --silent=false`.

**`npm run build` writes `.svelte-kit/` and `build/`**, both gitignored. `npm run
check` runs `svelte-kit sync` first, so it works from a clean checkout.

**`npm audit` reports issues** after the `@fontsource` / `@lucide/svelte`
installs. Not chased. Nothing is in a request path yet.

---

## Scaffold provenance

Recorded so it can be reproduced or compared:

```bash
npx sv@0.17.0 create frontend --template minimal --types ts --no-add-ons --install npm
npx sv@0.17.0 add tailwindcss=plugins:none vitest=usages:unit \
  sveltekit-adapter=adapter:node --install npm
```

Then, by hand: `@fontsource/dm-sans`, `@fontsource/jetbrains-mono`,
`@lucide/svelte`, `clsx`, `tailwind-merge`.

Removed from the scaffold: `src/routes/layout.css` (replaced by `src/app.css`)
and `src/lib/vitest-examples/`.

---

## Credentials

**None.** No `.env`, no `secret.md`, no API keys, no tokens anywhere in this
repo. The only credential in play is the GitHub SSH key already on the machine.

`.gitignore` covers `.env` and `.env.*` (with `!.env.example`) ahead of the
Django backend needing them. `secret.md` does not exist and has not been needed;
if it ever is, add it to `.gitignore` and verify with
`git check-ignore secret.md` **before** the first commit that could contain it.

---

## The two browser gates need a browser (added 2026-08-21)

`npm run check:layout` drives a real Chromium to assert no route can be scrolled
further than it paints. `npm run check:interaction` drives one to press the stat
pills. They are the only parts of the toolchain with an environment requirement
beyond Node, and they share all of the behaviour described here.

```bash
cd frontend
npm run build              # both gates measure the BUILD, not the dev server
npm run check:layout
npm run check:interaction
```

**That "the BUILD, not the dev server" has one consequence worth knowing.**
`arriveAtRow` warns on a missing row behind `import.meta.env.DEV`, so the branch
is compiled out of what `check:interaction` drives and no gate covers it. To see
it you need `npm run dev`. Noted here because it is an environment fact, not a
code one.

**`playwright-core` ships no browser.** On this machine the gate uses a Chromium
already in `~/Library/Caches/ms-playwright/` from an earlier Playwright install —
it tries `chromium.launch()` first and falls back to hunting a
`chrome-headless-shell` in that cache, because the cached revision was installed
by a different Playwright version than the one in `package.json`.

**If no browser is found it SKIPS and exits 0**, printing the install command:

```bash
npx playwright install chromium
```

That is deliberate. A gate that fails for a reason unrelated to the code gets
ignored, and an ignored gate is worse than no gate because it looks like
coverage. It is not part of `npm test` and not part of `npm run build`, so a
machine without a browser is never blocked.

**Each manages its own server.** The scripts spawn `node build/index.js` — the
layout gate on port 4399, the interaction gate on 4400 — wait for it, measure, and
kill it. Nothing to start by hand — but it
does require `npm run build` to have run, and it fails with a clear message if
`frontend/build/index.js` is missing.

### The full gate set

```bash
cd frontend
npm test                              # 640 tests, Node, no jsdom
npm run check                         # svelte-check
npm run build                         # vite build, adapter-netlify (ADAPTER=node for the gates)
npm run check:layout                  # 17 targets x 3 viewports, real browser
npm run check:interaction             # 213 assertions: popovers, editing, calendar,
                                      #   booking, Ask THRIVE, the page measure
cd .. && python3 scripts/check-contrast.py   # 58 assertions, no dependencies
```
