# pytest-django picks up DJANGO_SETTINGS_MODULE from pyproject.toml.

import pytest


@pytest.fixture(autouse=True)
def _no_real_llm(settings):
    settings.THRIVE_LLM = "fake"
