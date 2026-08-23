"""Versioned, deploy-free bot tuning.

Defaults live in the repo (`config/bots.json`, versioned). Setting
THRIVE_BOT_CONFIG to a file path overlays it key-by-key per bot, so prompts
and retrieval params are editable on the server without a deploy — the
spec's explicit tunability requirement.
"""

import json
from pathlib import Path

from django.conf import settings

_DEFAULTS_PATH = Path(settings.BASE_DIR) / "config" / "bots.json"


def load_bot_config() -> dict:
    config = json.loads(_DEFAULTS_PATH.read_text())
    override_path = getattr(settings, "THRIVE_BOT_CONFIG", "")
    if override_path:
        override = json.loads(Path(override_path).read_text())
        for bot, entry in override.items():
            config.setdefault(bot, {}).update(entry)
    return config


def bot_config(bot: str) -> dict:
    return load_bot_config()[bot]
