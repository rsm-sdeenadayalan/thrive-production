# THRIVE Admin Console — Design

**Date:** 2026-09-12
**Status:** Design, build in progress on branch `admin-console`
**Author:** Shankar (with Claude)

## Goal

A robust, integrated backend UI that lets **admin staff and faculty** operate the
whole THRIVE system: manage the content the bots answer from, oversee the chat
record and answer quality, review and correct course information, and administer
students, appointments, events, jobs, and program configuration — without
touching code or the shell.

## Architecture decision

**Build on Django Admin, branded as the "THRIVE Console," rather than a bespoke
SvelteKit admin.**

Why:
- The app is Django; admin ships free CRUD, search, filtering, permissions, and
  an audit log across all ~30 models. A hand-built SvelteKit admin would
  re-implement all of that at large cost.
- The pattern already exists: `rsm_thrive/admin.py` is a narrow trace/feedback
  admin. This extends the same surface instead of adding a parallel one.
- Auth is already wired — LDAP login, an allowlist, and staff gating. Admin
  reuses `is_staff` / Django groups directly.

Tradeoff: Django admin is staff-oriented, not a consumer-grade UI. For
non-technical faculty it is serviceable and themeable, and the highest-value
faculty tasks (answer review, course content) get purpose-built admin views.
If a fully bespoke faculty UI is later wanted, this console remains the
staff/admin backbone. This decision is recorded so it can be revisited.

## Access model

Two Django groups, mapped from auth at login:

- **THRIVE Admin** — staff; full console access.
- **THRIVE Faculty** — scoped access: their course content, faculty answer
  review, and read-only oversight. No student PII beyond what advising needs.

`is_superuser` remains for the maintainer. Faculty and admin are Django groups
with per-model permissions; custom views check group membership. Login
(`THRIVE_AUTH=ucsd_ldap`) assigns the group; a documented allowlist/role file
drives who is admin vs faculty.

## Structure

Convert admin registration into a package so the console is modular:

```
rsm_thrive/admin.py                     # keeps trace admin; imports the package
rsm_thrive/admin_modules/
  __init__.py     # branding (site header/title), base classes, imports submodules
  content.py      # catalog + corpus + careers + bundles management  ← flagship
  oversight.py    # conversations, turns, feedback, refusals (extends existing)
  academic.py     # degree, planner, courses, plan-of-study records
  people.py       # students, profiles, requests (read-mostly, PII-guarded)
  scheduling.py   # advisors, appointments, events
  careers.py      # jobs, resume records
  knowledge.py    # resources / knowledge base entries
```

Django autodiscovers `rsm_thrive.admin`; `admin.py` imports `admin_modules`, so
every submodule registers. Branding sets `site_header = "THRIVE Console"`,
`site_title`, and `index_title`.

## Content management (the flagship module)

The bots answer from two content stores that are **not** ordinary DB rows, so
they get custom admin views rather than model CRUD:

- **Catalog JSON** — `data/catalog/{courses,careers,bundles}.json`, loaded by the
  `services` layer. The console offers: view current entries, edit/add/remove,
  validate on save, and a **"Rebuild catalog"** action that runs the existing
  `build_catalog` command and re-ingests, so an edit reaches the bots.
- **Corpus** — markdown under `data/corpus/*`, ingested into `DocumentChunk` rows.
  The console offers: browse documents, upload/replace a markdown file, and a
  **"Re-ingest"** action wrapping `ingest_corpus`. Ingestion must run on the
  production embedding backend (TritonAI) so vectors match query dimensions.

These close the loop with the Insights work in the Phase 2 PRD: a content gap
identified there is fixed here.

## Oversight

Extend the existing trace admin: conversations and turns (read-only), feedback,
a refusals view, and a faculty-facing **answer review** where an instructor sees
what the bot said about their course and flags or corrects it (writes a
correction the retrieval/answer layer can honor).

## Non-goals

- Not a student-facing UI; students use the existing SvelteKit app.
- Not a replacement for SIS; academic records are managed read-mostly.
- No destructive bulk operations without confirmation and, for content, a
  re-ingest step.

## Testing

Django + pytest (`THRIVE_LLM=fake uv run pytest`). Each module ships tests:
admin registration loads, permissions gate correctly (admin vs faculty vs
anonymous), and custom content views validate input and invoke the right
command. Build module by module, each independently testable and committed.

## Build order

1. **Foundation** — package structure, branding, groups/permissions, base
   classes, and a smoke test that the admin index loads for a staff user.
2. **Content management** — catalog + corpus views with rebuild/re-ingest.
3. **Oversight** — extend traces; faculty answer review.
4. **Records** — academic, scheduling, careers, people, knowledge admins.
