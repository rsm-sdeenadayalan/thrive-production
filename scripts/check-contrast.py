#!/usr/bin/env python3
"""
WCAG contrast check for the THRIVE palette.

Run before changing any colour token:

    python3 scripts/check-contrast.py

Exits non-zero if any pair fails, so it can go straight into CI once there is
one. No dependencies.

This exists because a calm palette drifts toward unreadable one token at a time.
Two regressions on 2026-08-12 were introduced *while deliberately making things
quieter*: --thrive-faint shipped at 2.36:1, under even the 3:1 a non-text icon
needs, and was then used for count text, which needs 4.5:1. Neither was visible
by eye. Both were caught here.

## It reads app.css now (2026-08-22)

Until this pass the token values were mirrored here by hand, and the docstring
said "if you change a token there, change it here" -- which is a process, not a
guarantee. A repalette is exactly the moment that process fails: 43 assertions
were checking the green palette while the app rendered navy, and the gate would
have reported 43/43 the whole time.

So the tokens are now PARSED from frontend/src/app.css. A token edited there is
checked here, and the two cannot drift. The checks below name tokens by their
CSS custom-property name, so a rename or a typo fails loudly instead of being
silently skipped.

Known limit, stated rather than hidden: `color-mix()` values are not evaluated.
Resolving them faithfully means reimplementing oklab mixing and hoping it
matches the browser's rounding -- a gate that checks a colour nobody sees is
worse than no gate. Unresolved tokens are listed in the output, and none of them
is a pair this file checks. If a checked token ever becomes a color-mix, the
lookup raises instead of guessing.

## The rule that matters when this fails

If a pair fails, THE COLOUR CHANGES, NOT THE THRESHOLD. The thresholds are WCAG,
not preference. Where a brand colour cannot meet the bar for a role -- as UC San
Diego Yellow cannot, at 1.50:1 on white -- the ROLE changes: yellow is
decoration on light surfaces and carries meaning only against navy. That is
enforced below as a ceiling, not waived.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "app.css"

AA_TEXT = 4.5
AA_NON_TEXT = 3.0

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_VAR = re.compile(r"^var\(\s*(--[A-Za-z0-9-]+)\s*\)$")


# --- reading the tokens out of app.css -------------------------------------


def _root_block(source: str) -> str:
    """The text inside the first `:root { ... }`, comments already stripped."""
    match = re.search(r":root\s*\{", source)
    if match is None:
        raise SystemExit(f"no :root block found in {CSS_PATH}")

    start = match.end()
    depth, index = 1, start
    while depth and index < len(source):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    if depth:
        raise SystemExit(f"unterminated :root block in {CSS_PATH}")
    return source[start : index - 1]


def load_declarations() -> dict[str, str]:
    source = CSS_PATH.read_text()
    # Comments first. They contain both ':' and ';' -- several of them quote
    # ratios like "3.45 cream / 3.63 card" -- so splitting before stripping
    # would invent tokens out of prose.
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)

    declarations: dict[str, str] = {}
    for declaration in _root_block(source).split(";"):
        name, separator, value = declaration.partition(":")
        if not separator:
            continue
        name = name.strip()
        if name.startswith("--"):
            declarations[name] = " ".join(value.split())
    return declarations


DECLARATIONS = load_declarations()


def _expand(hex_colour: str) -> str:
    digits = hex_colour.lstrip("#")
    if len(digits) == 3:
        digits = "".join(character * 2 for character in digits)
    return f"#{digits.lower()}"


def colour(token: str, _seen: tuple[str, ...] = ()) -> str:
    """Resolve a custom property to a literal hex, following var() chains."""
    if token in _seen:
        raise SystemExit(f"circular var() chain at {token}")
    if token not in DECLARATIONS:
        raise SystemExit(
            f"{token} is checked here but not declared in {CSS_PATH.name} -- "
            "renamed or deleted?"
        )

    value = DECLARATIONS[token]
    if _HEX.match(value):
        return _expand(value)
    if value in ("white", "#fff"):
        return "#ffffff"

    indirect = _VAR.match(value)
    if indirect:
        return colour(indirect.group(1), _seen + (token,))

    raise SystemExit(
        f"{token} resolves to `{value}`, which this gate cannot evaluate. "
        "color-mix() is deliberately not implemented -- see the module "
        "docstring. Give the token a literal hex if it needs checking."
    )


def unresolved_colour_tokens() -> list[str]:
    """Tokens that look like colours but cannot be resolved. Reported, not fatal."""
    return sorted(
        name for name, value in DECLARATIONS.items() if "color-mix" in value
    )


# --- the maths --------------------------------------------------------------


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def ratio(foreground: str, background: str) -> float:
    a, b = luminance(foreground), luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


# --- what gets checked ------------------------------------------------------
#
# Named by CSS custom property, so this list is coupled to app.css by more than
# convention. Same relationships the green palette was checked on, plus the
# yellow constraints the brand colour brought with it.

PAPER = "--thrive-bg"
WHITE = "--thrive-surface"
SUNKEN = "--thrive-sunken"

INK = "--thrive-ink"
BODY = "--thrive-body"
MUTED = "--thrive-muted"
FAINT = "--thrive-faint"

PRIMARY = "--thrive-primary"
PRIMARY_SOFT = "--thrive-primary-soft"
PRIMARY_FILL = "--thrive-primary-fill"
ON_PRIMARY_FILL = "--thrive-on-primary-fill"
ON_PRIMARY = "--thrive-on-primary"
YELLOW = "--thrive-yellow"

INDIGO = "--thrive-indigo"

ON_TRACK = "--thrive-on-track"
WATCH = "--thrive-watch"
NEEDS_HELP = "--thrive-needs-help"
URGENT = "--thrive-urgent"
CIVIC = "--thrive-civic"
LATER = "--thrive-later"

# Hairlines are decorative in this direction and deliberately NOT checked --
# nothing depends on seeing them. The exception that IS checked: control
# boundaries. A checkbox edge is the only thing saying where the control is, so
# it owes 3:1 on every surface it can sit on, including the sunken row-hover
# fill.
CONTROL_LINE = "--thrive-control-line"

# (foreground, background, label, required ratio)
CHECKS = [
    # --- Every ink tier against every surface ------------------------------
    # All three surfaces, not just two. The gap that shipped a bug last time
    # was checking paper and card and stopping, when sunken is where the
    # failure lived -- and sunken matters more, not less, because it is the row
    # hover fill rather than an occasional well.
    (INK, PAPER, "ink on cream", AA_TEXT),
    (INK, WHITE, "ink on card", AA_TEXT),
    (INK, SUNKEN, "ink on sunken", AA_TEXT),
    (BODY, PAPER, "body on cream", AA_TEXT),
    (BODY, WHITE, "body on card", AA_TEXT),
    (BODY, SUNKEN, "body on sunken", AA_TEXT),
    (MUTED, PAPER, "muted on cream", AA_TEXT),
    (MUTED, WHITE, "muted on card", AA_TEXT),
    (MUTED, SUNKEN, "muted on sunken", AA_TEXT),
    # --- The accent: UC San Diego navy --------------------------------------
    (PRIMARY, WHITE, "navy text on card", AA_TEXT),
    (PRIMARY, PAPER, "navy text on cream", AA_TEXT),
    (PRIMARY, SUNKEN, "navy text on sunken", AA_TEXT),
    (ON_PRIMARY, PRIMARY, "white on navy fill", AA_TEXT),
    (PRIMARY, PRIMARY_SOFT, "navy on primary-soft", AA_TEXT),
    (ON_PRIMARY_FILL, PRIMARY_FILL, "ink on primary-fill", AA_TEXT),
    # --- Yellow: the accent, and the one surface it is legible on -----------
    # Against navy it is a real graphic. Against anything light it is not, and
    # the ceilings below are what stop it being promoted to one.
    (YELLOW, PRIMARY, "yellow accent on navy", AA_NON_TEXT),
    # --- Indigo, the reserved "you are here" -------------------------------
    (INDIGO, WHITE, "indigo marker text on card", AA_TEXT),
    (INDIGO, PAPER, "indigo marker text on cream", AA_TEXT),
    (ON_PRIMARY, INDIGO, "white on indigo fill", AA_TEXT),
    # --- Status and categorical text ---------------------------------------
    (ON_TRACK, WHITE, "on-track teal text", AA_TEXT),
    (WATCH, WHITE, "watch amber text", AA_TEXT),
    (NEEDS_HELP, WHITE, "needs-help violet text", AA_TEXT),
    (URGENT, WHITE, "urgent coral text", AA_TEXT),
    (CIVIC, WHITE, "civic plum text", AA_TEXT),
    (LATER, WHITE, "later slate text", AA_TEXT),
    # --- Solid chip fills --------------------------------------------------
    (ON_PRIMARY, URGENT, "white on urgent fill", AA_TEXT),
    (ON_PRIMARY, WATCH, "white on watch fill", AA_TEXT),
    (ON_PRIMARY, ON_TRACK, "white on on-track fill", AA_TEXT),
    (ON_PRIMARY, NEEDS_HELP, "white on needs-help fill", AA_TEXT),
    (ON_PRIMARY, CIVIC, "white on civic fill", AA_TEXT),
    (ON_PRIMARY, LATER, "white on later fill", AA_TEXT),
    # --- Non-text graphics -------------------------------------------------
    (PRIMARY, PAPER, "focus ring on cream", AA_NON_TEXT),
    (PRIMARY, WHITE, "ring around primary-fill", AA_NON_TEXT),
    (WATCH, WHITE, "amber dot", AA_NON_TEXT),
    (URGENT, WHITE, "coral dot", AA_NON_TEXT),
    (INDIGO, WHITE, "indigo marker dot", AA_NON_TEXT),
    # --- Control boundaries: the one exception to "hairlines are decorative"
    # WCAG 1.4.11.
    (CONTROL_LINE, PAPER, "control boundary on cream", AA_NON_TEXT),
    (CONTROL_LINE, WHITE, "control boundary on card", AA_NON_TEXT),
    (CONTROL_LINE, SUNKEN, "control boundary on sunken", AA_NON_TEXT),
    # --- faint as decorative text ------------------------------------------
    (FAINT, PAPER, "faint on cream", AA_NON_TEXT),
    (FAINT, WHITE, "faint on card", AA_NON_TEXT),
    (FAINT, SUNKEN, "faint on sunken", AA_NON_TEXT),
]

# Ceilings, not floors. These assert a token stays BELOW a ratio, which is how
# "decorative only" stops being a comment nobody reads.
#
# faint: if it ever clears the text bar, someone will put words in it and get
# away with it.
#
# yellow: the brand colour is 1.50:1 on card. Held under the NON-TEXT bar, not
# just the text bar, because the tempting misuse is not a yellow word -- it is a
# yellow indicator. If a future tweak brightens the surfaces or darkens the
# yellow enough to clear 3:1, that is a design decision that should be made on
# purpose, and this is what forces the conversation.
# (foreground, background, label, must stay under)
CEILINGS = [
    (FAINT, PAPER, "faint stays decorative on cream", AA_TEXT),
    (FAINT, WHITE, "faint stays decorative on card", AA_TEXT),
    (FAINT, SUNKEN, "faint stays decorative on sunken", AA_TEXT),
    (YELLOW, PAPER, "yellow stays decorative on cream", AA_NON_TEXT),
    (YELLOW, WHITE, "yellow stays decorative on card", AA_NON_TEXT),
    (YELLOW, SUNKEN, "yellow stays decorative on sunken", AA_NON_TEXT),
]


# --- structural assertions --------------------------------------------------
#
# Not contrast, but the same job: things components depend on that nothing else
# checks. The Svelte-side guard in src/lib/designSystem.spec.ts enforces that no
# component names a font directly and that every `.thrive-*` class it uses is in
# the known vocabulary -- but it cannot read app.css, because Vite's CSS pipeline
# processes the file before `?raw` sees it and the glob comes back empty.
# Probed and confirmed, not assumed. So the "does app.css actually define it"
# half lands here, in the one checker that already parses this file.

# (pattern, description)
REQUIRED_CSS = [
    (r"\.thrive-numeric\s*\{", "`.thrive-numeric` is declared"),
    (r"\.thrive-eyebrow\s*\{", "`.thrive-eyebrow` is declared"),
    (
        # Retired 2026-08-24: a value sitting mid-sentence in running copy
        # ("in 3 days", "9:30 AM") switching to a second typeface was itself
        # the "fonts are all non-uniform" complaint. `.thrive-numeric` is DM
        # Sans now, same as everything else -- see the ladder note in app.css.
        # Tabular figures (checked below) are what the class was actually for.
        r"\.thrive-numeric\s*\{[^}]*var\(--font-sans\)",
        "`.thrive-numeric` uses the sans face",
    ),
    (
        r"\.thrive-numeric\s*\{[^}]*tabular-nums",
        "`.thrive-numeric` sets tabular figures",
    ),
    (
        r"\.thrive-eyebrow\s*\{[^}]*var\(--font-sans\)",
        "`.thrive-eyebrow` uses the sans face",
    ),
    # The fit-on-one-screen contract. Each of these is a property Home's grid
    # depends on, and each is silent when broken: the page still renders, it just
    # stops fitting or starts moving when a card expands.
    (r"--thrive-card-body-cap:", "the card height cap is a token"),
    (
        r"\.thrive-card-body\s*\{",
        "`.thrive-card-body` is declared",
    ),
    (
        r"@media\s*\(width\s*>=\s*64rem\)\s*\{\s*\.thrive-card-body\s*\{[^}]*height:\s*var\(--thrive-card-body-cap\)",
        "the cap applies as a FIXED height at 64rem, so the grid cannot move",
    ),
    (
        r"@media\s*\(width\s*>=\s*64rem\)\s*\{\s*\.thrive-card-body\s*\{[^}]*overflow-y:\s*auto",
        "the capped card scrolls inside rather than clipping",
    ),
    # A browser-free backstop for the bug `scripts/check-layout.mjs` measures.
    # That gate is the real one -- it drives a browser and would catch a NEW
    # source of phantom scroll, which a regex cannot. This catches the specific
    # regression of someone deleting the containment while tidying, on a machine
    # with no browser installed, which is the likeliest way it would come back.
    (
        r"@media\s*\(width\s*>=\s*64rem\)\s*\{\s*\.thrive-card-body\s*\{[^}]*contain:\s*paint",
        "the capped card contains its paint, so overflow cannot leak to the page",
    ),
]


def check_structure(source: str) -> int:
    print()
    print("type treatments")
    print("-" * 68)
    failures = 0
    for pattern, description in REQUIRED_CSS:
        passed = re.search(pattern, source) is not None
        failures += not passed
        print(f"{description:<55}{'PASS' if passed else 'FAIL':>13}")
    return failures


def main() -> int:
    print(f"reading tokens from {CSS_PATH.relative_to(CSS_PATH.parents[2])}")
    print()
    print(f"{'pair':<38}{'ratio':>9}{'need':>8}   result")
    print("-" * 68)

    failures = 0
    for foreground, background, label, required in CHECKS:
        measured = ratio(colour(foreground), colour(background))
        passed = measured >= required
        failures += not passed
        print(
            f"{label:<38}{measured:>8.2f}:1{required:>7.1f}+   "
            f"{'PASS' if passed else 'FAIL'}"
        )

    print("-" * 68)
    for foreground, background, label, ceiling in CEILINGS:
        measured = ratio(colour(foreground), colour(background))
        passed = measured < ceiling
        failures += not passed
        print(
            f"{label:<38}{measured:>8.2f}:1{ceiling:>7.1f}-   "
            f"{'PASS' if passed else 'FAIL'}"
        )

    failures += check_structure(re.sub(r"/\*.*?\*/", "", CSS_PATH.read_text(), flags=re.DOTALL))

    total = len(CHECKS) + len(CEILINGS) + len(REQUIRED_CSS)
    print("-" * 68)
    print(f"{total - failures}/{total} pass")

    skipped = unresolved_colour_tokens()
    if skipped:
        print()
        print(f"not evaluated ({len(skipped)} color-mix tokens, none checked above):")
        for name in skipped:
            print(f"  {name}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
