# `program/` — Rady program material, converted by hand

Source: the **Rady Graduate Program Schedules and Resources** Drive folder,
<https://drive.google.com/drive/folders/1NkOVx60spVY31IHWZ7KWlGXBiXLL6Xk6>
(Google sign-in with a UCSD account required — see the wayfinding document in
this directory).

Unlike `crawled/`, these are **not** crawler output. The source files are PDFs
whose content is a four-column quarter grid, and `pypdf` reads such a grid
across rows rather than down columns: the raw extraction interleaves all four
quarters into one run of text, so a chunk would claim MGTA 454 is a Summer
course. The markdown here was therefore written from the PDFs by hand and is
checked by `scripts/gen_lean.py`-style arithmetic guards: every quarter's course
rows must sum to that quarter's stated unit total, and the quarters must sum to
50.

## What is here, and what is deliberately not

Only the plans for cohorts that are **still enrolled** as of August 2026:

- 11-month, MSBA 2027 cohort (Summer 2026 → Spring 2027)
- 17-month starting Summer 2026 (→ Fall 2027)
- 17-month starting Summer 2025 (→ Fall 2026, final quarter)

Left in Drive on purpose:

- Plans for cohorts that have already graduated (the 2023 and 2024 starts, the
  2025 11-month, the 2024 Flex part-time). Near-duplicate course grids compete
  with each other in retrieval, and a student asking "what do I take in Fall"
  should not get a sequence that expired.
- Plans for the other Rady graduate programs (EMBA, Full-Time MBA,
  FlexEvening/FlexWeekend, MPAc, MQF, MFin). THRIVE is the MSBA hub; an EMBA
  course sequence returned to an MSBA student is a wrong answer, not a bonus.

## Writing rules these files follow

Both rules exist because breaking them was measured to do damage.

1. **Every chunk must be readable alone.** Chunking is heading-aware, so each
   `#` section becomes its own chunk and is retrieved without its neighbours. A
   section headed `Fall 2026` that does not also name the program variant and
   the cohort can be returned to a student on a different plan as if it were
   theirs. Each heading therefore carries the plan label.

2. **Never repeat the degree requirement.** The 50-unit / 22-core / 28-elective
   requirement is identical across every plan. Stating it in each one produced
   ~12 chunks saturated with "MSBA", "quarter" and "units" — the vocabulary of
   "What does the MSBA cost per quarter and when is payment due?" — which
   outranked the Rady Registration Fees chunk holding the $1,571 figure on
   cosine (0.68 vs 0.59) and broke the `msba-per-unit-tuition` golden case. The
   requirement is stated once, in the wayfinding document.

Adding files here needs no code change: `run_playground` discovers every
subdirectory of `data/corpus/`. Re-ingest with

    uv run python manage.py ingest_corpus rsm_thrive/data/corpus/program

and re-run `manage.py eval_bots` afterwards — dense new material competes for a
fixed `top_k`, so check what it displaced.
