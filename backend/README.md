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
