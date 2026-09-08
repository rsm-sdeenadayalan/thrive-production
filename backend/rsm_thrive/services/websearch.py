"""Web search as a step this codebase runs, rather than one the model runs for us.

`LLM.search_chat` promises an answer grounded in something outside this
codebase. Exactly one backend could ever keep that promise by itself:
`CodexOAuthLLM`, because OpenAI's Responses API hosts the search loop on their
servers. Every other backend inherited the base-class fallback and quietly
answered from the model's own memory instead -- which is not wrong, but is not
what the caller asked for, and `role_lookup`'s prompt says "current postings"
in a sentence that then had nothing behind it.

TritonAI is the backend a deployment must run, and it CANNOT host that loop. It
is LiteLLM in front of self-hosted vLLM, an inference server whose whole job is
turning weights into tokens. Asked for a `web_search` tool it answers
`Input should be 'function'`: the only tools it knows are the kind where the
model asks and the CALLER executes. Confirmed against the live gateway on
2026-09-05, along with the model's own account of itself -- "I cannot look
things up."

So the search has to happen here, which turns out to be the better place for
it. When the provider runs the loop the pages it read are invisible to us and
the model's prose is all we get; when we run it we hold the URLs, and a
recommendation can say where its claims came from. That is what
`role_lookup.cite` renders, and it is the one thing the hosted loop never gave
us.

Providers are interchangeable and every one of them is optional -- `search()`
returns [] rather than raising, because a caller that cannot search must
degrade to the model's memory rather than lose the turn. `duckduckgo` needs no
key and is the default so that a laptop works out of the box; it parses a
public HTML endpoint, so it is also the one most likely to break on a markup
change, and anything that matters should set a keyed provider.
"""

import html
import logging
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger("rsm_thrive.websearch")

# One query, one lookup, for a few minutes. The keyless provider rate-limits
# hard -- measured on 2026-09-05, the fourth rapid query returned zero results
# in 0.4s where the first three took ~0.8s and returned three each -- and it
# signals that by serving a page which parses to nothing rather than by an
# error. So a burst degrades SILENTLY to ungrounded answers, which is the exact
# failure this module was written to end. Repeats are the cheapest half of that
# burst to remove.
#
# Only non-empty results are cached: storing a throttled miss would hold the
# failure open for the whole TTL.
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 15 * 60
_CACHE_MAX = 256

TIMEOUT_SECONDS = 12
DEFAULT_LIMIT = 6
# Long enough to carry the claim, short enough that six of them do not crowd
# out the instructions they are appended to.
SNIPPET_CHARS = 320


@dataclass(frozen=True)
class Result:
    title: str
    url: str
    snippet: str


def query_from(messages):
    """The search query hidden in a chat exchange: the last thing the user said.

    `search_chat` takes a system prompt and a message list, not a query, so
    something has to decide what to look up. The last user turn is the whole of
    it -- these callers send exactly one, holding the role name or the question.
    """
    for message in reversed(list(messages or [])):
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "").strip()[:300]
    return ""


def search(query, limit=DEFAULT_LIMIT):
    """[Result] for a query. Never raises; [] when unconfigured or failing.

    Tries each provider in `THRIVE_SEARCH` in turn and takes the first that
    answers, so a keyed provider can be configured before its key exists and a
    quota does not take grounding down with it.

    Returning [] rather than raising is the contract every caller is built on:
    a search that does not happen costs grounding, and a search that explodes
    would cost the student their turn.
    """
    query = str(query or "").strip()
    if not query:
        return []

    for provider in providers():
        results = _via(provider, query, limit)
        if results:
            return results
    return []


def providers():
    """The provider chain, in order of preference. Unknown names are dropped.

    A LIST rather than one name, because the two kinds of provider fail in
    opposite ways and cover for each other. The keyed ones stop at a quota or
    an unpaid bill; the keyless one is free and rate-limits by address, and its
    block clears on its own. `brave,duckduckgo` is the arrangement that has an
    answer for both -- and it is what lets a deployment adopt a keyed provider
    BEFORE the key exists, which is otherwise a flag day.
    """
    named = (getattr(settings, "THRIVE_SEARCH", "") or "none").lower()
    return [name for name in (part.strip() for part in named.split(","))
            if name in _PROVIDERS]


def _via(provider, query, limit):
    """One provider's results, or []. Never raises."""
    if provider in _NEEDS_KEY and not _key():
        # Configured but unusable, which is not the same as failing: with a
        # chain this is the ordinary state of the first provider before its key
        # arrives, so it is worth saying once and then moving on quietly.
        logger.info(
            "skipping %s: THRIVE_SEARCH_API_KEY is empty", provider)
        return []

    key = (provider, query.lower(), limit)
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
            return list(hit[1])

    try:
        results = _PROVIDERS[provider](query, limit)
    except Exception as exc:
        logger.warning("web search failed via %s: %s", provider, exc)
        return []
    results = [r for r in results if r.url][:limit]
    if not results:
        # Distinguishable in a log from "nobody asked": the keyless provider
        # answers a rate-limited request with an unparseable page, so zero
        # results after a real call is the shape throttling takes.
        logger.info("web search returned nothing via %s for %r", provider, query)
        return []

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(min(_CACHE, key=lambda k: _CACHE[k][0]), None)
        _CACHE[key] = (now, list(results))
    return results


def forget():
    """Drop the query cache. For tests, and for a deploy wanting a cold start."""
    with _CACHE_LOCK:
        _CACHE.clear()


GROUNDING = (
    "\n\nWeb results retrieved just now for this question. Ground what you say "
    "in these, and prefer them over anything you remember -- they are current "
    "and your training is not. If they do not cover it, say so rather than "
    "filling the gap from memory.\n\n")


def ground(system, results):
    """The system prompt with the retrieved pages appended, numbered.

    Numbered because a model asked to cite needs something to cite BY, and a
    number it can copy is harder to garble than a URL it has to reproduce
    character for character.
    """
    if not results:
        return system
    lines = []
    for index, result in enumerate(results, 1):
        lines.append(f"[{index}] {result.title}\n{result.url}\n{result.snippet}")
    return f"{system}{GROUNDING}" + "\n\n".join(lines)


def _get(url, **kwargs):
    import requests

    kwargs.setdefault("timeout", TIMEOUT_SECONDS)
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response


def _post(url, **kwargs):
    import requests

    kwargs.setdefault("timeout", TIMEOUT_SECONDS)
    response = requests.post(url, **kwargs)
    response.raise_for_status()
    return response


def _key():
    return getattr(settings, "THRIVE_SEARCH_API_KEY", "") or ""


def _clean(raw):
    """Tag soup to readable text. DuckDuckGo's snippets arrive as marked-up HTML."""
    return html.unescape(re.sub(r"<[^>]+>", "", raw or "")).strip()


_DDG_LINK = re.compile(
    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DDG_SNIPPET = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)


def _unwrap(href):
    """DuckDuckGo hands back its own redirector; the real URL is the uddg param."""
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return href


def _duckduckgo(query, limit):
    """Keyless, and therefore the default. Parses the public HTML endpoint.

    A user agent is sent because the endpoint serves an interstitial to clients
    that look automated, and an interstitial parses to zero results rather than
    to an error -- a silent failure this would otherwise never notice.
    """
    response = _get("https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36")})
    body = response.text
    if response.status_code == 202 or "result__a" not in body:
        # Being blocked and finding nothing are the same shape here: a 200-ish
        # page with no results in it. Measured 2026-09-05 -- roughly ten queries
        # from one address is enough, and the block arrives as HTTP 202 with an
        # anti-bot page. Worth its own log line, because the fix is a keyed
        # provider and not a better query.
        raise RuntimeError(
            f"duckduckgo returned no parseable results (HTTP "
            f"{response.status_code}); this address is most likely rate-limited "
            f"-- set THRIVE_SEARCH to a keyed provider")
    snippets = [_clean(s) for s in _DDG_SNIPPET.findall(body)]
    results = []
    for index, (href, title) in enumerate(_DDG_LINK.findall(body)[:limit]):
        results.append(Result(
            title=_clean(title),
            url=_unwrap(html.unescape(href)),
            snippet=(snippets[index] if index < len(snippets) else "")[:SNIPPET_CHARS],
        ))
    return results


def _brave(query, limit):
    payload = _get("https://api.search.brave.com/res/v1/web/search",
                   params={"q": query, "count": limit},
                   headers={"Accept": "application/json",
                            "X-Subscription-Token": _key()}).json()
    return [Result(title=row.get("title") or "",
                   url=row.get("url") or "",
                   snippet=_clean(row.get("description"))[:SNIPPET_CHARS])
            for row in (payload.get("web") or {}).get("results") or []]


def _serper(query, limit):
    payload = _post("https://google.serper.dev/search",
                    json={"q": query, "num": limit},
                    headers={"X-API-KEY": _key(),
                             "Content-Type": "application/json"}).json()
    return [Result(title=row.get("title") or "",
                   url=row.get("link") or "",
                   snippet=(row.get("snippet") or "")[:SNIPPET_CHARS])
            for row in payload.get("organic") or []]


def _tavily(query, limit):
    """Sends the key BOTH ways on purpose.

    Tavily moved from `api_key` in the body to an `Authorization: Bearer`
    header, and both forms are still documented in the wild. An invalid key
    returns the same 401 either way, so there is no way to tell from outside
    which one a given account's endpoint wants -- and guessing wrong looks
    exactly like a bad key. Extra fields are ignored, so sending both costs
    nothing and removes the question.
    """
    payload = _post("https://api.tavily.com/search",
                    json={"query": query, "max_results": limit,
                          "api_key": _key()},
                    headers={"Authorization": f"Bearer {_key()}",
                             "Content-Type": "application/json"}).json()
    return [Result(title=row.get("title") or "",
                   url=row.get("url") or "",
                   snippet=(row.get("content") or "")[:SNIPPET_CHARS])
            for row in payload.get("results") or []]


# Providers that cannot even be attempted without THRIVE_SEARCH_API_KEY.
_NEEDS_KEY = frozenset({"brave", "serper", "tavily"})

_PROVIDERS = {
    "duckduckgo": _duckduckgo,
    "ddg": _duckduckgo,
    "brave": _brave,
    "serper": _serper,
    "tavily": _tavily,
}


def cite(sources, lead):
    """A sources line for a web-grounded answer, or "" when nothing was read.

    A trailing markdown line rather than inline markers, matching how the
    resources bot lists the documents behind an answer -- one shape for "here
    is where this came from", wherever it appears.

    `lead` says what the WEB supplied, and the fixed tail says what it did not:
    the courses are the catalog's and were matched here, in Python. Blurring
    those two would undo the separation the whole uncurated path is built on.
    """
    listed = [s for s in (sources or []) if (s or {}).get("url")][:3]
    if not listed:
        return ""
    links = ", ".join(
        f"[{(s.get('title') or s['url'])[:60]}]({s['url']})" for s in listed)
    return (f"\n\n_{lead} — {links}. The courses are ours, matched against "
            "those skills._")
