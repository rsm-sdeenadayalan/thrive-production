"""Embedding backends and the cosine they're compared with."""

import hashlib
import math
import re
from abc import ABC, abstractmethod

from django.conf import settings

EMBEDDING_MODEL = "gemini-embedding-001"
FAKE_DIM = 32


class Embeddings(ABC):
    @abstractmethod
    def embed(self, texts: list) -> list:
        """texts -> list of same-length float vectors."""


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-hashed-words unit vectors.

    Shared words land in shared dimensions, so overlapping texts score
    higher than disjoint ones — enough signal for every retrieval test.
    """

    def embed(self, texts: list) -> list:
        out = []
        for text in texts:
            vector = [0.0] * FAKE_DIM
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.md5(word.encode()).digest()
                vector[digest[0] % FAKE_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            out.append([x / norm for x in vector])
        return out


class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key=None):
        from google import genai  # lazy

        key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=key)

    def embed(self, texts: list) -> list:
        result = self._client.models.embed_content(
            model=EMBEDDING_MODEL, contents=texts)
        return [list(e.values) for e in result.embeddings]


def get_embeddings() -> Embeddings:
    if getattr(settings, "THRIVE_LLM", "gemini") == "fake":
        return FakeEmbeddings()
    return GeminiEmbeddings()


def cosine(a: list, b: list) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
