# pytest-django picks up DJANGO_SETTINGS_MODULE from pyproject.toml.

from pathlib import Path

import pytest

_BOTS_TEST_CONFIG = str(Path(__file__).parent / "rsm_thrive" / "tests"
                        / "fixtures" / "bots-test.json")


@pytest.fixture(autouse=True)
def _no_real_llm(settings):
    settings.THRIVE_LLM = "fake"
    # Retrieval thresholds in config/bots.json are calibrated to the REAL
    # embedding space (TritonAI, 1024-dim). FakeEmbeddings scores sit lower,
    # so tests overlay the fake-calibrated thresholds — the same deploy-free
    # override mechanism production tuning uses.
    settings.THRIVE_BOT_CONFIG = _BOTS_TEST_CONFIG
