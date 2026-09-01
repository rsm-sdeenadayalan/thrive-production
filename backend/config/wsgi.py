"""WSGI entrypoint, for running under a real server rather than `runserver`.

`manage.py runserver` is a development server: it reloads on file changes,
serves single-threaded by default, and Django itself says not to deploy it. It
was the only way this project had ever been started, which was fine while the
only audience was a developer on a laptop and is not fine for a LaunchDaemon
serving a test group.

WSGI rather than ASGI. Nothing here is async: there are no websockets, no
channels, and the one piece of concurrency (the parallel match-report scoring in
`services/jobs/report.py`) uses a thread pool, which a threaded WSGI worker
serves correctly. ASGI would add an event loop and a protocol layer that no code
in this project asks for.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
