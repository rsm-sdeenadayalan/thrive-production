"""Deterministic skill extraction from a curated, versioned vocabulary.

Deliberately not an LLM call: extraction runs per posting per ingest, must be
reproducible in tests, and drives the role benchmark — the spec's legal
'what the market says this job needs' aggregate.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_VOCAB_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs" / "skills_vocab.json"


@lru_cache(maxsize=1)
def load_skills_vocab():
    return json.loads(_VOCAB_PATH.read_text())


@lru_cache(maxsize=1)
def _patterns():
    compiled = []
    for canonical, aliases in load_skills_vocab().items():
        terms = [canonical] + list(aliases)
        alternation = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
        compiled.append((canonical, re.compile(rf"(?<![\w/])({alternation})(?![\w/])",
                                               re.IGNORECASE)))
    return compiled


def extract_skills(text):
    found = {canonical for canonical, pattern in _patterns() if pattern.search(text)}
    return sorted(found)
