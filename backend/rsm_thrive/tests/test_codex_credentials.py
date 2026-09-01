"""The shared-credential path used by a hosted test instance.

None of this matters on a laptop, where one developer authenticates as
themselves. It all matters the moment one credential file serves everybody.
"""
import threading

import pytest

from rsm_thrive.services import codex_oauth
from rsm_thrive.services.llm import SharedCodexCredentials


def _credentials(expires_ms):
    return codex_oauth.OAuthCredentials(
        access="access-token", refresh="refresh-token",
        expires=expires_ms, account_id="acct-1")


@pytest.fixture(autouse=True)
def _clean():
    SharedCodexCredentials.reset()
    yield
    SharedCodexCredentials.reset()


class TestOneRefreshNotOnePerRequest:
    """OpenAI refresh tokens are single-use -- the vendored script recognises
    `refresh_token_reused` for exactly that reason. Two turns arriving together
    after expiry must not both refresh, or the loser's token is dead for every
    user on the box."""

    def test_concurrent_callers_refresh_once(self, monkeypatch, settings):
        settings.CODEX_ALLOW_BROWSER_LOGIN = False
        import time

        stale = _credentials(int(time.time() * 1000) - 1000)
        fresh = _credentials(int(time.time() * 1000) + 3600_000)
        refreshes = []

        monkeypatch.setattr(codex_oauth, "load_openai_codex_credentials",
                            lambda path=None: stale)
        monkeypatch.setattr(codex_oauth, "save_openai_codex_credentials",
                            lambda c, p=None: None)

        def refresh(token):
            refreshes.append(token)
            return fresh

        monkeypatch.setattr(codex_oauth, "refresh_openai_codex_token", refresh)

        seen = []
        threads = [threading.Thread(target=lambda: seen.append(SharedCodexCredentials.get()))
                   for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(refreshes) == 1, f"refreshed {len(refreshes)} times"
        assert all(c is fresh for c in seen), "every caller gets the same credential"

    def test_a_valid_credential_is_not_refreshed_at_all(self, monkeypatch, settings):
        settings.CODEX_ALLOW_BROWSER_LOGIN = False
        import time

        good = _credentials(int(time.time() * 1000) + 3600_000)
        monkeypatch.setattr(codex_oauth, "load_openai_codex_credentials",
                            lambda path=None: good)
        monkeypatch.setattr(codex_oauth, "save_openai_codex_credentials",
                            lambda c, p=None: None)
        monkeypatch.setattr(codex_oauth, "refresh_openai_codex_token",
                            lambda t: pytest.fail("should not refresh a valid token"))

        assert SharedCodexCredentials.get() is good
        assert SharedCodexCredentials.get() is good, "and it is cached"


class TestAServerNeverOpensABrowser:
    """`ensure_openai_codex_credentials` falls back to a browser sign-in that
    blocks on `input()`. On a headless host that hangs a worker for good."""

    def test_missing_credentials_raise_instead_of_prompting(self, monkeypatch, settings):
        settings.CODEX_ALLOW_BROWSER_LOGIN = False
        monkeypatch.setattr(codex_oauth, "load_openai_codex_credentials",
                            lambda path=None: None)
        monkeypatch.setattr(codex_oauth, "_load_codex_cli_credentials", lambda: None)
        monkeypatch.setattr(codex_oauth, "login_openai_codex_oauth",
                            lambda **kw: pytest.fail("a server must not sign in"))

        with pytest.raises(RuntimeError, match="CODEX_CREDENTIALS_PATH"):
            SharedCodexCredentials.get()

    def test_a_dead_refresh_token_raises_instead_of_prompting(self, monkeypatch, settings):
        settings.CODEX_ALLOW_BROWSER_LOGIN = False
        import time

        stale = _credentials(int(time.time() * 1000) - 1000)
        monkeypatch.setattr(codex_oauth, "load_openai_codex_credentials",
                            lambda path=None: stale)
        monkeypatch.setattr(codex_oauth, "refresh_openai_codex_token",
                            lambda t: (_ for _ in ()).throw(RuntimeError("refresh_token_reused")))
        monkeypatch.setattr(codex_oauth, "login_openai_codex_oauth",
                            lambda **kw: pytest.fail("a server must not sign in"))

        with pytest.raises(RuntimeError, match="could not be refreshed"):
            SharedCodexCredentials.get()

    def test_a_terminal_may_still_sign_in(self, monkeypatch, settings):
        # The laptop path stays exactly as it was.
        settings.CODEX_ALLOW_BROWSER_LOGIN = True
        import time

        logged_in = _credentials(int(time.time() * 1000) + 3600_000)
        monkeypatch.setattr(codex_oauth, "load_openai_codex_credentials",
                            lambda path=None: None)
        monkeypatch.setattr(codex_oauth, "_load_codex_cli_credentials", lambda: None)
        monkeypatch.setattr(codex_oauth, "login_openai_codex_oauth",
                            lambda **kw: logged_in)
        monkeypatch.setattr(codex_oauth, "save_openai_codex_credentials",
                            lambda c, p=None: None)

        assert SharedCodexCredentials.get() is logged_in
