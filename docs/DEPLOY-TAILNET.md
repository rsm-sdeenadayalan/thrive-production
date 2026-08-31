# Deploying THRIVE on the Rady Mac Studio for tailnet testers

Written 2026-08-31, from a survey of the actual machine rather than from the
design note. Target audience: a test-subject group from the MSBA cohort, all of
whom are on the tailnet.

## What already works, verified

- `https://ms-macos.tail37260b.ts.net` answers **200** from a laptop on the
  tailnet. Tailscale Serve terminates HTTPS and proxies `/` to Caddy on
  `127.0.0.1:8899`, which fans out to the ~40 fleet apps under `/msba-brain/`
  and friends. **Tailnet delivery is a solved problem — nothing to build.**
- SSH works as `sdeenadayalan@ms-macos` (macOS 15.7.7).
- Installed already: `node v26.5.0`, `caddy`, `python3.13`, Postgres 16
  (running), `tailscale`. All under `/opt/homebrew`.
- The fleet's LaunchDaemon convention is readable from
  `/Library/LaunchDaemons/com.rsm.*.plist` — `com.rsm.<app>.web`, a shared
  runner at `/srv/django/_migration/scripts/svc/run_web.sh`, logs at
  `/srv/django/<app>/logs/com.rsm.<app>.web.{out,err}.log`. No need to ask
  what the convention is; it is on the box.

## What blocks us, verified

1. **`/srv/django` is `drwx------ vnijs:staff`.** Not readable or writable by
   us, and it holds every fleet app plus the Caddy config.
2. **`sudo` requires a password we do not have.** So no LaunchDaemon install.
3. **The macOS application firewall blocks our Node.** It allows
   `/Users/vnijs/.nvm/versions/node/v23.11.1/bin/node`; our processes run
   `/opt/homebrew/bin/node`, which is not on the list. Demonstrated: the
   existing `~/thrive-preview` on port 4321 returns 200 from the machine itself
   and refuses connections from a tailnet peer.
4. **No Postgres role** for `sdeenadayalan` (`FATAL: role does not exist`).
5. **Tailscale's `OperatorUser` is unset**, so `tailscale serve` is readable by
   us but not writable — changing the serve config needs root.

## The sub-path trap — why NOT to route `/msba-brain/thrive/*`

The original spec proposed a Caddy route at `/msba-brain/thrive/*` → our Node
server, with `kit.paths.base = '/msba-brain/thrive'`. **That does not work
without a refactor**, and the failure is quiet.

Tested it: with `paths.base` set, SvelteKit correctly emits client assets under
`client/msba-brain/thrive/_app/...`, and the served page returns 200. But the
app's own links come back **bare** — `href="/"`, `href="/jobs"`,
`href="/appointments"`. `paths.base` moves assets; it does not rewrite links
written as absolute strings.

This codebase has 22+ hardcoded root-relative paths (16 `href`, 5
`goto`/`redirect`, 1 form `action`), plus template-built ones, and **nothing
imports `base` from `$app/paths`**. Every one of them would need changing, with
840 frontend tests asserting on paths. That is a real refactor with real
regression risk, and doing it immediately before a user test means the testers
find our routing bugs instead of THRIVE's usability bugs.

The change was written, tested, and reverted. Do not re-add `paths.base` alone
— it looks like it works (the page loads) and then every link is wrong.

## The recommended shape: serve at the ROOT on an alternate HTTPS port

Tailscale Serve can expose a second HTTPS port on the same machine name:

```
tailscale serve --bg --https=8443 http://127.0.0.1:8037
```

That gives testers `https://ms-macos.tail37260b.ts.net:8443/` — our app at the
**root path**, so no base-path refactor. It also sidesteps blockers 3 and 5
above: `tailscaled` does the listening (already allowed through the firewall)
and it proxies to loopback, so our Node process never needs an inbound firewall
exception. Tailnet-only, which is what we want for a test group.

It does not disturb the existing `/` → `:8899` mapping on port 443.

**Postgres is not needed for this phase.** Django defaults to SQLite here
(`THRIVE_PG=1` opts into Postgres); for a test group of this size SQLite is
adequate, and it removes blocker 4 entirely.

## What we still need from Vincent

Two things, both one-time:

1. **Either** run the `tailscale serve` line above once, **or** — better —
   `sudo tailscale set --operator=sdeenadayalan`, which lets us manage our own
   serve mappings from then on without coming back to him.
2. **A LaunchDaemon so it survives reboot.** `com.rsm.thrive.web`, following
   the fleet pattern, but pointed at our home directory rather than
   `/srv/django`. Installing it needs sudo. Without this the app dies on the
   next restart, which for a test group means testers hitting a dead link.

Everything else — code, build, database, the TritonAI key, keeping it current
— is ours and needs nothing from him.

## Later, if this graduates from a test to a real service

Then the fleet path (`/srv/django`, a Caddy route, Postgres, the full
LaunchDaemon) is the right home, and the base-path refactor becomes worth
doing properly. It is not worth doing to run a test.
