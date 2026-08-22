# frontend

The THRIVE SvelteKit app. See the repo root `README.md` for the monorepo layout
and `MIGRATION.md` for the port spec.

## Stack

SvelteKit · Svelte 5 (runes) · TypeScript strict · Vite · `adapter-node` ·
Tailwind v4 · Vitest · `@fontsource` for self-hosted fonts.

Runes mode is forced for everything outside `node_modules`, and the adapter is
configured in `vite.config.ts` — this SvelteKit version has no
`svelte.config.js`.

No `shadcn-svelte` and no `bits-ui` yet. `MIGRATION.md` §4 lists the Radix
primitives that will need equivalents, and notes that only two of the nine
vendored shadcn files in the Next app were ever actually reachable.

## Commands

```bash
npm install
npm run dev      # dev server
npm run build    # production build
npm run preview  # serve the build
npm run check    # svelte-check against tsconfig
npm test         # vitest, once
npm run test:unit  # vitest, watch
```

Vitest is configured for `unit` usage only — Node environment, no jsdom. That
matches the Next app, where all 83 tests were pure logic and rendering was
deliberately never tested. Component testing is a later decision, not an
oversight.

## Structure

```
src/
├── app.css      the design system. Single source of truth.
├── app.html     document shell. Carries the light-only meta tags.
├── lib/         shared code. Empty except the favicon.
└── routes/
    ├── +layout.svelte   imports app.css
    ├── +page.svelte     placeholder
    └── swatch/          THROWAWAY. Delete before Release 1.
```

## The design system

`src/app.css`, ported from the Next app's `src/app/globals.css`. Three layers:
raw `--thrive-*` tokens, shadcn semantic vars remapped onto them, then
`@theme inline` exposing both as Tailwind utilities.

The rules that matter are in the root `README.md`. The one worth repeating here,
because it is the easiest to break by accident: **the 1px decorative hairline
and the 1.5px control boundary are separate concepts carried by separate
tokens.** `border-line` is the hairline, `border-line-strong` is the control
boundary *colour only* — the 1.5px width comes from
`--thrive-control-stroke`, and the alias does not bring it along.

Two things from the Next file were deliberately not ported, both dead there:
the two shadow tokens and `.thrive-priority-label`. Both are commented in place
in `app.css` with the reason.
