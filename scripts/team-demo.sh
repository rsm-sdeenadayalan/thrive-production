#!/bin/bash
# Share the local THRIVE demo with the team through one public URL.
#
#   ./scripts/team-demo.sh          start everything, print the URL
#   ./scripts/team-demo.sh stop     stop everything this script started
#
# What it runs (all local; your Mac must stay awake while people browse):
#   - Django API on 127.0.0.1:8003
#   - SvelteKit dev server on 127.0.0.1:5174, proxying /api to Django so the
#     whole app lives on ONE hostname (cookies are host-scoped)
#   - a Cloudflare quick tunnel exposing 5174 at a random *.trycloudflare.com
#     URL (new URL each start; no account needed)
#
# Team sign-in: demo / demo (the seeded dev user). The URL is unlisted but
# public — anyone with the link can view the demo data.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.team-demo"
mkdir -p "$RUN"

if [ "${1:-}" = "stop" ]; then
  for f in "$RUN"/*.pid; do
    [ -f "$f" ] || continue
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  done
  echo "team demo stopped."
  exit 0
fi

command -v cloudflared >/dev/null || { echo "cloudflared missing: brew install cloudflared"; exit 1; }

# 1. Tunnel first — its random URL feeds the servers' env.
cloudflared tunnel --url http://localhost:5174 > "$RUN/tunnel.log" 2>&1 &
echo $! > "$RUN/tunnel.pid"
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$RUN/tunnel.log" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "tunnel never came up — see $RUN/tunnel.log"; exit 1; }
HOST="${URL#https://}"

# 2. Django, trusting the tunnel host for the browser-facing dev-login hop.
(
  cd "$ROOT/backend"
  THRIVE_EXTRA_HOSTS="$HOST" \
  THRIVE_FRONTEND_ORIGINS="$URL,http://localhost:5174,http://localhost:5173" \
  uv run python manage.py runserver 8003 > "$RUN/backend.log" 2>&1 &
  echo $! > "$RUN/backend.pid"
)

# 3. Frontend in tunnel mode: /api proxied to Django, tunnel Host accepted,
#    login redirect kept relative so it stays on the public hostname.
(
  cd "$ROOT/frontend"
  THRIVE_TUNNEL_HOST="$HOST" \
  THRIVE_API_ORIGIN="http://localhost:8003" \
  THRIVE_LOGIN_URL="/api/thrive/dev-login" \
  npm run dev -- --port 5174 --strictPort > "$RUN/frontend.log" 2>&1 &
  echo $! > "$RUN/frontend.pid"
)

# 4. Wait until the public URL actually serves the app.
for _ in $(seq 1 45); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -L "$URL" || true)"
  [ "$code" = "200" ] && break
  sleep 2
done

echo
echo "  Share this with the team:  $URL"
echo "  Sign in with:              demo / demo"
echo "  Keep this Mac awake; stop with: ./scripts/team-demo.sh stop"
echo "  Logs: $RUN/{tunnel,backend,frontend}.log"
