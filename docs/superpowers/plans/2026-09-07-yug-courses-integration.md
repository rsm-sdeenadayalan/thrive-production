# Yug Courses-Surface Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the current `courses` bot line from `rsm-ygadhiya/Thrive-Chatbots` into `thrive-production` and deploy it to `https://rsm-vnijs.ucsd.edu/thrive/`.

**Architecture:** The two repos are forks with unrelated git histories, so the port is file-level, not a merge. Yug's tree is available in the working repo as ref `refs/yug/main` (`bcc3764`). New files are taken wholesale; files both lines edited are merged so production's FAQ/career/jobs code survives. Yug's own test suites are the acceptance gate at each step. Only the `courses` surface changes.

**Tech Stack:** Django (backend, app `rsm_thrive`), pytest + pytest-django (`DJANGO_SETTINGS_MODULE=config.settings`), uv for Python deps, SvelteKit + adapter-node (frontend), TritonAI (`claude-sonnet-4-6`) in production and `THRIVE_LLM=fake` in tests.

**Spec:** `docs/specs/2026-09-07-yug-courses-integration-design.md`

## Global Constraints

- Work only on branch `integrate-yug-courses` (already created off `main` `fed7bd3`).
- Yug's tree is ref `refs/yug/main`; production `main` is `origin/main`. Pull Yug files with `git checkout refs/yug/main -- <path>`.
- NEVER touch: `backend/rsm_thrive/services/jobs/`, `views/jobs.py`, resume code, `pipeline/`, `scripts/`, `docs/upstream/`, or any frontend outside `frontend/src/lib/ask.ts`, `frontend/src/lib/components/ask/`, `frontend/src/lib/messages.ts`, `frontend/src/lib/data/types.ts`, `frontend/src/lib/data/api/providers.ts`, `frontend/src/routes/ask-sync/`, `frontend/src/app.css`.
- All backend test commands run from `backend/`. Deterministic runs use `THRIVE_LLM=fake`.
- Production deploy requires `THRIVE_LLM=tritonai` + `TRITONAI_API_KEY`; `codex` is local-dev only.
- Migrations are additive; do not renumber. The deploy MUST run `python manage.py migrate`.
- Commit after every green step. Verification is local only; nothing touches the live site before Task 10.

---

### Task 1: Setup and dependencies

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock`

**Interfaces:**
- Produces: a synced local environment where `uv run pytest` executes, and the current production test suite passes as a baseline.

- [ ] **Step 1: Confirm the working branch and Yug ref**

Run: `git branch --show-current` (expect `integrate-yug-courses`) and `git rev-parse --short refs/yug/main` (expect `bcc3764`). If the ref is missing: `git fetch "../../Codex/thrive-chatbots-source" 'bcc3764695cbd88a18d0352ebd35e4dce9917740:refs/yug/main'`.

- [ ] **Step 2: Establish the baseline**

Run: `cd backend && uv sync && THRIVE_LLM=fake uv run pytest -q`
Expected: current suite passes. Record the count; this is the pre-port baseline.

- [ ] **Step 3: See which dependencies Yug adds**

Run: `git diff origin/main..refs/yug/main -- backend/pyproject.toml`
Add every dependency line Yug introduced (in the `dependencies` and any dev/test groups) to `backend/pyproject.toml`, keeping production's existing entries. Do not remove production-only deps.

- [ ] **Step 4: Lock and sync**

Run: `cd backend && uv lock && uv sync`
Expected: lock resolves; `uv.lock` now includes Yug's new packages plus production's.

- [ ] **Step 5: Re-run the baseline suite**

Run: `cd backend && THRIVE_LLM=fake uv run pytest -q`
Expected: still passes (new deps installed, nothing wired yet).

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "deps: add Yug courses-surface backend dependencies"
```

---

### Task 2: Catalog and corpus data

**Files:**
- Create/Modify: `backend/rsm_thrive/data/catalog/**`, `backend/rsm_thrive/data/corpus/**` (from `refs/yug/main`)

**Interfaces:**
- Produces: the expanded catalog and cleaned corpus on disk plus an ingested index, which every courses service reads.

- [ ] **Step 1: List the data files Yug changed**

Run: `git diff --stat origin/main..refs/yug/main -- backend/rsm_thrive/data/`
Confirm all paths are under `data/` (catalog + corpus). None should be under `jobs/`.

- [ ] **Step 2: Bring the data in**

Run: `git checkout refs/yug/main -- backend/rsm_thrive/data/catalog backend/rsm_thrive/data/corpus`

- [ ] **Step 3: Re-ingest the corpus and catalog**

Run:
```bash
cd backend
THRIVE_LLM=fake uv run python manage.py ingest_corpus --catalog
for d in rsm_thrive/data/corpus/*/; do THRIVE_LLM=fake uv run python manage.py ingest_corpus "$d"; done
```
Expected: ingest completes without error; chunk counts print.

- [ ] **Step 4: Sanity-check retrieval against the new corpus**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_retrieval.py -q`
Expected: passes (bring Yug's version of this test in Task 5 if it fails on new expectations; if so, defer this assertion to Task 5 and note it).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive/data/catalog backend/rsm_thrive/data/corpus
git commit -m "data: expanded catalog and cleaned corpus from Yug's line"
```

---

### Task 3: Models and migrations

**Files:**
- Modify: `backend/rsm_thrive/models/chat.py` (TurnFeedback, ChatTurnLog fields), `backend/rsm_thrive/models/academic.py` or wherever `PlannerSession` is defined (`situation`, `asked`)
- Create: `backend/rsm_thrive/migrations/0024_turnfeedback_alter_chatturnlog_options_and_more.py`, `0025_backfill_turn_log_provenance.py`, `0026_plannersession_situation.py`, `0027_plannersession_asked.py`

**Interfaces:**
- Produces: `TurnFeedback` model; `ChatTurnLog` provenance fields; `PlannerSession.situation` (JSONField, nullable) and `.asked` (JSONField, default list). Later tasks' services and views depend on these.

- [ ] **Step 1: Find where the changed models live**

Run: `grep -rln "class PlannerSession\|class ChatTurnLog\|class TurnFeedback" backend/rsm_thrive/models/` against both trees: `git show refs/yug/main:backend/rsm_thrive/models/chat.py | grep -n "class "`. Identify the exact model files Yug changed with `git diff --stat origin/main..refs/yug/main -- backend/rsm_thrive/models/`.

- [ ] **Step 2: Bring Yug's model files and migrations**

Run:
```bash
git checkout refs/yug/main -- $(git diff --name-only origin/main..refs/yug/main -- backend/rsm_thrive/models/)
git checkout refs/yug/main -- backend/rsm_thrive/migrations/0024_turnfeedback_alter_chatturnlog_options_and_more.py \
  backend/rsm_thrive/migrations/0025_backfill_turn_log_provenance.py \
  backend/rsm_thrive/migrations/0026_plannersession_situation.py \
  backend/rsm_thrive/migrations/0027_plannersession_asked.py
```

- [ ] **Step 3: Verify the migration graph is consistent**

Run: `cd backend && THRIVE_LLM=fake uv run python manage.py makemigrations --check --dry-run`
Expected: "No changes detected" — models and migrations agree, and `0024`–`0027` depend cleanly on `0023`.

- [ ] **Step 4: Apply migrations on a local DB**

Run: `cd backend && THRIVE_LLM=fake uv run python manage.py migrate`
Expected: `0024`–`0027` apply without error (new table + nullable/defaulted fields).

- [ ] **Step 5: Commit**

```bash
git add backend/rsm_thrive/models backend/rsm_thrive/migrations
git commit -m "models: TurnFeedback, turn-log provenance, planner situation/asked"
```

---

### Task 4: New leaf services (websearch, situation, skill_match, router)

**Files:**
- Create: `backend/rsm_thrive/services/{websearch,situation,skill_match,router}.py`
- Test: `backend/rsm_thrive/tests/{test_websearch,test_situation,test_skill_match}.py` (router is covered via orchestrator + situation tests)

**Interfaces:**
- Produces: `router.classify(...)`, `websearch` provider entrypoint, `situation` helpers, `skill_match` helpers — all consumed by the orchestrator in Task 6. Use the exact signatures from Yug's files; do not rewrite them.

- [ ] **Step 1: Bring the four services and their tests**

Run:
```bash
git checkout refs/yug/main -- backend/rsm_thrive/services/websearch.py \
  backend/rsm_thrive/services/situation.py backend/rsm_thrive/services/skill_match.py \
  backend/rsm_thrive/services/router.py
git checkout refs/yug/main -- backend/rsm_thrive/tests/test_websearch.py \
  backend/rsm_thrive/tests/test_situation.py backend/rsm_thrive/tests/test_skill_match.py
```

- [ ] **Step 2: Run the leaf-service tests**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_websearch.py rsm_thrive/tests/test_situation.py rsm_thrive/tests/test_skill_match.py -q`
Expected: PASS. If an import fails for a shared helper, note the missing name; it arrives in Task 5. If truly blocked, run these tests again at the end of Task 5.

- [ ] **Step 3: Confirm no out-of-scope import crept in**

Run: `grep -nE "services\.jobs|resume" backend/rsm_thrive/services/{websearch,situation,skill_match,router}.py`
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add backend/rsm_thrive/services/{websearch,situation,skill_match,router}.py \
  backend/rsm_thrive/tests/{test_websearch,test_situation,test_skill_match}.py
git commit -m "services: add router, websearch, situation, skill_match"
```

---

### Task 5: Merge shared services (retrieval, role_lookup, electives, bundles, planner)

**Files:**
- Modify: `backend/rsm_thrive/services/{retrieval,role_lookup,electives,bundles,planner}.py`
- Test: `backend/rsm_thrive/tests/{test_retrieval,test_planner,test_bots_electives,test_quarter_load,test_conversation_repair,test_plan_sweep}.py`

**Interfaces:**
- Consumes: Task 4 services.
- Produces: the deterministic fact layer (catalog load, retrieval, planner state machine, bundle/role lookups) the orchestrator calls. Preserve every function production's career/FAQ/jobs code imports from these modules.

- [ ] **Step 1: See exactly what Yug changed in each shared service**

Run: `for f in retrieval role_lookup electives bundles planner; do echo "== $f =="; git diff origin/main..refs/yug/main -- backend/rsm_thrive/services/$f.py; done`

- [ ] **Step 2: Adopt Yug's versions, then restore any production-only symbols**

For each of the five files, take Yug's version, then check nothing production needs was dropped:
```bash
git checkout refs/yug/main -- backend/rsm_thrive/services/retrieval.py \
  backend/rsm_thrive/services/role_lookup.py backend/rsm_thrive/services/electives.py \
  backend/rsm_thrive/services/bundles.py backend/rsm_thrive/services/planner.py
```
Then, for each file, list the public functions production imports and confirm each still exists:
```bash
grep -rnE "from rsm_thrive.services.(retrieval|role_lookup|electives|bundles|planner) import|services\.(retrieval|role_lookup|electives|bundles|planner)\." backend/rsm_thrive | grep -v "/tests/"
```
For any imported name now missing from a file, re-add that function from `git show origin/main:backend/rsm_thrive/services/<file>.py`. Do not re-add courses-path logic Yug intentionally replaced.

- [ ] **Step 3: Bring Yug's tests for these modules**

Run:
```bash
git checkout refs/yug/main -- backend/rsm_thrive/tests/test_retrieval.py \
  backend/rsm_thrive/tests/test_planner.py backend/rsm_thrive/tests/test_bots_electives.py \
  backend/rsm_thrive/tests/test_quarter_load.py backend/rsm_thrive/tests/test_conversation_repair.py \
  backend/rsm_thrive/tests/test_plan_sweep.py
```

- [ ] **Step 4: Run the shared-service and planner tests**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_retrieval.py rsm_thrive/tests/test_planner.py rsm_thrive/tests/test_quarter_load.py rsm_thrive/tests/test_conversation_repair.py rsm_thrive/tests/test_plan_sweep.py -q`
Expected: PASS. Fix any dropped-symbol import error by restoring the function per Step 2.

- [ ] **Step 5: Re-run Task 4 leaf tests to confirm the layer is whole**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_websearch.py rsm_thrive/tests/test_situation.py rsm_thrive/tests/test_skill_match.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/rsm_thrive/services backend/rsm_thrive/tests
git commit -m "services: merge Yug's retrieval/role_lookup/electives/bundles/planner, preserve prod symbols"
```

---

### Task 6: Orchestrator

**Files:**
- Create: `backend/rsm_thrive/services/orchestrator.py`
- Modify: `backend/rsm_thrive/services/bots.py` (retire the grounded-advisor courses path; keep `answer_faq`, `answer_career`)
- Test: `backend/rsm_thrive/tests/{test_orchestrator,test_grounded_course_advisor,test_bots_faq}.py`

**Interfaces:**
- Consumes: Task 4 + Task 5 services.
- Produces: `orchestrator.answer(llm, conversation, question, history) -> BotReply`, the single entrypoint for the `courses` destination.

- [ ] **Step 1: Bring the orchestrator and its tests**

Run:
```bash
git checkout refs/yug/main -- backend/rsm_thrive/services/orchestrator.py
git checkout refs/yug/main -- backend/rsm_thrive/tests/test_orchestrator.py \
  backend/rsm_thrive/tests/test_grounded_course_advisor.py backend/rsm_thrive/tests/test_bots_faq.py
```

- [ ] **Step 2: Reconcile `bots.py`**

Run: `git diff origin/main..refs/yug/main -- backend/rsm_thrive/services/bots.py`
Take Yug's `bots.py` (its `answer_faq`/`answer_career` and residual `answer_electives`), then confirm production's `answer_career` and `answer_faq` behavior is preserved by running their tests in Step 4. Production's grounded-advisor wiring is intentionally dropped — the orchestrator replaces it.
```bash
git checkout refs/yug/main -- backend/rsm_thrive/services/bots.py
```
If production's `grounded_course_advisor` module is now unreferenced, leave the file in place (harmless) but confirm nothing imports it: `grep -rn grounded_course_advisor backend/rsm_thrive --include=*.py | grep -v tests`.

- [ ] **Step 3: Run the orchestrator and bot tests**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_orchestrator.py rsm_thrive/tests/test_grounded_course_advisor.py rsm_thrive/tests/test_bots_faq.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/rsm_thrive/services/orchestrator.py backend/rsm_thrive/services/bots.py backend/rsm_thrive/tests
git commit -m "services: add orchestrator as the courses dispatcher; retire grounded-advisor path"
```

---

### Task 7: Backend wiring and instrumentation

**Files:**
- Create: `backend/rsm_thrive/views/feedback.py`, `backend/rsm_thrive/views/traces.py`
- Modify: `backend/rsm_thrive/views/chat.py`, `backend/rsm_thrive/urls.py`, `backend/config/settings.py`, `backend/.env.example`
- Test: `backend/rsm_thrive/tests/{test_instrumentation,test_chat_write,test_switching_chats,test_long_conversations,test_adversarial,test_careers_and_coverage,test_uncurated_roles,test_hundred_jobs,test_catalog_build,test_planner_api,test_llm,test_codex_credentials,test_ingest}.py` and `tests/contract/schemas.py`

**Interfaces:**
- Consumes: Task 6 `orchestrator.answer`; Task 3 models.
- Produces: `courses` routed through the orchestrator; feedback + traces HTTP endpoints; `THRIVE_SEARCH` settings.

- [ ] **Step 1: Route `courses` to the orchestrator in `chat.py`**

Edit `backend/rsm_thrive/views/chat.py`: replace the `answer_electives` import and call with the orchestrator. Exact change:
```python
# import block: replace answer_electives with the orchestrator alias
from rsm_thrive.services.bots import BotReply, answer_career, answer_faq
from rsm_thrive.services.orchestrator import answer as answer_courses
# in _run_bot: the courses branch
if destination == "courses":
    reply = answer_courses(llm, conversation, question, history)
```
Keep everything else in `chat.py` as production has it. (Yug's `chat.py` differs only in these lines plus a `Prefetch` import used by instrumentation — take that too: `from django.db.models import Prefetch` and the traces prefetch it enables. Confirm by diffing: `git diff origin/main..refs/yug/main -- backend/rsm_thrive/views/chat.py`.)

- [ ] **Step 2: Bring the instrumentation views and add routes**

Run: `git checkout refs/yug/main -- backend/rsm_thrive/views/feedback.py backend/rsm_thrive/views/traces.py`
Then diff `urls.py` and add only the new routes (feedback, traces), keeping all production routes:
```bash
git diff origin/main..refs/yug/main -- backend/rsm_thrive/urls.py
```
Add the shown new `path(...)` entries and their imports to `backend/rsm_thrive/urls.py` by hand; do not overwrite the file.

- [ ] **Step 3: Add the search settings**

Append to `backend/config/settings.py` (verbatim from Yug):
```python
THRIVE_SEARCH = os.environ.get("THRIVE_SEARCH", "duckduckgo")
THRIVE_SEARCH_API_KEY = os.environ.get("THRIVE_SEARCH_API_KEY", "")
```
Add the matching commented lines to `backend/.env.example` from `git show refs/yug/main:backend/.env.example`. Leave production's `THRIVE_LLM`/`CODEX`/`TRITONAI` settings unchanged.

- [ ] **Step 4: Bring the remaining test suites and shared test helpers**

Run:
```bash
git checkout refs/yug/main -- backend/rsm_thrive/testing.py backend/rsm_thrive/tests/contract/schemas.py \
  backend/rsm_thrive/tests/test_instrumentation.py backend/rsm_thrive/tests/test_chat_write.py \
  backend/rsm_thrive/tests/test_switching_chats.py backend/rsm_thrive/tests/test_long_conversations.py \
  backend/rsm_thrive/tests/test_adversarial.py backend/rsm_thrive/tests/test_careers_and_coverage.py \
  backend/rsm_thrive/tests/test_uncurated_roles.py backend/rsm_thrive/tests/test_hundred_jobs.py \
  backend/rsm_thrive/tests/test_catalog_build.py backend/rsm_thrive/tests/test_planner_api.py \
  backend/rsm_thrive/tests/test_llm.py backend/rsm_thrive/tests/test_codex_credentials.py \
  backend/rsm_thrive/tests/test_ingest.py
```
Note: `test_hundred_jobs.py` here exercises the courses/coverage path, not the jobs tab; confirm with a quick read that it imports no `services.jobs` internals before keeping it.

- [ ] **Step 5: Run the wiring and instrumentation tests**

Run: `cd backend && THRIVE_LLM=fake uv run pytest rsm_thrive/tests/test_instrumentation.py rsm_thrive/tests/test_chat_write.py rsm_thrive/tests/test_switching_chats.py rsm_thrive/tests/test_long_conversations.py rsm_thrive/tests/test_adversarial.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/rsm_thrive/views backend/rsm_thrive/urls.py backend/config/settings.py backend/.env.example backend/rsm_thrive/testing.py backend/rsm_thrive/tests
git commit -m "wire courses -> orchestrator; add feedback/traces endpoints and search settings"
```

---

### Task 8: Frontend ask surface

**Files:**
- Modify: `frontend/src/lib/ask.ts`, `frontend/src/lib/components/ask/{ChatWindow,AskHistory}.svelte`, `frontend/src/lib/messages.ts`, `frontend/src/lib/data/types.ts`, `frontend/src/lib/data/api/providers.ts`, `frontend/src/routes/ask-sync/+server.ts`, `frontend/src/app.css`
- Test: `frontend/src/lib/ask.spec.ts`, `frontend/src/lib/designSystem.spec.ts`, `frontend/src/routes/ask-sync/server.spec.ts`

**Interfaces:**
- Consumes: the backend `courses` responses and feedback/traces endpoints from Task 7.
- Produces: routed-reply rendering and the feedback widget in the chat UI.

- [ ] **Step 1: Diff each frontend file**

Run: `for f in lib/ask.ts lib/components/ask/ChatWindow.svelte lib/components/ask/AskHistory.svelte lib/messages.ts lib/data/types.ts lib/data/api/providers.ts routes/ask-sync/+server.ts app.css; do echo "== $f =="; git diff origin/main..refs/yug/main -- frontend/src/$f; done`

- [ ] **Step 2: Apply Yug's ask-surface changes**

Take Yug's versions of the listed files, then verify production's base-path and auth hooks are intact (search for `THRIVE_BASE_PATH`, `base`, and auth imports in the changed files and restore any production-specific lines Yug's fork lacked):
```bash
git checkout refs/yug/main -- frontend/src/lib/ask.ts frontend/src/lib/components/ask/ChatWindow.svelte \
  frontend/src/lib/components/ask/AskHistory.svelte frontend/src/lib/messages.ts \
  frontend/src/lib/data/types.ts frontend/src/lib/data/api/providers.ts \
  frontend/src/routes/ask-sync/+server.ts frontend/src/app.css \
  frontend/src/lib/ask.spec.ts frontend/src/lib/designSystem.spec.ts frontend/src/routes/ask-sync/server.spec.ts
grep -rn "THRIVE_BASE_PATH\|/thrive" frontend/src/lib frontend/src/routes/ask-sync
```

- [ ] **Step 3: Install and run frontend checks**

Run: `cd frontend && npm ci && npm run test` (or the repo's test script; if none, run `npm run check`).
Expected: the three ask specs pass.

- [ ] **Step 4: Build with the production base path**

Run: `cd frontend && THRIVE_BASE_PATH=/thrive npm run build:node`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "frontend: routed replies and feedback widget on the ask surface"
```

---

### Task 9: Full local verification

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything above.
- Produces: a green full suite and a working local `courses` run — the gate before deploy.

- [ ] **Step 1: Whole backend suite**

Run: `cd backend && THRIVE_LLM=fake uv run pytest -q`
Expected: all pass. The total should be the pre-port baseline plus Yug's new suites. Investigate and fix any failure before proceeding.

- [ ] **Step 2: Migration check on a fresh DB**

Run: `cd backend && rm -f db.sqlite3 && THRIVE_LLM=fake uv run python manage.py migrate && THRIVE_LLM=fake uv run python manage.py makemigrations --check --dry-run`
Expected: migrates clean; "No changes detected".

- [ ] **Step 3: Local dev run of the courses bot**

Run the backend (`THRIVE_LLM=fake uv run python manage.py runserver`) and the built frontend, log in, and drive the `courses` bot through: (a) a free-text course question, (b) a plan build then a swap, (c) a question the corpus cannot answer to trigger the web-search fallback and confirm it is labeled unofficial. Confirm the feedback widget records a `TurnFeedback` row.

- [ ] **Step 4: Frontend build once more**

Run: `cd frontend && THRIVE_BASE_PATH=/thrive npm run build:node`
Expected: succeeds.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin integrate-yug-courses
```
If SSH push fails (no key on the server side), stop and resolve auth before Task 10.

---

### Task 10: Deploy to rsm-vnijs

**Files:** none (deploy only). Do this only after Task 9 is fully green and you have explicit go-ahead.

**Interfaces:**
- Consumes: merged `main`.
- Produces: the live site running the new courses surface.

- [ ] **Step 1: Record the rollback point**

On `rsm-vnijs`: `cd ~/thrive && git rev-parse HEAD` — save this SHA.

- [ ] **Step 2: Merge to main and confirm**

Locally (after review): `git checkout main && git merge --ff-only integrate-yug-courses && git push origin main`. Record the new `main` SHA.

- [ ] **Step 3: Deploy at a low-traffic time**

On `rsm-vnijs`:
```bash
cd ~/thrive
git pull --ff-only
cd ~/thrive/backend
/Users/sdeenadayalan/.local/bin/uv sync
python manage.py migrate
python manage.py ingest_corpus --catalog && for d in rsm_thrive/data/corpus/*/; do python manage.py ingest_corpus "$d"; done
cd ~/thrive/frontend
npm ci
THRIVE_BASE_PATH=/thrive npm run build:node
sudo /usr/local/sbin/thrivectl restart
sudo /usr/local/sbin/thrivectl health
```
Confirm the server env has `THRIVE_LLM=tritonai` and `TRITONAI_API_KEY` set before restart.

- [ ] **Step 4: Smoke-test live**

Open `https://rsm-vnijs.ucsd.edu/thrive/`, run one courses question, confirm a grounded answer and that FAQ/career/jobs still work.

- [ ] **Step 5: Rollback path (only if health or smoke fails)**

```bash
cd ~/thrive && git reset --hard <rollback-SHA> && cd backend && /Users/sdeenadayalan/.local/bin/uv sync
cd ~/thrive/frontend && npm ci && THRIVE_BASE_PATH=/thrive npm run build:node
sudo /usr/local/sbin/thrivectl restart && sudo /usr/local/sbin/thrivectl health
```
The additive migrations can stay applied; no down-migration needed.

---

## Self-Review Notes

- **Spec coverage:** every spec section maps to a task — deps (T1), data (T2), migrations (T3), new services (T4), shared merges (T5), orchestrator (T6), wiring + instrumentation (T7), frontend (T8), verification (T9), deploy + rollback (T10).
- **Out-of-scope guard:** each porting task includes a grep confirming no `services.jobs`/`resume`/`pipeline` import crept in.
- **Migration safety:** shared migrations are byte-identical through `0023`; `0024`–`0027` are additive and applied on a local DB in T3 and a fresh DB in T9.
- **Open risk carried into execution:** the merge-shared files (T5, T6, T7) may need a dropped-symbol restore; each such task greps for production imports and re-adds missing functions, with the test suite as the gate.
