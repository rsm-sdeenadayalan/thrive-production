# Integrating Yug's routed `courses` surface into production

**Date:** 2026-09-07
**Status:** Design, awaiting review
**Author:** Shankar (with Claude)

## Goal

Port the full current bot line from `rsm-ygadhiya/Thrive-Chatbots` (`main` at
`bcc3764`) into `rsm-sdeenadayalan/thrive-production` (`main` at `fed7bd3`),
then deploy to the live site at `https://rsm-vnijs.ucsd.edu/thrive/`.

The change is confined to the **`courses` chat surface**. FAQ, career, and the
job-search tab are untouched.

## Background

The two repositories are forks of the same THRIVE application (identical
top-level README) but have **unrelated git histories** — `git merge-base`
returns nothing. Merge and cherry-pick across them are therefore impossible;
the port is done file-by-file.

Yug's line replaced the internals of the `courses` bot. In `views/chat.py` the
only wiring change is:

```python
# was:  from rsm_thrive.services.bots import ... answer_electives
#       reply = answer_electives(llm, conversation, question, history)
# now:  from rsm_thrive.services.orchestrator import answer as answer_courses
#       reply = answer_courses(llm, conversation, question, history)
```

`orchestrator.answer` is a router-classified dispatcher that replaces three
older mechanisms: the regex in `grounded_course_advisor`, the interview state
machine in `planner.next_intake_step`, and the `if`-chain in
`bots.answer_electives`. Production's grounded advisor (merged in commit
`9522217`) is **superseded** by the orchestrator and is retired, not run in
parallel.

## What the port includes

### New capabilities
- Free-text routed conversation instead of a four-step interview.
- Bots run their own web search and label web-sourced answers unofficial when
  the corpus has nothing (keyless DuckDuckGo by default).
- Catalog rebuilt from the Drive markdown; a "what courses do you have" answer
  broken down by programme; FAQ corpus cleaned of syllabi that had swamped it.
- Per-turn feedback and trace instrumentation.

### File inventory

**Copy-new** (adopt Yug's file wholesale — absent in production):
- `backend/rsm_thrive/services/{orchestrator,router,situation,skill_match,websearch}.py`
- `backend/rsm_thrive/views/{feedback,traces}.py`
- `backend/rsm_thrive/migrations/0024_turnfeedback_alter_chatturnlog_options_and_more.py`,
  `0025_backfill_turn_log_provenance.py`, `0026_plannersession_situation.py`,
  `0027_plannersession_asked.py`
- Yug's new backend test files (adversarial, orchestrator, websearch,
  situation, skill_match, quarter_load, long_conversations, conversation_repair,
  catalog_build, careers_and_coverage, hundred_jobs, instrumentation,
  plan_sweep, switching_chats, uncurated_roles).
- Model file(s) under `backend/rsm_thrive/models/` carrying the new
  `TurnFeedback` model and the `ChatTurnLog` / `PlannerSession` fields.

**Merge-shared** (keep production's content, layer Yug's changes in):
- `backend/rsm_thrive/views/chat.py` — one import + one call.
- `backend/rsm_thrive/urls.py` — add the feedback and traces routes.
- `backend/config/settings.py` — add `THRIVE_SEARCH` and `THRIVE_SEARCH_API_KEY`.
- `backend/rsm_thrive/services/{bots,retrieval,role_lookup,electives,planner,bundles}.py`
  — preserve production's career/FAQ/jobs code; take Yug's courses-path changes.
- `backend/.env.example` — add the search knobs.
- `backend/uv.lock` — new backend dependencies.
- Frontend ask surface: `frontend/src/lib/ask.ts`,
  `frontend/src/lib/components/ask/{ChatWindow,AskHistory}.svelte`,
  `frontend/src/lib/{messages.ts,data/types.ts,data/api/providers.ts}`,
  `frontend/src/routes/ask-sync/+server.ts`, `frontend/src/app.css`, and the
  matching `.spec.ts` files. Merged, since production's frontend has diverged.

**Data dependency** (in scope — the bots read it):
- `backend/rsm_thrive/data/` catalog and corpus (128 files): expanded catalog,
  re-ingested syllabi, cleaned FAQ corpus.

**Out of scope, untouched:**
- `backend/rsm_thrive/services/jobs/`, resume ranking, `views/jobs.py`.
- `pipeline/` (the corpus generator), `scripts/`, `docs/upstream/`.
- All frontend outside the `ask` surface.

## Database migrations

The shared migrations `0001`–`0023` are **byte-identical** between the repos, so
the live database schema through `0023` already matches what Yug's new
migrations expect. Yug's `0024`–`0027` stack cleanly on top; no renumbering.

They are additive and low-risk:
- `0024` — create `TurnFeedback` table; alter `ChatTurnLog` options + add
  provenance fields.
- `0025` — data migration backfilling turn-log provenance.
- `0026` — `PlannerSession.situation` (`JSONField`, nullable).
- `0027` — `PlannerSession.asked` (`JSONField`, default `list`).

**The deploy must run `python manage.py migrate`.** Vincent's runbook omits it;
without it the new bots fail at runtime.

## Configuration and dependencies

- `uv sync` installs the new backend packages from the merged `uv.lock`.
- New env: `THRIVE_SEARCH` (default `duckduckgo`, keyless — nothing required)
  and optional `THRIVE_SEARCH_API_KEY`.
- Unchanged deploy requirement: `THRIVE_LLM=tritonai` with `TRITONAI_API_KEY`,
  which the live server already runs. `codex` is local-dev only.

## Verification — local only

On the Mac, before anything touches the live site:
1. `uv sync` in `backend/`.
2. `python manage.py migrate` against a local SQLite DB.
3. Full backend test suite green (`python manage.py test` / pytest as the repo
   uses), including Yug's new suites.
4. Local dev run driving the `courses` bot through: a free-text question, a
   plan build and a swap, and a web-search fallback where the corpus is empty.
5. Frontend `npm ci` and `THRIVE_BASE_PATH=/thrive npm run build:node` succeed.

Any red gate stops the deploy.

## Deploy runbook (augments Vincent's)

Push `integrate-yug-courses`, review, merge to `main`, then on `rsm-vnijs`:

```
cd ~/thrive
git pull --ff-only
cd ~/thrive/backend
/Users/sdeenadayalan/.local/bin/uv sync
python manage.py migrate            # ← added; not in Vincent's runbook
cd ~/thrive/frontend
npm ci
THRIVE_BASE_PATH=/thrive npm run build:node
sudo /usr/local/sbin/thrivectl restart
sudo /usr/local/sbin/thrivectl health
```

Deploy at a low-traffic time; confirm `thrivectl health` after.

## Rollback

Record the current `main` SHA before merging. If health fails after deploy:
`git reset --hard <prev-sha>`, `uv sync`, rebuild frontend, `thrivectl restart`.
The migrations are additive (new table + nullable/defaulted fields), so they are
safe to leave applied after a code rollback.

## Risks and open questions

- **Merge-shared conflicts in `bots.py` / `planner.py` / `retrieval.py`.** Both
  lines edited these. The merge must preserve production's career, FAQ, and jobs
  code while adopting Yug's courses-path behavior. This is the main hand-work.
- **Frontend divergence.** Production's `ask` surface is ahead of Yug's in some
  respects; the merge takes Yug's new interaction affordances without regressing
  production's layout and auth hooks.
- **Web search at runtime.** DuckDuckGo keyless is the default; confirm it is
  reachable from `rsm-vnijs` egress, else set `THRIVE_SEARCH=none` or a keyed
  provider.
- **Push access.** The working checkout uses the SSH remote; confirm push works
  (GitHub CLI is not authenticated).
