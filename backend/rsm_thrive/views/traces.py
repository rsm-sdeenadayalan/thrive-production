"""Reading the turn log back.

`ChatTurnLog` has been written since the chatbots landed and never read. That
is the whole gap this closes: when a tester says "that answer was bad", the
evidence is already in the database, and until now there was no way to look at
it. The point of having it before testing starts rather than after is that a
fortnight of testing produces a set of labelled failures instead of a set of
remembered impressions.

Staff only. A trace carries another student's question and another student's
answer verbatim, so this is not a student-facing surface however useful it
would be to one.
"""

import datetime as dt

from django.utils import timezone
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import ChatTurnLog, DocumentChunk
from rsm_thrive.serializers.traces import _chunk_payload, turn_payload

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def staff_required(view):
    """Use under `api_login_required`."""
    import functools

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return json_error("forbidden", "Staff access only.", 403)
        return view(request, *args, **kwargs)
    return wrapper


def _int_param(request, name, default, maximum):
    raw = request.GET.get(name)
    if raw is None or not raw.isdigit():
        return default
    return max(1, min(maximum, int(raw)))


def _since(request):
    """`?since=` as a date or an instant, or `?days=N`.

    Both spellings, because both get typed: a date is what you reach for when
    you know when the bad turn happened, and a day count is what you reach for
    when you want "this week's" and would otherwise have to work the date out.
    """
    raw = (request.GET.get("since") or "").strip()
    if raw:
        try:
            parsed = dt.datetime.fromisoformat(raw)
        except ValueError:
            return None, f"since must be an ISO date or instant, not {raw!r}."
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed, None
    days = request.GET.get("days")
    if days and days.isdigit():
        return timezone.now() - dt.timedelta(days=int(days)), None
    return None, None


def _filtered(request):
    rows = (ChatTurnLog.objects
            .select_related("message", "message__conversation",
                            "message__conversation__user", "feedback",
                            "feedback__user"))
    bot = request.GET.get("bot")
    if bot:
        rows = rows.filter(bot=bot)
    route = request.GET.get("route")
    if route:
        rows = rows.filter(route=route)
    model_note = request.GET.get("model_note")
    if model_note:
        rows = rows.filter(model_note=model_note)
    if request.GET.get("refused") in ("1", "true"):
        rows = rows.filter(refused=True)
    elif request.GET.get("refused") in ("0", "false"):
        rows = rows.filter(refused=False)
    thumbs = request.GET.get("thumbs")
    if thumbs in ("up", "down"):
        rows = rows.filter(feedback__rating=thumbs)
    elif thumbs in ("any", "rated"):
        rows = rows.filter(feedback__isnull=False)
    elif thumbs == "none":
        rows = rows.filter(feedback__isnull=True)
    query = (request.GET.get("q") or "").strip()
    if query:
        rows = rows.filter(question__icontains=query)
    student = (request.GET.get("student") or "").strip()
    if student:
        rows = rows.filter(message__conversation__user__username=student)
    return rows


def _chunk_index(turns):
    """Every chunk the listed turns cited, fetched once."""
    wanted = {cid for turn in turns for cid in (turn.chunk_ids or [])
              if isinstance(cid, int)}
    if not wanted:
        return {}
    return {chunk.pk: _chunk_payload(chunk)
            for chunk in (DocumentChunk.objects.filter(pk__in=wanted)
                          .select_related("document"))}


@api_login_required
@staff_required
@require_http_methods(["GET"])
def traces(request):
    since, problem = _since(request)
    if problem:
        return json_error("bad_request", problem, 400)
    rows = _filtered(request)
    if since is not None:
        rows = rows.filter(created_at__gte=since)
    limit = _int_param(request, "limit", DEFAULT_LIMIT, MAX_LIMIT)
    turns = list(rows[:limit])
    chunks = _chunk_index(turns) if request.GET.get("chunks") in ("1", "true") else None
    return json_ok({
        "count": len(turns),
        "traces": [turn_payload(turn, chunks) for turn in turns],
    })


@api_login_required
@staff_required
@require_http_methods(["GET"])
def trace(request, trace_id):
    if not trace_id.startswith("turn-") or not trace_id.removeprefix("turn-").isdigit():
        return json_error("unknown_trace", f"No trace {trace_id}.", 404)
    row = (ChatTurnLog.objects
           .select_related("message", "message__conversation",
                           "message__conversation__user", "feedback",
                           "feedback__user")
           .filter(pk=trace_id.removeprefix("turn-")).first())
    if row is None:
        return json_error("unknown_trace", f"No trace {trace_id}.", 404)
    # A single trace always inlines its chunks. Opening one IS the request to
    # see what the model was looking at.
    return json_ok(turn_payload(row, _chunk_index([row])))


@api_login_required
@staff_required
@require_http_methods(["GET"])
def refusals(request):
    """The content backlog: what students asked that we could not answer.

    Grouped by question rather than listed turn by turn, because the useful
    unit is "how many people needed this and nobody could tell them", not "here
    are 40 rows". Written by the people who need the material, which is the
    only requirements document for a corpus that anyone actually reads.

    `out-of-scope` routes are excluded by default and countable with
    `?scope=all`. A question the bot correctly declined is not a gap in the
    corpus — filing "what's the weather" as content to write would bury the
    real backlog under noise.
    """
    since, problem = _since(request)
    if problem:
        return json_error("bad_request", problem, 400)
    rows = ChatTurnLog.objects.filter(refused=True)
    if since is not None:
        rows = rows.filter(created_at__gte=since)
    if request.GET.get("scope") != "all":
        rows = rows.exclude(route="out-of-scope")
    bot = request.GET.get("bot")
    if bot:
        rows = rows.filter(bot=bot)

    grouped = {}
    for turn in rows.only("question", "bot", "route", "created_at"):
        key = " ".join((turn.question or "").lower().split())
        if not key:
            continue
        entry = grouped.setdefault(key, {
            "question": turn.question.strip(), "asked": 0,
            "bots": set(), "routes": set(), "lastAsked": turn.created_at,
        })
        entry["asked"] += 1
        entry["bots"].add(turn.bot)
        if turn.route:
            entry["routes"].add(turn.route)
        entry["lastAsked"] = max(entry["lastAsked"], turn.created_at)

    from rsm_thrive.serialize import iso_instant

    backlog = sorted(grouped.values(),
                     key=lambda row: (-row["asked"], row["question"]))
    limit = _int_param(request, "limit", DEFAULT_LIMIT, MAX_LIMIT)
    return json_ok({
        "count": len(backlog),
        "refusals": [{
            "question": row["question"],
            "asked": row["asked"],
            "bots": sorted(row["bots"]),
            "routes": sorted(row["routes"]),
            "lastAsked": iso_instant(row["lastAsked"]),
        } for row in backlog[:limit]],
    })
