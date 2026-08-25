# The retrieval corpus

Every document the FAQ bot can answer from. This directory is the corpus of
record for this repo: `ingest_corpus` reads it, and `run_playground` loads it
automatically, so a clean checkout can stand the bot up with no external
dependency.

```
crawled/   218 files  official ucsd.edu pages, crawled and fidelity-scored
canvas/      9 files  Rady Canvas material a human captured (SSO-gated), year-stamped
thrive/      1 file   how THIS app works, written here rather than crawled
```

Both are **generated output, committed on purpose** — the bot is only as good
as this corpus, so it is versioned alongside the code that reads it.

## What is in here, and what deliberately is not

`crawled/` contains only documents that scored **band A or B** on the fidelity
rubric: their Markdown was compared against the archived original byte-for-byte
and lost nothing that matters. Documents that failed a hard gate — a missing
deadline, a table that vanished in conversion, text that could not be traced to
the source — are **excluded by construction**. Feeding a known-broken
conversion to a student is the failure the whole scoring pass exists to prevent.

Also excluded, on purpose: listing/feed pages (`/channels/`, `/posts`),
date-archive blog posts (`recreation.ucsd.edu/2021/08/…` — 43 sports-club award
posts once made it into an export), and anything that is not `ucsd.edu` plus the
two labeled exceptions (`rady.instructure.com`, `rady.hosted.panopto.com`).

Each file starts with a `Source:` line. `ingest_corpus` reads it into
`Document.source_url`, which is what lets an answer cite a clickable link
instead of just a title.

`thrive/` is the one category that is WRITTEN rather than captured, and it holds
what no ucsd.edu page can: how this application itself works. It exists because
a student who asks "how do I contact Amber Hanna" wants the Appointments tab,
and nothing crawled from a university website knows that tab is there. Before
it, that exact question retrieved nothing at all and the bot refused it — the
advisor's name is in `canvas/`, but a name and an email address are not an
answer to "how do I reach them" when the app can book them a meeting.

Keep it truthful about the app as it actually behaves: it is corpus, so the bot
will state it as fact. A step that no longer matches the UI is a bot confidently
giving directions to a button that is not there.

`canvas/` files carry their cohort and academic year in the **filename** (so
every retrieved passage shows it) and a temporal stamp under **every heading**
(so a chunk about "Dress Code" cannot present July 2026 dates as upcoming). The
backend chunks per heading, which is why the stamp is repeated rather than
placed once at the top.

## Loading it

```bash
uv run python manage.py ingest_corpus rsm_thrive/data/corpus/crawled
uv run python manage.py ingest_corpus rsm_thrive/data/corpus/canvas
uv run python manage.py ingest_corpus rsm_thrive/data/corpus/thrive
uv run python manage.py ingest_corpus rsm_thrive/tests/fixtures/corpus --catalog
```

`run_playground` does all three for you. Ingest is idempotent per filename, so
re-running only refreshes. **Renaming a file creates a second document rather
than replacing one** — after a naming change, delete the stale rows:

```bash
uv run python manage.py shell -c "
from rsm_thrive.models import Document
Document.objects.filter(source__contains='<old-name-fragment>').delete()"
```

## Refreshing it (next quarter, next cohort)

The crawler that produces `crawled/` is the `pipeline/` project at the root of
this repo. It is a separate Node project (`thrive-pipeline`) and is **not part of
the running app**: no Django or SvelteKit code imports it or invokes it, and the
backend has no Node dependency. The handoff is entirely offline — the pipeline
exports markdown into this directory, and `manage.py ingest_corpus` embeds it.
Production reads the committed corpus, never the crawler.

Its fidelity score is meaningful because it converts pages with *the app's own
parsers* (`Thrive/campus-resources/src/lib/ingest/parsers/*`), so the score
measures the converter that actually ships rather than a second, different one.
Keep that import intact when moving anything around.

To refresh:

```bash
cd pipeline
npx tsx 1-crawl/discover.ts                      # re-discover (polite, cached)
npx tsx 1-crawl/inventory.ts                     # review 1-crawl/INVENTORY.md first
npx tsx 1-crawl/fetch.ts                         # archive originals (conditional GET)
npx tsx --conditions=react-server 3-convert/convert.ts
NODE_OPTIONS="--max-old-space-size=8192" npx tsx 3-convert/repair-tables.ts
npx tsx 4-score/score.ts && npx tsx 4-score/score.ts --dir md-repaired
find md md-repaired -name "* 2.md" -delete        # iCloud conflict copies

# write straight back into this directory:
npx tsx 5-report/export-corpus.ts   --out backend/rsm_thrive/data/corpus/crawled
npx tsx 5-report/export-datadump.ts --out backend/rsm_thrive/data/corpus/canvas
```

Then re-ingest here and **re-measure** — `manage.py eval_bots` (the persona probe was retired — see note below)
exists so a corpus change that costs coverage elsewhere is caught rather than
assumed. `pipeline/COVERAGE-LOOP.md` documents that loop and the numbers
from each round; `pipeline/SCORECARD.md` shows every document's score
including the ones held back and why.

## Provenance summary

- Crawl policy: `ucsd.edu` only, robots.txt obeyed, 1 req/s/host, never logs in.
  SSO-gated pages are recorded in `pipeline/BLOCKED.md` with what a human
  must do — they are never guessed at.
- Fidelity rubric: `rubric/1.2.0`, seven weighted metrics plus hard gates, all
  reproducible offline from the archived originals.
- 2026-08-24 snapshot: 423 documents scored → 218 shipped here (A 151 · B 65);
  the rest held back with reasons recorded per document.
