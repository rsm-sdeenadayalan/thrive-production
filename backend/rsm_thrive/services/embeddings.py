"""Embedding backends and the cosine they're compared with."""

import hashlib
import math
import re
from abc import ABC, abstractmethod

from django.conf import settings

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


class TritonAiEmbeddings(Embeddings):
    def __init__(self, api_key=None, model=None):
        from openai import OpenAI  # lazy: tests never import the SDK

        key = api_key or getattr(settings, "TRITONAI_API_KEY", "")
        if not key:
            raise RuntimeError("TRITONAI_API_KEY is not set.")
        self._model = model or getattr(settings, "TRITONAI_EMBED_MODEL", "embed-default")
        self._client = OpenAI(api_key=key, base_url="https://tritonai-api.ucsd.edu/v1")

    def embed(self, texts: list) -> list:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]


def get_embeddings() -> Embeddings:
    if getattr(settings, "THRIVE_LLM", "tritonai") == "fake":
        return FakeEmbeddings()
    return TritonAiEmbeddings()


def cosine(a: list, b: list) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
