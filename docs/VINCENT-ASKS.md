# Asks for Vincent (and other admins) — THRIVE deployment

Status date: 2026-08-27. **Every feature is built and working locally.**
Deployment (F5) is the only phase left, and everything in it is blocked on
access we do not have. Nothing below asks for development work — each item is
a permission, a setting, or a credential.

Current state: backend 529 tests green, frontend 840, plus five browser gates.
The whole app runs locally against a real corpus (261 documents / 2,451 chunks)
and 9,911 live job postings.

## Needs Vincent (server/platform owner)

1. **Caddy route** — one route in the fleet config:
   `/msba-brain/thrive/*` → `127.0.0.1:8037`. Everything else under
   `/msba-brain/` keeps going to the existing Django site on `:8036`.
   We know the fleet Caddyfile is generated, so we do not want to hand-edit
   it — tell us the mechanism, or add the snippet yourself.
   *Blocks: any URL at all that is not a laptop. This is the top one.*

2. **LaunchDaemon conventions** — we have admin and can install
   `com.rsm.thrive.web` (the SvelteKit Node server) ourselves; we just need to
   match fleet convention: naming, log paths (`logs/com.rsm.*.err.log`?), and
   the kickstart pattern. Daemon rather than agent, so it survives reboots.
   *Blocks: a deployment that stays up without someone logged in.*

3. **A scheduled job, same conventions** — job postings go stale, so
   `manage.py ingest_jobs` needs to run nightly (roughly 20 minutes, mostly
   waiting on other people's job boards). Whatever the fleet uses — a launchd
   timer, cron, something else. *Blocks: the career feed staying current;
   today it is a snapshot someone refreshes by hand.*

4. **Postgres** — a database (e.g. `thrive_db`), or permission to add our
   tables to `msba_brain_db`, plus a user and password we can put in the
   server's environment. Roughly **400MB and growing**, most of it job
   postings and their embeddings.
   *Blocks: server-side data. Local dev is on SQLite and unaffected.*
   **pgvector is NOT needed** — an earlier version of this list asked for it.
   Retrieval is portable Python cosine over a few thousand chunks, which is
   fast enough at this size. It becomes worth having if the corpus grows by an
   order of magnitude; not before, so please ignore that earlier ask.

5. **Outbound network access from the box** — two destinations:
   - `tritonai-api.ucsd.edu` (every chatbot answer, match score and embedding)
   - the public job boards we ingest from: `boards-api.greenhouse.io`,
     `api.lever.co`, `api.ashbyhq.com`, and company career domains
   If egress is restricted, we need these allowed. *Blocks: chatbots and the
   career feed, i.e. most of the app.* (We confirmed TritonAI is reachable
   from the open internet, so no VPN is involved.)

6. **SMTP** — which relay and settings the fleet uses for outbound mail. We
   send calendar invites (ICS) to the student and to the advisor when an
   appointment is booked. *Blocks: real emails from the server. Bookings work
   without it; the invitations just do not arrive.*

7. **Where the component should live, and how it gets there** — our Django
   component is `backend/` in
   `github.com/rsm-sdeenadayalan/thrive-production` (public). We do not have a
   checkout on the box and no location has been agreed, so this is an open
   question rather than a preference between known options: where would you
   like it to sit, and would you rather we clone and pull there ourselves, or
   have it installed some other way? *Blocks: F5 integration.*

   (An earlier version of this doc named `/srv/django/rsm-guild-ai-brain`,
   branch `feat/msba-brain`, as the target. That came from the original design
   note and we have no such checkout — treat it as a proposal that was never
   set up, not as something already in place.)

## Needs other admins (Vincent may know who to ask)

8. **Zoom Server-to-Server OAuth app** — from whoever owns the Rady/UCSD Zoom
   account: one app created, then its account ID, client ID and client secret.
   *Blocks: real Zoom links on booked appointments. We build against a fake
   client meanwhile, so the booking flow itself already works.*

## What we supply, so nobody waits on us

- **TritonAI API key** — we hold it. It goes in the server's environment as
  `TRITONAI_API_KEY`; it is never committed. Models in use are
  `claude-sonnet-4-6` (chat) and `api-tgpt-embeddings` (1024-dim embeddings).
- **The corpus and the job data** — both are reproducible on the server with
  management commands once the database exists.
- **Everything else.** All five phases are built: backend core, appointments,
  course requests and living resume, the frontend on the real API, both
  chatbots, the planner, and the career job search.

## Withdrawn or superseded

- ~~**Shared `ai_service`**~~ — superseded 2026-08-23. The backend runs on
  TritonAI, so no shared `ai_service` is needed. (An earlier version of this
  doc named `claude-opus-4-6-v1`; that model does not exist on the proxy —
  the real one is `claude-sonnet-4-6`.)
- ~~**Canvas API access**~~ — withdrawn 2026-08-23. Canvas integration is out
  of scope; academic data is seeded or admin-entered. Revisit only if the
  program wants live assignment sync later.
- ~~**Tailnet/firewall for previews**~~ — no longer needed. Previews now go
  through a Cloudflare tunnel or an SSH tunnel, so no raw ports are exposed.
