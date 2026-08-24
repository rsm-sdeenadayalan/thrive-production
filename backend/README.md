# rsm-django-thrive

The Django backend component for THRIVE. Not started yet — the design it
implements is `../docs/specs/2026-08-21-thrive-backend-design.md`.

Will contain:

- `rsm_thrive/` — Django app: models, the `/msba-brain/api/thrive/` API,
  Celery tasks (Canvas sync, corpus ingestion, job pipeline), chatbot
  services, appointment side effects (Zoom, ICS email)
- `deploy/` — LaunchDaemon plists, Caddy snippet, sync-to-platform scripts

Developed here; deployed by installing into the `rsm-guild-ai-brain`
platform checkout on the server (branch `feat/msba-brain`).

## Chatbots: corpus, LLM backend, and eval

The three destination bots (`resources`/FAQ, `career`, `courses`/electives)
answer from an ingested corpus of retrieved passages plus an LLM. Two knobs
control the backend:

- `THRIVE_LLM` — `tritonai` (default) or `fake`. `fake` makes `get_llm()`
  raise, which is the intended way to exercise the degraded/turn-rescue path
  without an API key; it also switches embeddings to `FakeEmbeddings` for
  retrieval.
- `TRITONAI_API_KEY` — required when `THRIVE_LLM=tritonai` (or unset). Used
  for both chat completions (`TRITONAI_MODEL`, default
  `claude-sonnet-4-6`) and embeddings (`TRITONAI_EMBED_MODEL`). Get a key
  from https://tritonai-api.ucsd.edu/ with your UCSD login — this may
  require campus network access (or VPN) off-campus. `THRIVE_LLM=fake` is
  unchanged for tests and needs no key. Copy `backend/.env.example` to
  `backend/.env` and fill in the key for local dev (auto-loaded by
  `config/settings.py`).

Ingest a corpus directory (`.pdf`/`.md`/`.txt`) and/or the course catalog:

```bash
uv run python manage.py ingest_corpus path/to/corpus --catalog
```

This is idempotent per source (`file:<name>` / `catalog:<code>`), so re-runs
just refresh chunks — safe to schedule as a cron once F5 adds Celery. The repo
carries only a small fixture corpus at
`rsm_thrive/tests/fixtures/corpus/`; the real syllabus PDFs and the program
handbook live outside the repo (see the spec's deferred-work notes) and get
ingested the same way, locally and on the server.

Run the golden FAQ eval against whatever corpus is ingested:

```bash
THRIVE_LLM=fake uv run python manage.py eval_bots --llm fake   # deterministic, no API key
uv run python manage.py eval_bots --llm real                   # needs TRITONAI_API_KEY
```

`THRIVE_LLM=fake` is required alongside `--llm fake`: without it, retrieval
still instantiates `TritonAiEmbeddings` and needs an API key, even though the
bot's own LLM calls are faked.

It prints `PASS`/`FAIL` per case in `rsm_thrive/data/evals/faq_golden.json`
with the retrieved chunk ids, and exits non-zero on any regression — add
cases to that file as the corpus grows. A `must_refuse: false` case that
retrieves nothing fails as `no-retrieval`, which usually means the corpus is
missing material rather than the bot misbehaving. The shipped golden set is
calibrated to a policy-only corpus (the seeded handbook fixture); run against
a larger mixed corpus (e.g. the fixture plus `--catalog`) and fake-embedding
retrieval dilutes, so several cases fail by design — run the eval against the
corpus the goldens target, or grow/tune the goldens as the corpus grows.

## Jobs: ingest, sources, and match reports

Job search (`GET /api/thrive/jobs?q=`), a job detail view
(`GET /api/thrive/jobs/<id>`), an LLM match report
(`POST /api/thrive/jobs/<id>/report`), and resume upload
(`POST /api/thrive/resume/upload`) round out the career surface. Same two
knobs as the chatbots — `THRIVE_LLM=fake`/`tritonai` and `TRITONAI_API_KEY` —
govern both endpoints: `fake` makes `get_llm()` raise, so `job_report` and
`resume_upload` fail honest with a `503 llm_unavailable` rather than a silent
or fabricated result, and switches embeddings to `FakeEmbeddings` for
ranking/ingestion. Switching `THRIVE_LLM` (`fake` ↔ real) — or switching
embedding backends generally, e.g. after correcting `TRITONAI_EMBED_MODEL` —
changes embedding dimensions, so re-run `ingest_corpus`/`ingest_jobs` after
switching — otherwise ranking/retrieval silently degrades (a dim-mismatch
warning is logged, but postings/chunks keep their stale, wrong-dimension
embeddings until re-ingested).

**Sources** (`rsm_thrive/services/jobs/sources.py`) sit behind one `JobSource`
ABC (`fetch() -> list[dict]`):

- `GreenhouseSource` / `LeverSource` — public, keyless JSON boards
  (`boards-api.greenhouse.io`, `api.lever.co`), configured per company in
  `rsm_thrive/data/jobs/companies.json`.
- `FakeJobSource` — an in-memory source for tests and offline seeding; takes
  the same row shape the real sources normalize to.
- An aggregator source (Adzuna/JSearch) slots in later behind the same ABC
  once a free API key exists (backlog).

**Ingest** (`ingest_from` in `rsm_thrive/services/jobs/ingest.py`) is
idempotent per `(source, external_id)`: it fetches each configured source,
upserts postings, recomputes `skills` (`services/jobs/skills.py`,
vocabulary in `rsm_thrive/data/jobs/skills_vocab.json`), embeds title+description
for ranking, and deactivates postings from sources that succeeded this run
but weren't seen (stale expiry). A source that fails to fetch is skipped —
its existing postings are left untouched rather than deactivated.

```bash
uv run python manage.py ingest_jobs                    # real boards, needs TRITONAI_API_KEY for embeddings
THRIVE_LLM=fake uv run python manage.py ingest_jobs     # real boards, fake (deterministic) embeddings
```

Seed postings without any network access — useful for local smoke and demos —
by calling `ingest_from` directly with a `FakeJobSource`:

```bash
THRIVE_LLM=fake uv run python manage.py shell -c "
from rsm_thrive.services.jobs.ingest import ingest_from
from rsm_thrive.services.jobs.sources import FakeJobSource
from rsm_thrive.services.embeddings import get_embeddings
rows = [{'external_id': '1', 'title': 'Data Analyst', 'company': 'Acme',
         'location': 'Remote', 'url': 'https://example.com/1',
         'description': 'SQL, Python, and Tableau reporting.',
         'posted_at': None}]
print(ingest_from([FakeJobSource(rows)], embeddings=get_embeddings()))
"
```

`companies.json` is a starter list of MSBA-target employers' Greenhouse/Lever
board slugs — expand it over time, and correct or drop any slug that starts
404ing (boards get renamed or migrate off the platform; e.g. Netflix's public
Lever board no longer resolves and was dropped rather than guessed at). F5
schedules `ingest_jobs` as a nightly Celery task; the command's idempotency is
what makes that safe to run unattended.

Search ranks by cosine similarity between the resume embedding and each
posting's embedding, blended with skill overlap
(`rsm_thrive/services/jobs/search.py`); with no current resume it falls back
to recency ordering and the response's `profileAvailable` is `false`. The
role benchmark (top skills by share, for a title) is portable icontains
filtering today — an F5 swap inside `_matching_postings` moves it to
Postgres full-text search once the corpus outgrows that.

Resume upload is PDF-only (`pypdf` text extraction; a scanned/image-only PDF
comes back `400 unreadable_resume` before any LLM call) and DOCX support is
deferred (`python-docx` is a small add when wanted). A match report is cached
per `(user, posting, resume_version)` — re-requesting it after a resume
change bypasses the cache since the version changed, but repeat requests
against the same resume version hit the cache instead of re-billing the LLM.
