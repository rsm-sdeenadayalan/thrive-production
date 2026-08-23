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

- `THRIVE_LLM` — `gemini` (default) or `fake`. `fake` makes `get_llm()` raise,
  which is the intended way to exercise the degraded/turn-rescue path without
  an API key; it also switches embeddings to `FakeEmbeddings` for retrieval.
- `GEMINI_API_KEY` — required when `THRIVE_LLM=gemini` (or unset). Used for
  both chat completions and embeddings (`gemini-embedding-001`).

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
uv run python manage.py eval_bots --llm fake   # deterministic, no API key
uv run python manage.py eval_bots --llm real    # needs GEMINI_API_KEY
```

It prints `PASS`/`FAIL` per case in `rsm_thrive/data/evals/faq_golden.json`
with the retrieved chunk ids, and exits non-zero on any regression — add
cases to that file as the corpus grows. A `must_refuse: false` case that
retrieves nothing fails as `no-retrieval`, which usually means the corpus is
missing material rather than the bot misbehaving.
