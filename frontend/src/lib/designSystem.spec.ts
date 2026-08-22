import { describe, expect, it } from "vitest";

/**
 * Guards for the two design-system rules nothing else enforces.
 *
 * Both rules were previously stated only in a comment at the top of `app.css`,
 * and both are the kind that decay one call site at a time:
 *
 *   1. Never hardcode a colour, size, radius or duration in a component.
 *   2. A component asks for a TREATMENT, not a font.
 *
 * Rule 2 is the one that actually broke. The two-face rule lived in prose, so
 * every call site re-decided it, and `font-mono` spread from numbers onto
 * eyebrows, view switchers, chips, tags and stream names -- until an app with
 * two faces read as though it had more. That is not a mistake anyone makes
 * once; it is a mistake a comment cannot prevent.
 *
 * Rendering is deliberately never tested in this repo (Vitest runs in Node with
 * no jsdom, matching the prototype). These are source scans instead, which is
 * the right shape anyway: the rules are about what the source is allowed to
 * say, not about what the browser does with it.
 *
 * `/swatch` is excluded throughout. It is the design system's own display page:
 * it prints hex values as text and sets code samples in mono on purpose, and
 * both are the thing it exists to do.
 */

const MARKUP = import.meta.glob<string>(["../**/*.svelte", "!../routes/swatch/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});

/*
 * TypeScript that applies a design-system class.
 *
 * `reveal.svelte.ts` adds `.thrive-arrived` to a row from JavaScript, which put a
 * treatment name outside the markup glob for the first time. A typo there is the
 * exact silent failure the vocabulary check exists to catch -- the class simply
 * does nothing and the row is never marked -- so the check has to be able to see
 * it.
 *
 * Scanned only for the vocabulary rule, not for hex or fonts: a `.ts` legitimately
 * holds neither, and `tones.ts` is a file of class strings that would make the
 * colour rule ambiguous rather than useful.
 */
const SCRIPTS = import.meta.glob<string>(["../**/*.ts", "!../**/*.spec.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const FILES = Object.keys(MARKUP);

describe("the design system's unenforced rules", () => {
  it("scans a real corpus", () => {
    // The companion assertion. Every test below asserts an ABSENCE, and an
    // absence proves nothing if the glob quietly matched nothing -- a broken
    // pattern would turn the whole file permanently green.
    expect(FILES.length).toBeGreaterThan(5);
    expect(FILES.some((path) => path.includes("shell/AppShell"))).toBe(true);
    expect(Object.values(MARKUP).join("").length).toBeGreaterThan(2000);
  });

  it("never hardcodes a colour in a component", () => {
    // app.css is the single source of truth. A hex in markup is a colour that
    // cannot be repaletted -- which is exactly what this pass would have had to
    // hunt down by hand if any existed.
    const offenders = FILES.filter((path) =>
      /#[0-9a-fA-F]{3,8}\b/.test(MARKUP[path]),
    );
    expect(offenders).toEqual([]);
  });

  it("never names a font in a component", () => {
    /*
     * The two-face rule, enforced. Components reach for `.thrive-numeric` (a
     * value) or `.thrive-eyebrow` (a small label), or they set nothing and get
     * DM Sans, which is what words should be.
     *
     * `font-mono` in a component is the specific regression this guards: it is
     * a font assertion, and choosing the face is the design system's call.
     */
    const offenders = FILES.filter((path) =>
      /\bfont-(mono|sans)\b|font-family/.test(MARKUP[path]),
    );
    expect(offenders).toEqual([]);
  });

  it("uses only treatments the design system actually defines", () => {
    /*
     * The other half of the rule above: components must not reach for a
     * `.thrive-*` class that app.css does not define. A typo here is silent --
     * an unknown class simply does nothing, so the text renders in the default
     * face and looks almost right.
     *
     * app.css itself cannot be read from here: Vite's CSS pipeline processes it
     * before `?raw` sees it, so `import.meta.glob` returns the path with empty
     * content. Probed and confirmed rather than assumed. The definitive check --
     * that app.css declares `.thrive-numeric` and `.thrive-eyebrow` and that
     * numeric carries both the mono face and tabular figures -- lives in
     * scripts/check-contrast.py, which parses app.css natively.
     *
     * What is checkable here is the call sites, against the known vocabulary.
     */
    const DEFINED = [
      "thrive-numeric",
      "thrive-eyebrow",
      "thrive-panel",
      "thrive-row",
      "thrive-checkbox",
      "thrive-strike",
      // The fit-on-one-screen mechanism. Fixed height and inside-scroll on
      // desktop, no cap on mobile -- see app.css.
      "thrive-card-body",
      // The stat pill popover's width clamp. Width only: its surface, hairline
      // and radius are utilities at the call site.
      "thrive-popover",
      // The arrival ring on a row a stat popover jumped to. Applied from
      // TypeScript, which is why SCRIPTS is scanned as well as MARKUP.
      "thrive-arrived",
    ];

    const used = new Set<string>();
    for (const source of [...Object.values(MARKUP), ...Object.values(SCRIPTS)]) {
      // The lookbehind excludes custom-property references: `AppShell` reads
      // `var(--thrive-bottomnav-height)` for the shell's rem heights, and
      // `reveal.svelte.ts` reads `--thrive-arrival-duration`. Both are tokens
      // being used correctly, not class names.
      for (const match of source.matchAll(/(?<![-\w])thrive-[a-z-]+/g)) {
        used.add(match[0]);
      }
    }

    // Non-vacuous: the sweep put `.thrive-eyebrow` on two page headers and
    // `.thrive-numeric` on SectionHeading's count, so all three must be seen.
    expect(used.has("thrive-eyebrow")).toBe(true);
    expect(used.has("thrive-numeric")).toBe(true);
    expect(used.has("thrive-panel")).toBe(true);
    // And the script glob really matched: this one exists only in a `.ts`.
    expect(used.has("thrive-arrived")).toBe(true);

    expect([...used].filter((name) => !DEFINED.includes(name)).sort()).toEqual([]);
  });
});
