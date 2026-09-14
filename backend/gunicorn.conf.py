"""Gunicorn settings for the THRIVE API.

Bound to loopback on purpose. Nothing reaches this process directly: Tailscale
Serve terminates HTTPS on the tailnet and proxies to it, so binding a public
interface would only widen what can reach Django without adding a single
capability.

## Threads, not more workers

`services/jobs/report.py` scores a shortlist across a bounded thread pool while
the request waits on the network, so a request spends most of its life blocked
on TritonAI rather than burning CPU. Threads serve that shape well and share one
SQLite connection pool per worker; adding processes instead would multiply the
memory held for a 345MB database and multiply writers against a file that takes
one at a time.

Two workers rather than one so a crash or a slow request cannot take the whole
API down, which for a test group is the difference between one person seeing an
error and everybody seeing one.

## The timeout

Ninety seconds. It must sit ABOVE the courses bot's per-turn budget
(TRITONAI_TURN_BUDGET_SECONDS, 75s) or gunicorn would kill a slow turn before
the app's own budget can return a graceful answer. A cold career search is the
other outlier: it fans out roughly 24 LLM scoring calls. The default 30s would
kill exactly the requests these features exist to serve, leaving the student a
worker timeout instead of results.
"""

bind = "127.0.0.1:8039"
workers = 2
threads = 4
timeout = 90
graceful_timeout = 30

# Long enough that a keep-alive connection survives a student reading a page,
# short enough that dead connections are not held forever.
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"

# The proxy is Tailscale Serve on loopback, so forwarded headers from it are
# trustworthy. Without this Django builds absolute URLs as http:// and the
# https:// the browser actually used is lost, which breaks redirects after
# login.
forwarded_allow_ips = "127.0.0.1"
