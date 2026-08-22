# THRIVE — Production

Production home of THRIVE, the Rady MSBA student hub: dashboard, calendar,
appointments with CMC/GSA advisors (Zoom + calendar invites), an FAQ chatbot,
an electives recommender, and a job-search tab with resume-based suitability
ranking.

Deployed on the Rady Mac Studio inside the `rsm-msba-brain` Django platform at
`https://ms-macos.tail37260b.ts.net/msba-brain/thrive/` (Tailscale + UCSD AD
login required).

## Layout

```
frontend/    SvelteKit app — forked from rsm-msaad/thrive, patched for
             production (base path, auth hooks, real provider bodies)
backend/     rsm-django-thrive — the Django component (API, models, Celery
             pipelines, chatbots, job search)
scripts/     repo-wide checks (browser gates, contrast) — from upstream
docs/
  specs/     design specifications (start with the backend design spec)
  upstream/  the original thrive repo's documentation, kept for reference —
             BACKEND.md is the provider contract the API satisfies
```

## Provenance

`frontend/`, `scripts/`, and `docs/upstream/` originate from
[rsm-msaad/thrive](https://github.com/rsm-msaad/thrive) (all frontend design
and its documentation are that project's work). That repo is **read-only** for
this team: development happens here and is never pushed upstream.

This repo does not deploy to Netlify — upstream's `netlify.toml` was
intentionally not carried over. The frontend builds with `adapter-node`
(`npm run build:node`) and runs as a LaunchDaemon behind the fleet Caddy.

## Where to start

1. `docs/specs/2026-08-21-thrive-backend-design.md` — the architecture, agreed
   decisions, and phased build order (Foundation → Chatbots → Job search).
2. `docs/upstream/BACKEND.md` — the 27-provider contract the API implements.
3. `frontend/README.md` (upstream) — running the frontend and its six gates.
