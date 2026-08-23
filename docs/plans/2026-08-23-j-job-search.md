# Phase J: Job Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working job-search tab: ingested real postings (Greenhouse/Lever public APIs), search ranked against the student's living resume, a role benchmark ("what the market says this job needs"), an on-demand LLM MatchReport with competency verdict, and PDF resume upload that refreshes the profile.

**Architecture:** A `JobSource` interface feeds an idempotent `ingest_jobs` command (normalize → upsert by (source, externalId) → deterministic skill extraction from a curated vocabulary → embedding). Stage-1 search is portable: ORM term filter + in-Python cosine (resume-profile embedding ↔ posting embedding) + skill-overlap bonus — Postgres FTS is an F5 swap behind one function. Stage 2 is an LLM rubric scorer producing a cached `MatchReport` against resume + posting + role benchmark. The frontend gets a fifth nav destination `/jobs` (search page with `?q=`, detail page with a form-action-generated report, resume PDF upload), with mock providers so mock mode renders fully.

**Tech Stack:** Django 6.1 (`rsm_thrive`), requests (existing), pypdf (existing), Gemini embeddings/LLM via existing `services/embeddings.py` + `services/llm.py` (fakes for tests), SvelteKit 2 / Svelte 5 runes.

**Spec:** `docs/specs/2026-08-21-thrive-backend-design.md` §6 (Job search & suitability ranking). Canvas is dropped (2026-08-23); nothing here depends on it.

## Global Constraints

- Error envelope `{"error": {"code", "message"}}` via `json_error`; camelCase JSON; instants via `iso_instant`.
- New id key space: postings serialize as `job-<pk>`, match reports as `rep-<pk>`. Guard incoming ids with the `isascii()+isdigit()` pattern after prefix strip (see `views/chat.py:_own_conversation`).
- Auth: `@api_login_required` everywhere; job data is shared (no per-user rows except MatchReport); MatchReports are per-user and never leak across users.
- **No LinkedIn scraping.** Sources are Greenhouse/Lever public JSON APIs and (later, keyed) an aggregator. The benchmark is aggregated posting skills — never people data.
- Tests never touch the network: `FakeJobSource`, `FakeEmbeddings`, `FakeLLM` only (conftest already forces `THRIVE_LLM=fake`). Ingest/search/report all injectable.
- Backend: `cd backend && uv run pytest`. Frontend gates: `npm test`, `npm run check` (0/0), `npm run build`.
- Frontend copy only in `src/lib/messages.ts`; no hardcoded colors (design-token test); no `Date.now()`/`new Date()` in components for persisted/compared values; nav item added to the ONE list in `src/lib/nav.ts`.
- Provider seam: new read/write providers live in `data/api/providers.ts` AND get mock implementations + delegators in `data/providers.ts` (jobs must render in mock mode — unlike chat writes, the jobs tab is a whole surface).
- `services/llm.py` chat interface: `llm.chat(system, messages, json_mode=False)`; parse with `parse_llm_json`. Views hold LLM access behind a module-level `llm_factory = get_llm` seam (monkeypatched in tests, same as `views/chat.py`).
- Stage-2 report failure is an honest error (503 `llm_unavailable` envelope), NOT a fabricated report — a student acts on this output.

---

### Task 1: Job models + skills vocabulary + deterministic extractor

**Files:**
- Create: `backend/rsm_thrive/models/jobs.py`
- Modify: `backend/rsm_thrive/models/__init__.py` (export `JobPosting`, `MatchReport`)
- Create: migration `0015_jobposting_matchreport.py` (via `makemigrations`)
- Create: `backend/rsm_thrive/data/jobs/skills_vocab.json`
- Create: `backend/rsm_thrive/services/jobs/__init__.py` (empty)
- Create: `backend/rsm_thrive/services/jobs/skills.py`
- Test: `backend/rsm_thrive/tests/test_job_skills.py`

**Interfaces:**
- Produces:
  - `JobPosting(source: Char 32, external_id: Char 120, title: Char 200, company: Char 120, location: Char 160 blank, url: URLField, description: TextField, posted_at: DateTimeField null, last_seen_at: DateTimeField default timezone.now, active: Bool default True, skills: JSONField list[str], embedding: JSONField list[float])`, unique `(source, external_id)` named `uniq_job_source_external`.
  - `MatchReport(user FK, posting FK related_name="reports", resume_version FK "rsm_thrive.ResumeVersion" on_delete=CASCADE, competency: Char 16, score: Integer, matched_skills: JSONField list, gaps: JSONField list, verdict: TextField, created_at auto_now_add)`, unique `(user, posting, resume_version)` named `uniq_match_report`.
  - `load_skills_vocab() -> dict[str, list[str]]` (lru_cached; canonical skill → alias list).
  - `extract_skills(text: str) -> list[str]` — canonical skills whose canonical name or any alias appears in the text as a whole word (case-insensitive); result sorted alphabetically, deduped.

- [ ] **Step 1: Write the vocabulary**

`skills_vocab.json` — canonical name → aliases (word-boundary matched, case-insensitive). Seed with the analytics-market vocabulary (extend freely later; this is versioned config):

```json
{
  "python": ["python3"],
  "sql": ["postgresql", "mysql", "postgres", "t-sql"],
  "r": [],
  "tableau": [],
  "power bi": ["powerbi"],
  "excel": [],
  "machine learning": ["ml", "scikit-learn", "sklearn"],
  "deep learning": ["neural networks", "pytorch", "tensorflow"],
  "nlp": ["natural language processing", "llm", "llms"],
  "statistics": ["statistical analysis", "statistical modeling"],
  "a/b testing": ["ab testing", "experimentation"],
  "causal inference": [],
  "forecasting": ["time series"],
  "data visualization": ["dashboards", "looker"],
  "etl": ["data pipelines", "airflow", "dbt"],
  "spark": ["pyspark", "databricks"],
  "aws": ["amazon web services", "s3", "redshift"],
  "gcp": ["bigquery", "google cloud"],
  "azure": [],
  "snowflake": [],
  "git": ["github", "version control"],
  "apis": ["rest apis", "rest"],
  "product analytics": ["amplitude", "mixpanel"],
  "marketing analytics": ["attribution"],
  "supply chain": ["logistics", "operations research"],
  "pricing": ["revenue management"],
  "optimization": ["linear programming", "gurobi"],
  "communication": ["stakeholder management", "presentations"],
  "project management": ["agile", "jira"],
  "fraud detection": ["anomaly detection"],
  "recommendation systems": ["recommender systems", "personalization"]
}
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_job_skills.py
import pytest
from django.db import IntegrityError

from rsm_thrive.models import JobPosting
from rsm_thrive.services.jobs.skills import extract_skills, load_skills_vocab

pytestmark = pytest.mark.django_db


class TestVocab:
    def test_loads_with_canonical_keys(self):
        vocab = load_skills_vocab()
        assert "python" in vocab and isinstance(vocab["sql"], list)


class TestExtractSkills:
    def test_matches_canonical_and_alias_case_insensitive(self):
        text = "We use Python, PostgreSQL and PyTorch daily."
        skills = extract_skills(text)
        assert "python" in skills
        assert "sql" in skills           # via postgresql alias
        assert "deep learning" in skills  # via pytorch alias

    def test_whole_word_only(self):
        # "rstudio" must not match the skill "r"; "sparkle" not "spark"
        assert "r" not in extract_skills("we love rstudio and sparkle")
        assert "spark" not in extract_skills("sparkle")

    def test_multiword_alias(self):
        assert "nlp" in extract_skills("natural language processing pipelines")

    def test_sorted_and_deduped(self):
        skills = extract_skills("SQL sql PostgreSQL python")
        assert skills == sorted(set(skills))
        assert skills.count("sql") == 1


class TestModels:
    def test_posting_dedup_constraint(self):
        JobPosting.objects.create(source="greenhouse", external_id="1",
                                  title="Analyst", company="Acme",
                                  url="https://a.example/1", description="d")
        with pytest.raises(IntegrityError):
            JobPosting.objects.create(source="greenhouse", external_id="1",
                                      title="Other", company="Acme",
                                      url="https://a.example/1", description="d")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_job_skills.py -q` → import errors.

- [ ] **Step 4: Implement models and extractor**

```python
# backend/rsm_thrive/models/jobs.py
from django.conf import settings
from django.db import models
from django.utils import timezone

COMPETENCY_CHOICES = [("strong", "strong"), ("good", "good"),
                      ("stretch", "stretch"), ("reach", "reach")]


class JobPosting(models.Model):
    """One normalized posting from any source. Shared across users."""
    source = models.CharField(max_length=32)          # greenhouse | lever | fake | adzuna(later)
    external_id = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=120)
    location = models.CharField(max_length=160, blank=True)
    url = models.URLField()
    description = models.TextField()
    posted_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    skills = models.JSONField(default=list)
    embedding = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["source", "external_id"], name="uniq_job_source_external")]


class MatchReport(models.Model):
    """Stage-2 LLM verdict, cached per (user, posting, resume version)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE,
                                related_name="reports")
    resume_version = models.ForeignKey("rsm_thrive.ResumeVersion",
                                       on_delete=models.CASCADE)
    competency = models.CharField(max_length=16, choices=COMPETENCY_CHOICES)
    score = models.IntegerField()  # 0-100
    matched_skills = models.JSONField(default=list)
    gaps = models.JSONField(default=list)
    verdict = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "posting", "resume_version"], name="uniq_match_report")]
```

```python
# backend/rsm_thrive/services/jobs/skills.py
"""Deterministic skill extraction from a curated, versioned vocabulary.

Deliberately not an LLM call: extraction runs per posting per ingest, must be
reproducible in tests, and drives the role benchmark — the spec's legal
'what the market says this job needs' aggregate.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_VOCAB_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs" / "skills_vocab.json"


@lru_cache(maxsize=1)
def load_skills_vocab():
    return json.loads(_VOCAB_PATH.read_text())


@lru_cache(maxsize=1)
def _patterns():
    compiled = []
    for canonical, aliases in load_skills_vocab().items():
        terms = [canonical] + list(aliases)
        alternation = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
        compiled.append((canonical, re.compile(rf"(?<![\w/])({alternation})(?![\w/])",
                                               re.IGNORECASE)))
    return compiled


def extract_skills(text):
    found = {canonical for canonical, pattern in _patterns() if pattern.search(text)}
    return sorted(found)
```

Export models; `uv run python manage.py makemigrations rsm_thrive` (expect `0015`); migrate.

- [ ] **Step 5: Run tests, then full suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_job_skills.py -q && uv run pytest -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend && git commit -m "feat(j): job posting + match report models, skills vocabulary and extractor"
```

---

### Task 2: JobSource clients (Greenhouse, Lever, fake)

**Files:**
- Create: `backend/rsm_thrive/services/jobs/sources.py`
- Create: `backend/rsm_thrive/data/jobs/companies.json`
- Test: `backend/rsm_thrive/tests/test_job_sources.py`

**Interfaces:**
- Produces:
  - `class JobSource(ABC)` with `name: str` attribute and `fetch(self) -> list[dict]` returning normalized dicts: `{"external_id": str, "title": str, "company": str, "location": str, "url": str, "description": str, "posted_at": datetime|None}`.
  - `class GreenhouseSource(JobSource)` — `__init__(self, board: str, company: str, session=None)`; GET `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`; maps `id→external_id`, `title`, `location["name"]`, `absolute_url→url`, `content` (HTML — strip tags) → description, `updated_at` parsed → posted_at. `name = "greenhouse"`.
  - `class LeverSource(JobSource)` — `__init__(self, company_slug: str, company: str, session=None)`; GET `https://api.lever.co/v0/postings/{company_slug}?mode=json`; maps `id`, `text→title`, `categories.location`, `hostedUrl→url`, `descriptionPlain` (fall back to tag-stripped `description`) → description, `createdAt` ms epoch → posted_at. `name = "lever"`.
  - `class FakeJobSource(JobSource)` — `__init__(self, postings: list[dict])`, returns them; `name = "fake"`.
  - `def strip_html(html: str) -> str` — tags removed, entities unescaped, whitespace collapsed.
  - `def configured_sources(session=None) -> list[JobSource]` — built from `companies.json`.
- `companies.json` shape: `{"greenhouse": [{"board": "<slug>", "company": "<display>"}], "lever": [{"slug": "<slug>", "company": "<display>"}]}` — seed with a starter list of analytics-hiring companies whose public boards exist (verify slugs resolve during the Task 9 smoke; the list is data, not code): greenhouse: `stripe`/Stripe, `airbnb`/Airbnb, `databricks`/Databricks, `doordashusa`/DoorDash, `instacart`/Instacart; lever: `netflix`/Netflix, `spotify`/Spotify, `plaid`/Plaid.
- `session` is a `requests.Session`-like object with `.get(url, timeout=...)`; tests inject a stub. Real calls use `timeout=20` and raise nothing fatal per-source: `fetch()` may raise `requests.RequestException` — callers handle it.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_job_sources.py
import datetime as dt

from rsm_thrive.services.jobs.sources import (
    FakeJobSource, GreenhouseSource, LeverSource, configured_sources, strip_html)


class StubSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        payload = self.payload

        class R:
            def json(self):
                return payload
            def raise_for_status(self):
                pass
        return R()


class TestStripHtml:
    def test_tags_entities_whitespace(self):
        html = "<div><p>SQL &amp; Python</p>\n\n<li>ML</li></div>"
        assert strip_html(html) == "SQL & Python ML"


class TestGreenhouse:
    def test_normalizes(self):
        session = StubSession({"jobs": [{
            "id": 4001, "title": "Data Analyst",
            "location": {"name": "San Diego, CA"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/4001",
            "content": "&lt;p&gt;Needs SQL&lt;/p&gt;",
            "updated_at": "2026-08-01T12:00:00-04:00",
        }]})
        [row] = GreenhouseSource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "4001"
        assert row["company"] == "Acme"
        assert "SQL" in row["description"] and "<p>" not in row["description"]
        assert isinstance(row["posted_at"], dt.datetime)
        assert "boards-api.greenhouse.io/v1/boards/acme/jobs" in session.calls[0][0]


class TestLever:
    def test_normalizes(self):
        session = StubSession([{
            "id": "ab-12", "text": "BI Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/acme/ab-12",
            "descriptionPlain": "dbt and Snowflake",
            "createdAt": 1754000000000,
        }])
        [row] = LeverSource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "ab-12"
        assert row["title"] == "BI Engineer"
        assert row["description"] == "dbt and Snowflake"
        assert row["posted_at"].year >= 2025


class TestConfigured:
    def test_builds_from_companies_json(self):
        sources = configured_sources(session=StubSession({"jobs": []}))
        names = {s.name for s in sources}
        assert names == {"greenhouse", "lever"}
        assert len(sources) >= 4

    def test_fake_source_passthrough(self):
        rows = [{"external_id": "x", "title": "t", "company": "c",
                 "location": "", "url": "https://e.example", "description": "d",
                 "posted_at": None}]
        assert FakeJobSource(rows).fetch() == rows
```

Note the Greenhouse `content` field arrives HTML-escaped from the API (`&lt;p&gt;`) — unescape then strip.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_job_sources.py -q` → import errors.

- [ ] **Step 3: Implement `sources.py`**

```python
# backend/rsm_thrive/services/jobs/sources.py
"""Posting sources behind one interface.

Greenhouse and Lever expose public JSON boards — no key, no scraping, and
explicitly served for this purpose. An aggregator source (Adzuna/JSearch)
slots in later behind the same ABC once a key exists (backlog).
"""

import datetime as dt
import html
import json
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from django.utils.dateparse import parse_datetime

_COMPANIES_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs" / "companies.json"
_TAG = re.compile(r"<[^>]+>")


def strip_html(raw):
    text = html.unescape(raw or "")
    text = _TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


class JobSource(ABC):
    name = "abstract"

    @abstractmethod
    def fetch(self):
        """-> list of normalized posting dicts (see module tests)."""


class FakeJobSource(JobSource):
    name = "fake"

    def __init__(self, postings):
        self._postings = postings

    def fetch(self):
        return list(self._postings)


def _session_or_requests(session):
    if session is not None:
        return session
    import requests
    return requests.Session()


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def __init__(self, board, company, session=None):
        self.board = board
        self.company = company
        self._session = session

    def fetch(self):
        session = _session_or_requests(self._session)
        url = (f"https://boards-api.greenhouse.io/v1/boards/"
               f"{self.board}/jobs?content=true")
        response = session.get(url, timeout=20)
        response.raise_for_status()
        rows = []
        for job in response.json().get("jobs", []):
            rows.append({
                "external_id": str(job["id"]),
                "title": job.get("title", ""),
                "company": self.company,
                "location": (job.get("location") or {}).get("name", ""),
                "url": job.get("absolute_url", ""),
                "description": strip_html(job.get("content", "")),
                "posted_at": parse_datetime(job.get("updated_at") or "") or None,
            })
        return rows


class LeverSource(JobSource):
    name = "lever"

    def __init__(self, company_slug, company, session=None):
        self.slug = company_slug
        self.company = company
        self._session = session

    def fetch(self):
        session = _session_or_requests(self._session)
        url = f"https://api.lever.co/v0/postings/{self.slug}?mode=json"
        response = session.get(url, timeout=20)
        response.raise_for_status()
        rows = []
        for job in response.json():
            created = job.get("createdAt")
            posted = (dt.datetime.fromtimestamp(created / 1000, tz=dt.timezone.utc)
                      if created else None)
            rows.append({
                "external_id": str(job["id"]),
                "title": job.get("text", ""),
                "company": self.company,
                "location": (job.get("categories") or {}).get("location", "") or "",
                "url": job.get("hostedUrl", ""),
                "description": job.get("descriptionPlain")
                               or strip_html(job.get("description", "")),
                "posted_at": posted,
            })
        return rows


@lru_cache(maxsize=1)
def _companies():
    return json.loads(_COMPANIES_PATH.read_text())


def configured_sources(session=None):
    config = _companies()
    sources = [GreenhouseSource(e["board"], e["company"], session=session)
               for e in config.get("greenhouse", [])]
    sources += [LeverSource(e["slug"], e["company"], session=session)
                for e in config.get("lever", [])]
    return sources
```

Write `companies.json` with the starter list from the Interfaces block.

- [ ] **Step 4: Run tests, then full suite**

Run: `cd backend && uv run pytest rsm_thrive/tests/test_job_sources.py -q && uv run pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend && git commit -m "feat(j): job sources — Greenhouse/Lever public boards behind a JobSource seam"
```

---

### Task 3: ingest_jobs command

**Files:**
- Create: `backend/rsm_thrive/services/jobs/ingest.py`
- Create: `backend/rsm_thrive/management/commands/ingest_jobs.py`
- Test: `backend/rsm_thrive/tests/test_job_ingest.py`

**Interfaces:**
- Consumes: `JobPosting`, `extract_skills` (Task 1); `JobSource`/`configured_sources` (Task 2); `get_embeddings` (existing).
- Produces:
  - `def ingest_from(sources: list[JobSource], embeddings=None) -> dict` — for each source: `fetch()`, upsert each row by `(source.name, external_id)` (update fields + `last_seen_at=now`, `active=True`); skills = `extract_skills(title + " " + description)`; embedding = one batch `embeddings.embed()` per source over `f"{title}\n{description[:2000]}"`; after all sources, deactivate (`active=False`) any posting whose `source` is among the fetched sources' names and whose `last_seen_at` predates this run's start. A source whose `fetch()` raises is logged (`logger.exception`) and skipped — its existing postings are NOT deactivated. Returns `{"ingested": n, "deactivated": m, "failed_sources": [names]}`.
  - Command `ingest_jobs`: runs `ingest_from(configured_sources())`, prints one summary line per source and the totals.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_job_ingest.py
import pytest

from rsm_thrive.models import JobPosting
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.ingest import ingest_from
from rsm_thrive.services.jobs.sources import FakeJobSource, JobSource

pytestmark = pytest.mark.django_db


def _row(external_id="1", title="Data Analyst", description="SQL and Tableau"):
    return {"external_id": external_id, "title": title, "company": "Acme",
            "location": "SD", "url": "https://e.example/1",
            "description": description, "posted_at": None}


class ExplodingSource(JobSource):
    name = "boom"

    def fetch(self):
        raise RuntimeError("network down")


class TestIngest:
    def test_creates_with_skills_and_embedding(self):
        result = ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        assert result["ingested"] == 1
        posting = JobPosting.objects.get()
        assert posting.source == "fake"
        assert "sql" in posting.skills and "tableau" in posting.skills
        assert len(posting.embedding) > 0 and posting.active

    def test_rerun_updates_not_duplicates(self):
        ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        ingest_from([FakeJobSource([_row(title="Senior Data Analyst")])],
                    embeddings=FakeEmbeddings())
        assert JobPosting.objects.count() == 1
        assert JobPosting.objects.get().title == "Senior Data Analyst"

    def test_stale_postings_deactivate(self):
        ingest_from([FakeJobSource([_row("1"), _row("2")])],
                    embeddings=FakeEmbeddings())
        ingest_from([FakeJobSource([_row("1")])], embeddings=FakeEmbeddings())
        assert JobPosting.objects.get(external_id="1").active
        assert not JobPosting.objects.get(external_id="2").active

    def test_failed_source_skipped_and_its_rows_kept_active(self):
        ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        result = ingest_from([ExplodingSource(), FakeJobSource([_row()])],
                             embeddings=FakeEmbeddings())
        assert result["failed_sources"] == ["boom"]
        assert JobPosting.objects.get().active  # fake source refreshed it
```

- [ ] **Step 2: Run to verify failure**, then implement:

```python
# backend/rsm_thrive/services/jobs/ingest.py
"""Idempotent posting ingestion: fetch -> upsert -> skills -> embed -> expire.

A management command today; the F5 cron just schedules the same call.
"""

import logging

from django.utils import timezone

from rsm_thrive.models import JobPosting
from rsm_thrive.services.embeddings import get_embeddings
from rsm_thrive.services.jobs.skills import extract_skills

logger = logging.getLogger("rsm_thrive.jobs")


def ingest_from(sources, embeddings=None):
    embeddings = embeddings or get_embeddings()
    run_started = timezone.now()
    ingested = 0
    succeeded_names = []
    failed = []

    for source in sources:
        try:
            rows = source.fetch()
        except Exception:
            logger.exception("job source %s failed; keeping its postings", source.name)
            failed.append(source.name)
            continue
        texts = [f"{r['title']}\n{r['description'][:2000]}" for r in rows]
        vectors = embeddings.embed(texts) if texts else []
        for row, vector in zip(rows, vectors):
            JobPosting.objects.update_or_create(
                source=source.name, external_id=row["external_id"],
                defaults={
                    "title": row["title"][:200],
                    "company": row["company"][:120],
                    "location": (row["location"] or "")[:160],
                    "url": row["url"],
                    "description": row["description"],
                    "posted_at": row["posted_at"],
                    "last_seen_at": timezone.now(),
                    "active": True,
                    "skills": extract_skills(f"{row['title']} {row['description']}"),
                    "embedding": vector,
                })
            ingested += 1
        succeeded_names.append(source.name)

    deactivated = (JobPosting.objects
                   .filter(source__in=succeeded_names, active=True,
                           last_seen_at__lt=run_started)
                   .update(active=False))
    return {"ingested": ingested, "deactivated": deactivated,
            "failed_sources": failed}
```

```python
# backend/rsm_thrive/management/commands/ingest_jobs.py
from django.core.management.base import BaseCommand

from rsm_thrive.services.jobs.ingest import ingest_from
from rsm_thrive.services.jobs.sources import configured_sources


class Command(BaseCommand):
    help = "Fetch, normalize, and upsert job postings from all configured sources."

    def handle(self, *args, **options):
        result = ingest_from(configured_sources())
        self.stdout.write(
            f"ingested {result['ingested']} postings, "
            f"deactivated {result['deactivated']} stale"
            + (f", failed: {', '.join(result['failed_sources'])}"
               if result["failed_sources"] else ""))
```

- [ ] **Step 3: Run tests, then full suite** → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat(j): idempotent ingest_jobs command with skill extraction and stale expiry"
```

---

### Task 4: Search, ranking, and role benchmark

**Files:**
- Create: `backend/rsm_thrive/services/jobs/search.py`
- Test: `backend/rsm_thrive/tests/test_job_search.py`

**Interfaces:**
- Consumes: `JobPosting`; `cosine`, `get_embeddings` (existing); `ResumeVersion` (existing).
- Produces:
  - `def profile_of(user) -> dict | None` — the user's current `ResumeVersion` reduced to `{"text": str, "skills": set[str], "version": ResumeVersion}`. Text = summary + skill names + experience titles/bullets joined. `None` when no current version exists.
  - `def search_postings(user, query, limit=20, embeddings=None) -> dict` — active postings matching EVERY whitespace-separated query term (each term `icontains` in title OR company OR description; empty query = all active). Ranking score per posting: `0.6 * cosine(profile_embedding, posting.embedding) + 0.4 * skill_overlap` where `skill_overlap = |posting.skills ∩ profile.skills| / max(1, |posting.skills|)`; with NO profile, score = 0.0 for all and ordering falls back to `-posted_at` (nulls last), then title. Returns `{"results": [{"posting": JobPosting, "score": float, "matched_skills": [str], "missing_skills": [str]}...], "benchmark": {...}, "profile_available": bool}` — results best-first, capped at `limit`; `matched_skills`/`missing_skills` computed vs the profile skill set (missing = posting skills not in profile; both sorted). Ties break on posting title.
  - `def role_benchmark(query) -> dict` — over active postings whose TITLE matches every query term (`icontains`): `{"sampleSize": n, "topSkills": [{"name": str, "share": float}...]}` — skills ranked by document frequency, share = fraction of matching postings listing the skill (2 decimals), top 10. Empty query or no matches → `{"sampleSize": 0, "topSkills": []}`.
- Profile skill names normalize to lowercase for matching (vocabulary is lowercase; resume skills are human-cased).

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_job_search.py
import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.search import profile_of, role_benchmark, search_postings

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    return User.objects.create_user("stu")


def _posting(external_id, title, description, skills, active=True):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=skills, embedding=vector, active=active)


def _resume(user, skills=("Python", "SQL")):
    return ResumeVersion.objects.create(
        user=user, label="v1", summary="Analytics student strong in sql and python",
        skills=[{"id": f"s{i}", "name": n, "source": "manual"}
                for i, n in enumerate(skills)],
        courses=[], experience=[], is_current=True)


class TestProfile:
    def test_none_without_current_resume(self, student):
        assert profile_of(student) is None

    def test_profile_lowercases_skills(self, student):
        _resume(student)
        profile = profile_of(student)
        assert profile["skills"] == {"python", "sql"}
        assert "sql" in profile["text"].lower()


class TestSearch:
    def test_terms_filter_and_profile_ranking(self, student):
        _resume(student)
        _posting("1", "Data Analyst", "sql python dashboards",
                 ["sql", "python", "data visualization"])
        _posting("2", "Data Analyst", "supply chain optimization",
                 ["supply chain", "optimization"])
        _posting("3", "Chef", "cooking", [])

        result = search_postings(student, "data analyst")
        ids = [r["posting"].external_id for r in result["results"]]
        assert "3" not in ids
        assert ids[0] == "1"  # skill+embedding overlap wins
        top = result["results"][0]
        assert top["matched_skills"] == ["python", "sql"]
        assert top["missing_skills"] == ["data visualization"]
        assert result["profile_available"] is True

    def test_inactive_excluded_and_no_profile_falls_back(self, student):
        _posting("1", "Data Analyst", "sql", ["sql"])
        _posting("2", "Data Analyst old", "sql", ["sql"], active=False)
        result = search_postings(student, "analyst")
        assert len(result["results"]) == 1
        assert result["profile_available"] is False
        assert result["results"][0]["score"] == 0.0

    def test_empty_query_returns_all_active(self, student):
        _posting("1", "A", "x", [])
        _posting("2", "B", "y", [])
        assert len(search_postings(student, "")["results"]) == 2


class TestBenchmark:
    def test_shares_and_ranking(self, student):
        _posting("1", "Data Analyst", "d", ["sql", "python"])
        _posting("2", "Senior Data Analyst", "d", ["sql", "tableau"])
        _posting("3", "Chef", "d", ["cooking"])
        benchmark = role_benchmark("data analyst")
        assert benchmark["sampleSize"] == 2
        top = benchmark["topSkills"][0]
        assert top["name"] == "sql" and top["share"] == 1.0

    def test_empty(self, student):
        assert role_benchmark("") == {"sampleSize": 0, "topSkills": []}
```

- [ ] **Step 2: Run to verify failure**, then implement `search.py`:

```python
# backend/rsm_thrive/services/jobs/search.py
"""Stage-1 ranking and the role benchmark.

Portable by construction: term filtering via the ORM, similarity in Python
over stored embeddings (same pattern as chatbot retrieval — the posting set
is small). Postgres FTS is an F5 swap inside `_matching_postings` only.
"""

from collections import Counter

from django.db.models import Q

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import cosine, get_embeddings


def profile_of(user):
    version = ResumeVersion.objects.filter(user=user, is_current=True).first()
    if version is None:
        return None
    skills = {(s.get("name") or "").lower() for s in version.skills if s.get("name")}
    parts = [version.summary]
    parts += sorted(skills)
    for exp in version.experience:
        parts.append(exp.get("title", ""))
        parts += exp.get("bullets", [])
    return {"text": "\n".join(p for p in parts if p),
            "skills": skills, "version": version}


def _matching_postings(query):
    postings = JobPosting.objects.filter(active=True)
    for term in query.split():
        postings = postings.filter(Q(title__icontains=term)
                                   | Q(company__icontains=term)
                                   | Q(description__icontains=term))
    return postings


def search_postings(user, query, limit=20, embeddings=None):
    profile = profile_of(user)
    postings = list(_matching_postings(query))

    profile_vector = None
    if profile is not None and postings:
        embeddings = embeddings or get_embeddings()
        [profile_vector] = embeddings.embed([profile["text"]])

    results = []
    for posting in postings:
        posting_skills = [s.lower() for s in posting.skills]
        if profile is not None:
            matched = sorted(set(posting_skills) & profile["skills"])
            missing = sorted(set(posting_skills) - profile["skills"])
            overlap = len(matched) / max(1, len(set(posting_skills)))
            score = 0.6 * cosine(profile_vector, posting.embedding) + 0.4 * overlap
        else:
            matched, missing, score = [], sorted(set(posting_skills)), 0.0
        results.append({"posting": posting, "score": score,
                        "matched_skills": matched, "missing_skills": missing})

    if profile is not None:
        results.sort(key=lambda r: (-r["score"], r["posting"].title))
    else:
        results.sort(key=lambda r: (r["posting"].posted_at is None,
                                    -(r["posting"].posted_at.timestamp()
                                      if r["posting"].posted_at else 0),
                                    r["posting"].title))
    return {"results": results[:limit],
            "benchmark": role_benchmark(query),
            "profile_available": profile is not None}


def role_benchmark(query):
    if not query.split():
        return {"sampleSize": 0, "topSkills": []}
    postings = JobPosting.objects.filter(active=True)
    for term in query.split():
        postings = postings.filter(title__icontains=term)
    rows = list(postings.values_list("skills", flat=True))
    if not rows:
        return {"sampleSize": 0, "topSkills": []}
    counts = Counter()
    for skills in rows:
        counts.update({s.lower() for s in skills})
    top = [{"name": name, "share": round(count / len(rows), 2)}
           for name, count in counts.most_common(10)]
    return {"sampleSize": len(rows), "topSkills": top}
```

- [ ] **Step 3: Run tests, then full suite** → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat(j): profile-ranked job search and role benchmark"
```

---

### Task 5: Jobs read endpoints

**Files:**
- Create: `backend/rsm_thrive/serializers/jobs.py`
- Create: `backend/rsm_thrive/views/jobs.py` (this task: `jobs_search`, `job_detail`)
- Modify: `backend/rsm_thrive/urls.py`
- Test: `backend/rsm_thrive/tests/test_jobs_api.py`

**Interfaces:**
- Consumes: `search_postings`, `role_benchmark` (Task 4).
- Produces:
  - `GET /api/thrive/jobs?q=<terms>` → 200 `{"query": str, "profileAvailable": bool, "benchmark": {"sampleSize", "topSkills"}, "results": [{"job": JOB, "score": float rounded 3, "matchedSkills": [..], "missingSkills": [..]}]}`.
  - `GET /api/thrive/jobs/<job_id>` → 200 `{"job": JOB_FULL, "benchmark": <role_benchmark(posting.title)>}`; unknown/malformed id → 404 `unknown_job`.
  - `JOB` (list shape) = `{"id": "job-<pk>", "title", "company", "location", "url", "source", "skills": [..], "postedAt": iso_instant|null, "snippet": first 220 chars of description + "…" if longer}`. `JOB_FULL` = JOB + `"description"` (full) instead of snippet.
  - `serialize_job(posting, full=False) -> dict` in `serializers/jobs.py`.
  - `_own_posting(job_id) -> JobPosting|None` helper: `job-` prefix + `isascii()+isdigit()` guard (postings are shared — no user filter; the name mirrors the chat helper's shape).
- urls: `path("jobs", jobs.jobs_search)`, `path("jobs/<str:job_id>", jobs.job_detail)` (+ Task 6 adds the report route). Both `@api_login_required`, GET-only via `require_http_methods(["GET"])`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_jobs_api.py
import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


def _posting(external_id="1", title="Data Analyst", description="sql python",
             skills=("sql", "python")):
    [vector] = FakeEmbeddings().embed([f"{title}\n{description}"])
    return JobPosting.objects.create(
        source="fake", external_id=external_id, title=title, company="Acme",
        url=f"https://e.example/{external_id}", description=description,
        skills=list(skills), embedding=vector)


class TestSearchEndpoint:
    def test_shape_and_camel_case(self, client, student):
        ResumeVersion.objects.create(user=student, label="v", summary="sql person",
                                     skills=[{"id": "s1", "name": "SQL",
                                              "source": "manual"}],
                                     courses=[], experience=[], is_current=True)
        _posting()
        payload = client.get("/api/thrive/jobs?q=analyst").json()
        assert payload["profileAvailable"] is True
        assert payload["benchmark"]["sampleSize"] == 1
        [entry] = payload["results"]
        assert entry["job"]["id"].startswith("job-")
        assert entry["matchedSkills"] == ["sql"]
        assert "description" not in entry["job"] and "snippet" in entry["job"]

    def test_requires_login(self, client):
        assert client.get("/api/thrive/jobs").status_code in (401, 403)

    def test_post_is_405(self, client, student):
        assert client.post("/api/thrive/jobs").status_code == 405


class TestDetailEndpoint:
    def test_full_description_and_benchmark(self, client, student):
        posting = _posting(description="long description " * 30)
        payload = client.get(f"/api/thrive/jobs/job-{posting.pk}").json()
        assert payload["job"]["description"].startswith("long description")
        assert payload["benchmark"]["sampleSize"] == 1

    def test_unknown_and_malformed_404(self, client, student):
        for job_id in ("job-99999", "banana", "job-๑๒"):
            response = client.get(f"/api/thrive/jobs/{job_id}")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "unknown_job"
```

- [ ] **Step 2: Run to verify failure**, then implement serializer + views following the repo's existing view style (`json_ok`, `json_error`, decorators). Snippet: `description[:220] + ("…" if len(description) > 220 else "")`. Score rounded `round(score, 3)`.

- [ ] **Step 3: Run tests, then full suite** → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat(j): job search and detail endpoints"
```

---

### Task 6: MatchReport service + endpoint

**Files:**
- Create: `backend/rsm_thrive/services/jobs/report.py`
- Modify: `backend/rsm_thrive/views/jobs.py` (add `job_report`)
- Modify: `backend/rsm_thrive/serializers/jobs.py` (add `serialize_report`)
- Modify: `backend/rsm_thrive/urls.py` (`path("jobs/<str:job_id>/report", jobs.job_report)`)
- Test: `backend/rsm_thrive/tests/test_job_report.py`

**Interfaces:**
- Consumes: `MatchReport`, `profile_of`, `role_benchmark`, `parse_llm_json`, `llm_factory` seam pattern.
- Produces:
  - `def generate_report(llm, user, posting) -> MatchReport` — requires a current resume (caller checks). Cache: existing `MatchReport` for `(user, posting, current_version)` returned as-is. Else ONE `llm.chat(system, [user message], json_mode=True)`:
    - system = `REPORT_PROMPT` (module constant): "You are a pragmatic career advisor scoring one candidate against one job posting. Reply with JSON only: {\"score\": <0-100 integer>, \"competency\": \"strong|good|stretch|reach\", \"matched_skills\": [..], \"gaps\": [..], \"verdict\": \"<3-5 plain sentences on competitiveness and what to emphasize or close>\"}. Ground every claim in the resume, the posting, and the market benchmark. Never invent experience."
    - user message content = labeled blocks: RESUME (profile text), POSTING (title, company, description[:4000], posting skills), MARKET BENCHMARK (role_benchmark(posting.title) top skills with shares).
    - Envelope parsed with `parse_llm_json`; sanitize: score int clamped 0–100 (unparseable → raise `ReportError`); competency must be one of the four (else derive from score: ≥80 strong, ≥60 good, ≥40 stretch, else reach); matched_skills/gaps filtered to strings; verdict must be a non-empty string else `ReportError`.
    - `class ReportError(Exception)` for any unusable LLM output.
  - `POST /api/thrive/jobs/<job_id>/report` → 200 `{"report": REPORT}`; no current resume → 409 `no_resume` ("Upload or build a resume first."); unknown job → 404 `unknown_job`; LLM exception or `ReportError` → 503 `llm_unavailable` (honest failure — a fabricated competency verdict is worse than an error; students act on this). Module seam `llm_factory = get_llm` in `views/jobs.py`.
  - `REPORT` = `{"id": "rep-<pk>", "jobId": "job-<pk>", "score", "competency", "matchedSkills", "gaps", "verdict", "createdAt": iso_instant}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_job_report.py
import json

import pytest
from django.contrib.auth.models import User

from rsm_thrive.models import JobPosting, MatchReport, ResumeVersion
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.views import jobs as jobs_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


@pytest.fixture
def resume(student):
    return ResumeVersion.objects.create(
        user=student, label="v", summary="sql analyst",
        skills=[{"id": "s1", "name": "SQL", "source": "manual"}],
        courses=[], experience=[], is_current=True)


@pytest.fixture
def posting():
    [vector] = FakeEmbeddings().embed(["Data Analyst\nsql"])
    return JobPosting.objects.create(source="fake", external_id="1",
                                     title="Data Analyst", company="Acme",
                                     url="https://e.example/1",
                                     description="sql", skills=["sql"],
                                     embedding=vector)


def _reply(score=72, competency="good"):
    return json.dumps({"score": score, "competency": competency,
                       "matched_skills": ["sql"], "gaps": ["tableau"],
                       "verdict": "Competitive. Emphasize SQL projects."})


def _install(monkeypatch, replies):
    fake = FakeLLM(replies=replies)
    monkeypatch.setattr(jobs_views, "llm_factory", lambda: fake)
    return fake


class TestReportEndpoint:
    def test_generates_and_caches(self, client, student, resume, posting, monkeypatch):
        _install(monkeypatch, [_reply()])
        first = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert first.status_code == 200
        report = first.json()["report"]
        assert report["competency"] == "good" and report["score"] == 72
        assert report["id"].startswith("rep-")
        # second call: FakeLLM is exhausted, so success proves the cache
        _install(monkeypatch, [])
        second = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert second.status_code == 200
        assert MatchReport.objects.count() == 1

    def test_new_resume_version_regenerates(self, client, student, resume, posting,
                                            monkeypatch):
        _install(monkeypatch, [_reply()])
        client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        resume.is_current = False
        resume.save()
        ResumeVersion.objects.create(user=student, label="v2", summary="new",
                                     skills=[], courses=[], experience=[],
                                     is_current=True)
        _install(monkeypatch, [_reply(score=40, competency="stretch")])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.json()["report"]["score"] == 40
        assert MatchReport.objects.count() == 2

    def test_no_resume_409(self, client, student, posting, monkeypatch):
        _install(monkeypatch, [])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "no_resume"

    def test_llm_failure_503(self, client, student, resume, posting, monkeypatch):
        _install(monkeypatch, [])  # first chat call raises
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "llm_unavailable"
        assert MatchReport.objects.count() == 0

    def test_bad_competency_derives_from_score(self, client, student, resume,
                                               posting, monkeypatch):
        _install(monkeypatch, [json.dumps({"score": 85, "competency": "amazing",
                                           "matched_skills": [], "gaps": [],
                                           "verdict": "Strong fit."})])
        response = client.post(f"/api/thrive/jobs/job-{posting.pk}/report")
        assert response.json()["report"]["competency"] == "strong"

    def test_unknown_job_404_and_get_405(self, client, student, resume, monkeypatch):
        _install(monkeypatch, [])
        assert client.post("/api/thrive/jobs/job-999/report").status_code == 404
        assert client.get("/api/thrive/jobs/job-999/report").status_code == 405
```

- [ ] **Step 2: Run to verify failure**, then implement `report.py` + view per the Interfaces block. The view: resolve posting → `profile_of(user)` (None → 409) → try `generate_report(llm_factory(), user, posting)` except `ReportError` and generic `Exception` → `logger.exception` + 503 envelope. Success → `json_ok({"report": serialize_report(report)})`.

- [ ] **Step 3: Run tests, then full suite** → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat(j): cached LLM match reports with honest 503 on failure"
```

---

### Task 7: Resume PDF upload

**Files:**
- Create: `backend/rsm_thrive/services/jobs/resume_upload.py`
- Modify: `backend/rsm_thrive/views/resume.py` (add `resume_upload` view; read the file first and follow its style)
- Modify: `backend/rsm_thrive/urls.py` (`path("resume/upload", resume.resume_upload)`)
- Test: `backend/rsm_thrive/tests/test_resume_upload.py`

**Interfaces:**
- Consumes: `extract_pdf_text` (existing, `services/ingest.py`); `parse_llm_json`, `FakeLLM`; `ResumeVersion` (existing semantics: exactly-one-current via partial unique constraint — read `views/resume.py`/`services/resume.py` first to reuse the existing version-creation flow if one exists, else set previous `is_current=False` then create new with `is_current=True` inside `transaction.atomic`).
- Produces:
  - `def extract_profile(llm, text: str) -> dict` — ONE `llm.chat(EXTRACT_PROMPT, [text-as-user], json_mode=True)` → `parse_llm_json` → sanitized `{"summary": str, "skills": [str], "experience": [{"title", "organization", "period", "bullets": [str]}]}`. EXTRACT_PROMPT constant: "Extract a structured resume profile from this resume text. Reply with JSON only: {\"summary\": \"<2-3 sentence professional summary in the candidate's voice>\", \"skills\": [<skill names>], \"experience\": [{\"title\": ..., \"organization\": ..., \"period\": ..., \"bullets\": [<achievement strings>]}]}. Use only information present in the text." Sanitize: skills → unique non-empty strings; experience entries → strings coerced, bullets filtered; empty summary → raise `UploadError`.
  - `POST /api/thrive/resume/upload` — multipart with field `file`; PDF only v1 (extension + `%PDF` magic check; else 400 `bad_request` "Only PDF resumes are supported right now."); size cap 5MB (400 `too_large`); extracted text < 200 chars → 400 `unreadable_resume` (likely a scanned image). Success: creates a new current `ResumeVersion` (label `"Uploaded resume"`, skills as contract-shaped dicts `{"id": "up-<n>", "name": ..., "source": "manual"}`, `courses=[]`, experience contract-shaped with generated ids `"exp-up-<n>"`), returns 201 with the SAME payload shape the existing resume GET endpoints use for a version (read `serializers/` for the existing resume serializer and reuse it).
  - LLM failure/`UploadError` → 503 `llm_unavailable`, and NO version is created. Module seam `llm_factory = get_llm` in `views/resume.py`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/rsm_thrive/tests/test_resume_upload.py
import json

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from rsm_thrive.models import ResumeVersion
from rsm_thrive.services.llm import FakeLLM
from rsm_thrive.views import resume as resume_views

pytestmark = pytest.mark.django_db


@pytest.fixture
def student(client):
    user = User.objects.create_user("stu", password="pw")
    client.force_login(user)
    return user


def _envelope():
    return json.dumps({
        "summary": "Analytics graduate student with SQL-heavy internships.",
        "skills": ["SQL", "Python", ""],
        "experience": [{"title": "Data Intern", "organization": "Acme",
                        "period": "Summer 2025", "bullets": ["Built dashboards"]}],
    })


def _install(monkeypatch, replies):
    fake = FakeLLM(replies=replies)
    monkeypatch.setattr(resume_views, "llm_factory", lambda: fake)
    return fake


def _upload(client, content=b"%PDF-1.4 x", name="cv.pdf"):
    return client.post("/api/thrive/resume/upload",
                       {"file": SimpleUploadedFile(name, content,
                                                   content_type="application/pdf")})


class TestUpload:
    def test_creates_current_version(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "Jane Doe. SQL intern at Acme. " * 20)
        _install(monkeypatch, [_envelope()])
        response = _upload(client)
        assert response.status_code == 201
        version = ResumeVersion.objects.get(user=student, is_current=True)
        assert [s["name"] for s in version.skills] == ["SQL", "Python"]
        assert version.experience[0]["organization"] == "Acme"

    def test_replaces_previous_current(self, client, student, monkeypatch):
        ResumeVersion.objects.create(user=student, label="old", summary="s",
                                     skills=[], courses=[], experience=[],
                                     is_current=True)
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [_envelope()])
        assert _upload(client).status_code == 201
        assert ResumeVersion.objects.filter(user=student).count() == 2
        assert ResumeVersion.objects.get(user=student, is_current=True).label \
            == "Uploaded resume"

    def test_non_pdf_400(self, client, student, monkeypatch):
        _install(monkeypatch, [])
        response = _upload(client, content=b"plain text", name="cv.txt")
        assert response.status_code == 400

    def test_unreadable_pdf_400(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text", lambda f: "  ")
        _install(monkeypatch, [])
        response = _upload(client)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unreadable_resume"

    def test_llm_failure_503_and_nothing_created(self, client, student, monkeypatch):
        monkeypatch.setattr(resume_views, "extract_uploaded_text",
                            lambda f: "text " * 100)
        _install(monkeypatch, [])
        assert _upload(client).status_code == 503
        assert ResumeVersion.objects.count() == 0

    def test_missing_file_400(self, client, student, monkeypatch):
        _install(monkeypatch, [])
        assert client.post("/api/thrive/resume/upload").status_code == 400
```

`extract_uploaded_text(file) -> str` is a small named function in `views/resume.py` (wraps `pypdf.PdfReader` over the uploaded stream) precisely so tests monkeypatch text extraction rather than generating text-bearing PDFs (pypdf cannot easily write text). The magic/extension/size checks run BEFORE it.

- [ ] **Step 2: Run to verify failure**, then implement per the Interfaces block. Real PDF text-extraction path is exercised in the Task 9 smoke with a real resume-like PDF.

- [ ] **Step 3: Run tests, then full suite** → PASS.

- [ ] **Step 4: Commit**

```bash
git add backend && git commit -m "feat(j): resume PDF upload with LLM profile extraction"
```

---

### Task 8: Frontend types, providers, mock fixtures

**Files:**
- Modify: `frontend/src/lib/data/types.ts` (job types)
- Create: `frontend/src/lib/data/mock/jobs.ts` (fixtures)
- Modify: `frontend/src/lib/data/api/providers.ts` (4 api providers)
- Modify: `frontend/src/lib/data/providers.ts` (mock impls + delegators)
- Modify: `frontend/src/lib/data/index.ts` if it re-exports types (check)
- Test: extend `frontend/src/lib/data/api/providers.spec.ts`

**Interfaces:**
- Produces (types, matching Task 5/6 payloads exactly):

```typescript
export type JobCompetency = "strong" | "good" | "stretch" | "reach";

export interface JobPosting {
  id: string;            // "job-<pk>"
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  skills: string[];
  postedAt: ISODateTime | null;
  snippet: string;
}

export interface JobPostingDetail extends Omit<JobPosting, "snippet"> {
  description: string;
}

export interface JobSearchEntry {
  job: JobPosting;
  score: number;
  matchedSkills: string[];
  missingSkills: string[];
}

export interface RoleBenchmark {
  sampleSize: number;
  topSkills: { name: string; share: number }[];
}

export interface JobSearchResult {
  query: string;
  profileAvailable: boolean;
  benchmark: RoleBenchmark;
  results: JobSearchEntry[];
}

export interface MatchReport {
  id: string;            // "rep-<pk>"
  jobId: string;
  score: number;
  competency: JobCompetency;
  matchedSkills: string[];
  gaps: string[];
  verdict: string;
  createdAt: ISODateTime;
}
```

- Providers (api): `searchJobs(query: string): Promise<JobSearchResult>` → `GET /jobs?q=<encoded>`; `getJobPosting(jobId): Promise<{job: JobPostingDetail; benchmark: RoleBenchmark}>` → `GET /jobs/<id>`; `generateMatchReport(jobId): Promise<MatchReport>` → `POST /jobs/<id>/report`, unwrap `.report`; `uploadResume(file: File): Promise<void>` → multipart POST `/resume/upload` (check `apiFetch` supports FormData — if it JSON-encodes bodies unconditionally, add a `rawBody` option or a dedicated multipart path in `client.ts`, following its existing style).
- Mock impls in `data/providers.ts`: fixtures in `mock/jobs.ts` — 6 postings across 3 titles (Data Analyst ×3, Data Scientist ×2, Product Analyst ×1) with realistic skills; `mockSearchJobs` filters by terms and fakes scores descending; `mockGetJobPosting` by id; `mockGenerateMatchReport` returns a fixed plausible report after `resolveAfterDelay` (mirroring other mocks); `mockUploadResume` resolves after delay (no-op). Delegators follow the 27-provider pattern (`apiEnabled() ? api.x() : mockX()`).

- [ ] **Step 1: Write failing provider specs** (follow the file's table/stub pattern):

```typescript
it("searchJobs encodes the query", async () => {
  const impl = stubFetch(200, { query: "x", profileAvailable: false,
    benchmark: { sampleSize: 0, topSkills: [] }, results: [] });
  await runWithAuth(AUTH, () => api.searchJobs("data analyst"));
  expect(impl.mock.calls[0][0])
    .toBe("http://api.test/api/thrive/jobs?q=data%20analyst");
});

it("generateMatchReport POSTs and unwraps", async () => {
  const impl = stubFetch(200, { report: { id: "rep-1", jobId: "job-1",
    score: 70, competency: "good", matchedSkills: [], gaps: [],
    verdict: "v", createdAt: "2026-08-23T09:00:00-07:00" } });
  const report = await runWithAuth(AUTH, () => api.generateMatchReport("job-1"));
  expect(impl.mock.calls[0][1].method).toBe("POST");
  expect(report.id).toBe("rep-1");
});
```

(plus `getJobPosting` in the existing read-provider table). `uploadResume` gets a spec asserting multipart/FormData handling once the client mechanism is chosen — assert the body is a `FormData` instance and no JSON content-type header is forced.

- [ ] **Step 2: Run to verify failure**, implement types + fixtures + providers + delegators.

- [ ] **Step 3: `npm test` and `npm run check`** → green, 0/0.

- [ ] **Step 4: Commit**

```bash
git add frontend && git commit -m "feat(j): job types, providers (api + mock), and fixtures"
```

---

### Task 9: Jobs UI — nav, search page, detail page, upload

**Files:**
- Modify: `frontend/src/lib/nav.ts` (fifth destination `/jobs`)
- Modify: `frontend/src/lib/messages.ts` (jobs copy block)
- Create: `frontend/src/routes/jobs/+page.server.ts` (search load via `?q=` + upload action)
- Create: `frontend/src/routes/jobs/+page.svelte`
- Create: `frontend/src/routes/jobs/[id]/+page.server.ts` (detail load + report action)
- Create: `frontend/src/routes/jobs/[id]/+page.svelte`
- Create: `frontend/src/lib/components/jobs/JobResultCard.svelte`, `frontend/src/lib/components/jobs/BenchmarkPanel.svelte`, `frontend/src/lib/components/jobs/ReportPanel.svelte`
- Test: `frontend/src/lib/components/jobs/jobs.spec.ts` (or per-component, matching repo test layout — check how other component specs are organized first)

**Interfaces & binding behavior:**
- Nav: add after Appointments: `{ href: '/jobs', label: 'Jobs', icon: BriefcaseBusiness, description: 'Search postings ranked against your resume' }` (import `BriefcaseBusiness` from `@lucide/svelte/icons/briefcase-business`).
- Search page (`/jobs?q=...`): server load reads `url.searchParams.get("q") ?? ""`, calls `searchJobs(q)` (delegator — works in both modes), returns `{ query, result }`. The page: a search form (GET method, input name `q` — plain form navigation, no JS needed), a "profile" banner when `profileAvailable` is false ("Upload your resume to rank results against your skills") with the upload form (file input, POST action `?/upload` using the `uploadResume` provider; on success `redirect(303, '/jobs?q='+query)`; api-mode-only guard like appointments actions: in mock mode the action calls `mockUploadResume` via the delegator — fine), the benchmark panel (top skills with share bars — widths via inline style percentage, colors via tokens), and the ranked result cards (title, company, location, matched skills as chips, missing skills muted, score only when profileAvailable). Each card links to `/jobs/job-<pk>`.
- Detail page (`/jobs/[id]`): load calls `getJobPosting(id)` — null/404 → `error(404, messages.jobs.notFound)`. Renders full description (in a `max-w-measure` prose block), skills, benchmark panel, external "View posting" link (`target="_blank" rel="noopener noreferrer"`), and the report section: a form action `?/report` calling `generateMatchReport(id)`; render the returned report from the action result (`use:enhance` per the appointments pattern); handle 409 no_resume (`fail(409, {error: messages.jobs.report.noResume})`) and 503 (`fail(503, {error: messages.jobs.report.unavailable})`). Report renders: competency label + score, matched skills, gaps, verdict paragraphs.
- Copy: full `jobs` block in `messages.ts` — documentTitle, eyebrow, title, intro, search placeholder/label/button, empty states (no query yet / no results), profile banner + upload labels, benchmark heading + sample-size line (function of n), card labels (match score, skills you have, skills to build), notFound, report copy (heading, generate button, generating, noResume, unavailable, competency labels map for the four values). Follow the file's commented style.
- Accessibility/conventions: labels on inputs, the results list as a semantic list, no `Date.now()` (postedAt formatted via existing `formatShortDate`), all colors via tokens, wide content in `overflow-x-auto` only if needed.
- Also register the route in whatever guards exist: grep for how `PagePlaceholder`/nav lookups treat unknown hrefs — `/jobs` must be a real page, not a placeholder.

- [ ] **Step 1: Write failing component/view-model specs** — before writing them, read one existing component spec to copy the harness. Cover at least: benchmark share rendering math (a pure helper `shareWidth(share) -> "NN%"` in a `jobs.ts` lib module if any logic is extracted), result-card competency label lookup from messages, and the search page's empty-state selection logic (no query vs no results) if extracted as a pure function. Keep components thin; extract pure logic to `frontend/src/lib/jobs.ts` and unit-test THAT (repo pattern: `ask.ts` + `ask.spec.ts`).
- [ ] **Step 2: Implement** nav + copy + lib + components + routes.
- [ ] **Step 3: Run ALL frontend gates**: `npm test`, `npm run check` (0/0), `npm run build`, plus the repo's extra gates if wired into npm scripts (`check-contrast`, `check:layout`, `check:interaction` — run whatever `package.json` defines; new pages must pass the contrast/layout/interaction sweeps).
- [ ] **Step 4: Commit**

```bash
git add frontend && git commit -m "feat(j): jobs tab — search, benchmark, detail, match report, resume upload"
```

---

### Task 10: Gates + e2e smoke + docs

**Files:**
- Modify: `backend/README.md` (jobs section: ingest_jobs, sources, report/upload endpoints, THRIVE_LLM notes)
- Test: full suites + live smoke (transcript in the report).

- [ ] **Step 1: Full gates**: backend `uv run pytest -q`; frontend `npm test && npm run check && npm run build` + layout/interaction/contrast gates per package.json.
- [ ] **Step 2: e2e smoke** (same-hostname localhost; kill servers by captured PID, never pkill):
  1. `uv run python manage.py migrate && uv run python manage.py seed_demo`.
  2. Seed postings WITHOUT network: `THRIVE_LLM=fake uv run python manage.py shell -c` a short script calling `ingest_from([FakeJobSource([...6 realistic rows...])], embeddings=get_embeddings())` (fake embeddings under THRIVE_LLM=fake).
  3. OPTIONAL real-source check (network permitting): `uv run python manage.py ingest_jobs` against the real Greenhouse/Lever boards — verify at least one source ingests real postings; a failing board slug gets corrected in `companies.json` (data fix, no review needed) or noted. Skip cleanly if offline.
  4. Start Django (`THRIVE_LLM=fake THRIVE_DEV_LOGIN_ENABLED=1`) + frontend (`THRIVE_API_ORIGIN=http://localhost:<port>`); dev-login demo/demo via cookie jar.
  5. `GET /api/thrive/jobs?q=analyst` → ranked results + benchmark (demo user's seeded resume exists? check seed_demo — if it seeds no current ResumeVersion, profileAvailable false is the correct assertion).
  6. `POST /api/thrive/jobs/<id>/report` → 503 under fake (get_llm raises) — proves the honest-failure path; with a real GEMINI_API_KEY present, restart without THRIVE_LLM and verify a real report generates and second call hits the cache. Skip the real half if no key (note it).
  7. Resume upload with a real small PDF (generate one with reportlab? NO — use any real PDF available, e.g. one page of an MGTA syllabus from "/Users/shankar/Documents/Rady Recommender/Old/MGTA/" purely as a text-bearing PDF to prove extraction; expect 503 under fake LLM after extraction succeeds — proving the parse path; with a real key expect 201).
  8. Browser check (Playwright if available): /jobs renders, search narrows, detail page renders, report button shows the unavailable message under fake LLM.
  9. Kill servers by PID.
- [ ] **Step 3: README section + commit**

```bash
git add backend frontend && git commit -m "feat(j): jobs smoke, gates, and docs"
```

---

## Deferred / carried

- **Aggregator source (Adzuna/JSearch)**: needs a (free) API key — adapter slots behind `JobSource`; backlog until a key exists.
- **Celery nightly ingest + expiry**: F5 schedules `ingest_jobs`; the command is already idempotent.
- **Postgres FTS**: F5 swap inside `_matching_postings` when the corpus outgrows icontains.
- **DOCX resumes**: v1 is PDF-only (kept deps flat); python-docx is a small add when wanted.
- **Benchmark caching**: computed per request; cache table only if posting volume makes it slow.
- **Skill vocabulary growth**: `skills_vocab.json` is versioned config — extend as real postings reveal gaps (the ingest recomputes skills on every run, so vocabulary edits self-heal the corpus).
- **companies.json curation**: starter list; board slugs verified at smoke — expand with MSBA-target employers over time.
