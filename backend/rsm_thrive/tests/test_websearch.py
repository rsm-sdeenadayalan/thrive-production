"""Web search as a step we run: the lookup, the grounding, and the citation.

The bug this whole module exists to prevent is a SILENT one. `search_chat`
promised a web lookup, TritonAI could not perform one, and the base class
quietly delegated to `chat` -- so the prompt said "current postings" and the
answer came from training data, with nothing anywhere to say so. Every test
below is really the same test: that the promise and the behaviour agree.
"""

import pytest

from rsm_thrive.services import websearch
from rsm_thrive.services.llm import LLM, FakeLLM


class Recorder(LLM):
    """Records the system prompt it was handed, so grounding can be inspected."""

    def __init__(self, reply="{}"):
        self.reply = reply
        self.systems = []

    def chat(self, system, messages, json_mode=False):
        self.systems.append(system)
        return self.reply


def _results(count=2):
    return [websearch.Result(f"Title {i}", f"https://example.com/{i}", f"Snippet {i}")
            for i in range(count)]


class TestQueryFrom:
    def test_takes_the_last_user_turn(self):
        assert websearch.query_from([
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "esports analyst"},
        ]) == "esports analyst"

    @pytest.mark.parametrize("messages", [[], None, [{"role": "assistant", "content": "x"}]])
    def test_no_user_turn_is_empty_not_an_error(self, messages):
        assert websearch.query_from(messages) == ""

    def test_a_long_turn_is_trimmed(self):
        assert len(websearch.query_from(
            [{"role": "user", "content": "x" * 900}])) == 300


class TestSearchIsAlwaysSafe:
    def test_off_by_default_in_tests(self, settings):
        assert settings.THRIVE_SEARCH == "none"
        assert websearch.search("anything") == []

    def test_unknown_provider_returns_empty(self, settings):
        settings.THRIVE_SEARCH = "altavista"
        assert websearch.search("anything") == []

    def test_blank_query_never_calls_a_provider(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_duckduckgo",
                            lambda *a: pytest.fail("provider called on a blank query"))
        assert websearch.search("   ") == []

    def test_a_provider_that_raises_degrades_to_empty(self, settings, monkeypatch):
        """A search that explodes must cost grounding, never the student's turn."""
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "duckduckgo": lambda *a: (_ for _ in ()).throw(RuntimeError("network"))})
        assert websearch.search("esports analyst") == []

    def test_results_without_a_url_are_dropped(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS", {"duckduckgo": lambda *a: [
            websearch.Result("no link", "", "snippet"),
            websearch.Result("good", "https://example.com", "snippet")]})
        assert [r.url for r in websearch.search("q")] == ["https://example.com"]

    def test_limit_is_honoured(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: _results(10)})
        assert len(websearch.search("q", limit=3)) == 3


class TestGround:
    def test_no_results_leaves_the_prompt_alone(self):
        assert websearch.ground("SYSTEM", []) == "SYSTEM"

    def test_results_are_numbered_and_carry_their_urls(self):
        grounded = websearch.ground("SYSTEM", _results(2))
        assert grounded.startswith("SYSTEM")
        assert "[1]" in grounded and "[2]" in grounded
        assert "https://example.com/0" in grounded
        assert "Snippet 1" in grounded

    def test_it_tells_the_model_to_prefer_them_over_memory(self):
        assert "prefer them over anything you remember" in websearch.ground(
            "SYSTEM", _results(1))


class TestUnwrap:
    def test_duckduckgo_redirect_yields_the_real_url(self):
        assert websearch._unwrap(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x"
        ) == "https://example.com/a"

    def test_a_plain_url_is_left_alone(self):
        assert websearch._unwrap("https://example.com/a") == "https://example.com/a"


class TestSearchChatActuallySearches:
    """The regression. Before this, every non-codex backend answered from memory."""

    def test_the_prompt_is_grounded_in_what_was_found(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: _results(2)})
        llm = Recorder()
        llm.search_chat("SYSTEM", [{"role": "user", "content": "esports analyst"}])
        assert "https://example.com/0" in llm.systems[0], \
            "search_chat answered without the pages it claims to be grounded in"

    def test_sources_come_back_to_the_caller(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: _results(2)})
        got = []
        Recorder().search_chat("SYSTEM", [{"role": "user", "content": "q"}],
                               sources_out=got)
        assert [r.url for r in got] == ["https://example.com/0", "https://example.com/1"]

    def test_no_search_leaves_the_prompt_untouched(self, settings):
        settings.THRIVE_SEARCH = "none"
        llm = Recorder()
        got = []
        llm.search_chat("SYSTEM", [{"role": "user", "content": "q"}], sources_out=got)
        assert llm.systems == ["SYSTEM"] and got == []

    def test_the_codex_backend_is_left_to_its_own_loop(self, settings, monkeypatch):
        """Native search beats one bolted on, and its pages are not ours to show."""
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: pytest.fail(
                                "codex must not be routed through our search")})
        from rsm_thrive.services.llm import CodexOAuthLLM

        seen = {}

        class Stub(CodexOAuthLLM):
            def __init__(self):
                pass

            def chat(self, system, messages, json_mode=False, search=False):
                seen["search"] = search
                return "ok"

        got = []
        Stub().search_chat("SYSTEM", [{"role": "user", "content": "q"}], sources_out=got)
        assert seen["search"] is True and got == []


class TestTheQueryCache:
    """Repeats are free, misses are not cached, and tests never share state."""

    def test_a_repeat_does_not_hit_the_provider_twice(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        calls = []

        def once(query, limit):
            calls.append(query)
            return _results(2)

        monkeypatch.setattr(websearch, "_PROVIDERS", {"duckduckgo": once})
        assert len(websearch.search("esports analyst")) == 2
        assert len(websearch.search("Esports Analyst")) == 2, "case should share"
        assert calls == ["esports analyst"]

    def test_an_empty_result_is_not_cached(self, settings, monkeypatch):
        """Throttling looks like zero results. Caching it holds the failure open."""
        settings.THRIVE_SEARCH = "duckduckgo"
        replies = [[], _results(1)]
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: replies.pop(0)})
        assert websearch.search("q") == []
        assert len(websearch.search("q")) == 1, "a throttled miss was cached"

    def test_different_queries_do_not_share(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "duckduckgo": lambda q, limit: [
                websearch.Result(q, f"https://example.com/{q}", "")]})
        assert websearch.search("alpha")[0].title == "alpha"
        assert websearch.search("beta")[0].title == "beta"

    def test_forget_clears_it(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        calls = []
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "duckduckgo": lambda q, limit: (calls.append(q), _results(1))[1]})
        websearch.search("q")
        websearch.forget()
        websearch.search("q")
        assert len(calls) == 2


class TestWhatGetsSearched:
    """The subject, not the sentence it arrived in."""

    def test_an_explicit_query_overrides_the_last_turn(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        asked = []
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "duckduckgo": lambda q, limit: (asked.append(q), _results(1))[1]})
        Recorder().search_chat(
            "SYSTEM",
            [{"role": "user", "content": "what should I take to work in esports?"}],
            search_query="esports jobs required skills")
        assert asked == ["esports jobs required skills"]

class TestTheKeylessProvider:
    """`_duckduckgo` itself, which every other test monkeypatches away.

    It was briefly broken in a way the whole suite stayed green through --
    `body` read one line before it was assigned -- because nothing exercised
    the parser. These are that missing coverage.
    """

    class _Response:
        def __init__(self, text, status_code=200):
            self.text, self.status_code = text, status_code

        def raise_for_status(self):
            pass

    PAGE = ('<a class="result__a" href="//duckduckgo.com/l/?uddg='
            'https%3A%2F%2Fexample.com%2Fjobs&rut=x">Esports <b>Analyst</b></a>'
            '<a class="result__snippet" href="#">Reads <b>match</b> data.</a>')

    def _serve(self, monkeypatch, page, status=200):
        monkeypatch.setattr(websearch, "_get",
                            lambda *a, **k: self._Response(page, status))

    def test_it_parses_a_real_page_shape(self, monkeypatch):
        self._serve(monkeypatch, self.PAGE)
        [result] = websearch._duckduckgo("esports analyst", 5)
        assert result.title == "Esports Analyst"
        assert result.url == "https://example.com/jobs", "redirector not unwrapped"
        assert result.snippet == "Reads match data."

    def test_a_rate_limited_202_raises_rather_than_reporting_nothing(self, monkeypatch):
        """The block must not look like an honest empty result set."""
        self._serve(monkeypatch, "<html>anti-bot</html>", status=202)
        with pytest.raises(RuntimeError, match="rate-limited"):
            websearch._duckduckgo("esports analyst", 5)

    def test_an_unparseable_200_raises_too(self, monkeypatch):
        self._serve(monkeypatch, "<html>changed markup</html>")
        with pytest.raises(RuntimeError, match="no parseable results"):
            websearch._duckduckgo("esports analyst", 5)

    def test_search_still_degrades_to_empty_when_it_raises(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        self._serve(monkeypatch, "<html>anti-bot</html>", status=202)
        assert websearch.search("esports analyst") == []


class TestAKeyedProviderWithoutAKey:
    """Selected but unusable must be loud, not indistinguishable from empty."""

    @pytest.mark.parametrize("provider", ["brave", "serper", "tavily"])
    def test_it_does_not_fire_a_doomed_request(self, settings, monkeypatch, provider):
        settings.THRIVE_SEARCH = provider
        settings.THRIVE_SEARCH_API_KEY = ""
        monkeypatch.setattr(websearch, "_get",
                            lambda *a, **k: pytest.fail("requested without a key"))
        monkeypatch.setattr(websearch, "_post",
                            lambda *a, **k: pytest.fail("requested without a key"))
        assert websearch.search("esports analyst") == []

    def test_it_says_so_in_the_log(self, settings, caplog):
        """INFO, not WARNING: with a chain, a keyless first provider is the
        ordinary state before the key arrives, not a fault."""
        settings.THRIVE_SEARCH = "brave"
        settings.THRIVE_SEARCH_API_KEY = ""
        with caplog.at_level("INFO", logger="rsm_thrive.websearch"):
            websearch.search("esports analyst")
        assert "THRIVE_SEARCH_API_KEY" in caplog.text
        assert "brave" in caplog.text

    def test_the_keyless_provider_is_unaffected(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = ""
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: _results(1)})
        assert len(websearch.search("esports analyst")) == 1

    def test_a_key_lets_it_through(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "brave"
        settings.THRIVE_SEARCH_API_KEY = "BSA-key"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"brave": lambda q, limit: _results(2)})
        assert len(websearch.search("esports analyst")) == 2


class TestTheProviderChain:
    """`brave,duckduckgo` -- adopt a keyed provider before its key exists."""

    def test_the_first_that_answers_wins(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "brave,duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = "BSA-key"
        tried = []
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "brave": lambda q, limit: (tried.append("brave"), _results(2))[1],
            "duckduckgo": lambda q, limit: pytest.fail("should not be reached")})
        assert len(websearch.search("q")) == 2
        assert tried == ["brave"]

    def test_it_falls_through_when_the_key_is_missing(self, settings, monkeypatch):
        """The ordinary state before a key arrives -- not an outage."""
        settings.THRIVE_SEARCH = "brave,duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = ""
        tried = []
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "brave": lambda q, limit: pytest.fail("called without a key"),
            "duckduckgo": lambda q, limit: (tried.append("ddg"), _results(1))[1]})
        assert len(websearch.search("q")) == 1
        assert tried == ["ddg"]

    def test_it_falls_through_when_the_first_raises(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "brave,duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = "BSA-key"
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "brave": lambda q, limit: (_ for _ in ()).throw(RuntimeError("quota")),
            "duckduckgo": lambda q, limit: _results(1)})
        assert len(websearch.search("q")) == 1

    def test_it_falls_through_when_the_first_is_rate_limited(self, settings, monkeypatch):
        """Zero results is how throttling arrives, so it must fall through too."""
        settings.THRIVE_SEARCH = "brave,duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = "BSA-key"
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "brave": lambda q, limit: [],
            "duckduckgo": lambda q, limit: _results(1)})
        assert len(websearch.search("q")) == 1

    def test_everything_failing_is_still_empty_not_an_error(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "brave,duckduckgo"
        settings.THRIVE_SEARCH_API_KEY = ""
        monkeypatch.setattr(websearch, "_PROVIDERS", {
            "brave": lambda q, limit: _results(1),
            "duckduckgo": lambda q, limit: []})
        assert websearch.search("q") == []

    @pytest.mark.parametrize("configured,expected", [
        ("brave", ["brave"]),
        ("brave,duckduckgo", ["brave", "duckduckgo"]),
        (" BRAVE , DuckDuckGo ", ["brave", "duckduckgo"]),
        ("brave,altavista,tavily", ["brave", "tavily"]),
        ("none", []),
        ("", []),
    ])
    def test_the_chain_is_parsed_forgivingly(self, settings, configured, expected):
        settings.THRIVE_SEARCH = configured
        assert websearch.providers() == expected

    def test_a_single_name_still_works(self, settings, monkeypatch):
        settings.THRIVE_SEARCH = "duckduckgo"
        monkeypatch.setattr(websearch, "_PROVIDERS",
                            {"duckduckgo": lambda q, limit: _results(1)})
        assert len(websearch.search("q")) == 1

