# Asks for Vincent (and other admins) — THRIVE deployment

Status date: 2026-08-22. Development continues locally regardless; each item
below only blocks the step named next to it.

## Needs Vincent (server/platform owner)

1. **Caddy route** — one route in the fleet config: `/msba-brain/thrive/*` →
   `127.0.0.1:<port>` (8037 is already taken on the box; any free 80xx port —
   your call). We know the fleet Caddyfile is generated, so we don't want to
   hand-edit it; tell us the mechanism or add the snippet. *Blocks: public
   URL under /msba-brain/ (F5).*
2. **LaunchDaemon conventions** — we have admin and can install
   `com.rsm.thrive.web` (SvelteKit Node server) + later a Celery worker as
   LaunchDaemons; confirm naming/log-path conventions so we match the fleet
   (`logs/com.rsm.*.err.log`, kickstart pattern). *Blocks: reboot-surviving
   deployment (F5).*
3. **Postgres** — a database (e.g. `thrive_db`) or permission to add our app's
   tables to `msba_brain_db`, plus `CREATE EXTENSION vector` (pgvector) for
   the chatbot retrieval index. Is pgvector installed on your Postgres build?
   *Blocks: server data + chatbot corpus (F5/Phase C). Local dev unaffected.*
4. **Shared ai_service** — OK to use the platform `ai_service`
   (rsm-django-assessment) / shared OAuth provider for the FAQ bot and
   electives recommender? What config/quota should we point at? *Blocks:
   chatbot LLM calls on the server (Phase C). We have a Gemini fallback.*
5. **SMTP** — which relay/settings the fleet uses for outbound mail, for
   appointment calendar invites (ICS) to students and CMC/GSA advisors.
   *Blocks: real emails from the server (F2 side effects in production).*
6. **Component wiring preference** — our Django component lives in
   github.com/rsm-sdeenadayalan/thrive-production (`backend/`). For the
   platform checkout (/srv/django/rsm-guild-ai-brain, branch feat/msba-brain):
   symlink, pip path-install, or mirrored push? *Blocks: F5 integration.*
7. **Tailnet/firewall for previews (optional, nice-to-have)** — do tailnet
   ACLs allow non-443 ports? We run temporary user-space previews on high
   ports (currently 4321); the macOS app firewall also needs `node` allowed
   for inbound. If you'd rather we never expose raw ports, say so and we'll
   stick to SSH tunnels until the Caddy route exists.

## Needs other admins (Vincent may know who)

8. **Zoom Server-to-Server OAuth app** (Rady/UCSD Zoom account owner): one
   app created → account ID, client ID, client secret. *Blocks: real Zoom
   links on bookings; we build against a fake client meanwhile.*
9. ~~**Canvas API access** (IT/program)~~ — **withdrawn for now**: Canvas
   integration is out of scope (decision 2026-08-23). Academic data stays
   admin-seeded; revisit if the program wants live assignment sync later.

## What we're doing meanwhile (no dependencies)

- F2a: appointments backend — booking with race-safe slots, ICS invite
  emails, Zoom behind a swappable client (fake until #8 lands).
- F2b: course-request + living-resume providers.
- ~~F3: Canvas ingestion~~ — dropped (2026-08-23); academic data is seeded/admin-entered.
- F4: wiring the SvelteKit frontend to the API behind UCSD login.
- Phases C/J: chatbots + job search (local Postgres/pgvector via Docker).
