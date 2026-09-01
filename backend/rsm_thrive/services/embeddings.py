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

    @property
    def dimension(self) -> int:
        """How wide this backend's vectors are.

        Callers use it to notice that STORED vectors were written by a
        different backend — a fake-vs-real switch, or a corrected embed model —
        without embedding anything to find out. Ingest re-embeds on a mismatch;
        without that check the stored width never changes and semantic ranking
        silently degrades to keyword overlap.

        The default asks the backend once and caches, which costs one call for
        a remote model and nothing thereafter. A backend with a fixed width
        should just declare it.
        """
        if getattr(self, "_dimension", None) is None:
            self._dimension = len(self.embed(["dimension probe"])[0])
        return self._dimension


class FakeEmbeddings(Embeddings):
    """Deterministic bag-of-hashed-words unit vectors.

    Shared words land in shared dimensions, so overlapping texts score
    higher than disjoint ones — enough signal for every retrieval test.
    """

    # Fixed by construction, so declaring it keeps the dimension check free:
    # tests that count embed calls stay exact.
    dimension = FAKE_DIM

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


class LocalEmbeddings(Embeddings):
    """Real semantic embeddings, computed on this machine, needing no API key.

    `model2vec` static embeddings: a distilled sentence encoder reduced to a
    lookup table, so inference is numpy over token vectors with no torch, no
    GPU and no network after the first download (~123MB, cached in the usual
    HuggingFace directory).

    This exists because the alternative was losing semantic search entirely.
    The TritonAI keys carry a fixed one-time budget with no reset, and the
    OAuth chat route provides completions only -- its token reaches
    api.openai.com but the account has no API billing, so `/v1/embeddings`
    answers 429. Retrieval was left on BM25, which measurably cannot separate
    "how do I drop a class" from "do my homework" (see `retrieval.py`).

    Quality is below a large hosted model and far above keyword matching:
    "how do i set up zoom" against "zoom account setup instructions" scores
    0.69, and against "what is the recipe for lasagna" 0.01.

    Switching to or from this changes the VECTOR WIDTH (256), so the corpus
    must be re-ingested after the switch -- `ingest_corpus` is local and free
    with this backend, which is what makes the switch cheap in both directions.
    """

    MODEL = "minishlab/potion-retrieval-32M"

    # NOT declared as a constant, though the base class allows it. It was, and
    # it went stale the moment the model changed: the class said 256 (the width
    # of the model this started on) while the model in use produced 512 and the
    # stored corpus held 512. `ingest_corpus` reads `.dimension` to notice that
    # a backend switch has happened and re-embed -- pointed at a stale number it
    # would decide nothing had changed and leave the corpus mismatched. Asking
    # the loaded model costs one probe on first use and cannot drift.
    _model = None   # class-level: loading costs ~1s and the weights are read-only

    @classmethod
    def _load(cls):
        if cls._model is None:
            from model2vec import StaticModel

            cls._model = StaticModel.from_pretrained(
                getattr(settings, "THRIVE_LOCAL_EMBED_MODEL", cls.MODEL))
        return cls._model

    def embed(self, texts: list) -> list:
        return [vector.tolist() for vector in self._load().encode(list(texts))]


class NullEmbeddings(Embeddings):
    """No semantic signal at all, declared rather than faked.

    For a chat backend that provides completions and no embeddings -- `codex` --
    where the alternative was worse in both directions: `TritonAiEmbeddings`
    raises on an exhausted key, and `FakeEmbeddings` returns 32-dim vectors that
    score 0.0 against a corpus stored at 1024, which looks like a working
    embedder finding nothing rather than like an embedder that is absent.

    An EMPTY vector is the signal. `retrieve` reads it and drops to its lexical
    tier, which needs no vectors and was built for exactly the short, literal
    questions students type. Ranking is then keyword-only: worse than cosine at
    paraphrase, honest about it, and it leaves the stored corpus untouched --
    which matters, because re-embedding it needs the very budget that is gone.
    """

    dimension = 0

    def embed(self, texts: list) -> list:
        return [[] for _ in texts]


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
    """The configured embedding backend.

    Chosen INDEPENDENTLY of `THRIVE_LLM`, because the two are not the same
    question and stopped having the same answer the moment a chat backend
    arrived that has no embeddings of its own. `THRIVE_LLM=codex` reaches a
    ChatGPT subscription over OAuth and provides completions only, so tying
    embeddings to it would silently mean "TritonAI" while everything else moved
    -- which reads as retrieval mysteriously failing rather than as a backend
    that was never selected.

    `THRIVE_EMBEDDINGS` overrides; unset, it follows `THRIVE_LLM` so existing
    setups and the whole test suite behave exactly as before.

    A change of backend changes the VECTOR WIDTH, and stored vectors are not
    re-embedded on read -- re-run `ingest_corpus` after switching, or ranking
    quietly degrades to keyword overlap. See `Embeddings.dimension`.
    """
    backend = getattr(settings, "THRIVE_EMBEDDINGS", "") or getattr(
        settings, "THRIVE_LLM", "tritonai")
    if backend == "fake":
        return FakeEmbeddings()
    if backend == "none":
        # Says "no vectors" out loud so `retrieve` drops to BM25. Kept as an
        # escape hatch; `codex` no longer lands here because BM25 measurably
        # cannot tell an in-scope question from an off-topic one.
        return NullEmbeddings()
    if backend in ("codex", "local"):
        return LocalEmbeddings()
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
