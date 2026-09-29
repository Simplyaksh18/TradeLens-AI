"""Phase 5A: embedding abstraction. `EmbeddingProvider` decouples the
retrieval architecture from any one embedding implementation -- a real
semantic provider (calling an external model) can be added later without
changing the retrieval contract (see CLAUDE.md Phase 5A).

`LocalHashEmbeddingProvider` is the v1 default: a deterministic, local,
dependency-free lexical (hashed TF-IDF, L2-normalized) vector
representation. It exists for architectural correctness and deterministic
retrieval testing -- it does not claim state-of-the-art semantic quality,
requires no network, and downloads/imports nothing beyond the Python
standard library."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from app.core.exceptions import EmbeddingInputInvalidError

Embedding = tuple[float, ...]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "into", "is", "it", "its", "of", "on", "or", "than", "that",
        "the", "their", "this", "to", "when", "which", "while", "with",
        "never", "not", "no",
    }
)
# Minimal deterministic suffix stripping (not a real stemmer) so closely
# related word forms -- "executed"/"executing"/"execution",
# "backtest"/"backtesting", "trigger"/"triggered" -- hash to the same
# bucket. Kept intentionally crude: this is a retrieval-quality nicety for
# the local lexical provider, not a linguistic component, per CLAUDE.md
# Phase 5A's "no tokenizer/ML dependency" constraint.
_SUFFIXES = ("edly", "ing", "ies", "ion", "ed", "es", "s")


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    """Public wrapper around the exact tokenizer/stemmer/stopword
    filtering `LocalHashEmbeddingProvider` uses internally -- exposed so
    other modules (Phase 5B's evidence-sufficiency heuristic) can reuse
    the identical, already-tested tokenization instead of duplicating it.
    Purely additive; behavior is unchanged from Phase 5A."""
    return [_stem(tok) for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOPWORDS]


class EmbeddingProvider(Protocol):
    """Conceptual interface every embedding backend implements."""

    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Embedding]: ...

    def embed_query(self, text: str) -> Embedding: ...


class BaseEmbeddingProvider(ABC):
    """Shared validation for concrete providers."""

    dimension: int

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> Sequence[Embedding]: ...

    @abstractmethod
    def embed_query(self, text: str) -> Embedding: ...

    def _validate_text(self, text: str) -> None:
        if not text or not text.strip():
            raise EmbeddingInputInvalidError("Cannot embed blank text.")

    def _validate_embedding(self, vector: Embedding) -> None:
        if len(vector) != self.dimension:
            raise EmbeddingInputInvalidError(
                f"Embedding has dimension {len(vector)}, expected {self.dimension}."
            )
        if not vector or all(v == 0.0 for v in vector):
            raise EmbeddingInputInvalidError("Embedding vector must be non-empty and non-zero.")
        if not all(math.isfinite(v) for v in vector):
            raise EmbeddingInputInvalidError("Embedding vector contains a non-finite value.")


class LocalHashEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic hashed bag-of-words embedding with smoothed IDF
    weighting, L2-normalized to a fixed dimension.

    `embed_texts` both fits per-batch IDF weights (from the given texts)
    and transforms them -- the intended usage is indexing the full chunk
    corpus in one call. `embed_query` reuses the IDF weights from the most
    recent `embed_texts` call so query and document vectors are
    comparable; before any corpus has been embedded, it falls back to
    plain (unweighted) term frequency.

    Token hashing uses SHA-256 (not Python's salted `hash()`, which is
    randomized per-process) so the mapping from token to vector index is
    stable across runs -- required for determinism.
    """

    def __init__(self, dimension: int = 512):
        self.dimension = dimension
        self._idf: dict[int, float] | None = None

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Embedding]:
        for text in texts:
            self._validate_text(text)

        token_lists = [self._tokenize(text) for text in texts]
        bucket_lists = [[self._bucket(tok) for tok in tokens] for tokens in token_lists]

        document_frequency: Counter[int] = Counter()
        for buckets in bucket_lists:
            document_frequency.update(set(buckets))

        n_docs = len(texts)
        self._idf = {
            bucket: math.log((1 + n_docs) / (1 + df)) + 1.0 for bucket, df in document_frequency.items()
        }

        vectors = [self._vectorize(buckets, self._idf) for buckets in bucket_lists]
        for vector in vectors:
            self._validate_embedding(vector)
        return vectors

    def embed_query(self, text: str) -> Embedding:
        self._validate_text(text)
        buckets = [self._bucket(tok) for tok in self._tokenize(text)]
        idf = self._idf or {}
        vector = self._vectorize(buckets, idf)
        self._validate_embedding(vector)
        return vector

    def _tokenize(self, text: str) -> list[str]:
        return tokenize(text)

    def _bucket(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % self.dimension

    def _vectorize(self, buckets: list[int], idf: dict[int, float]) -> Embedding:
        term_frequency = Counter(buckets)
        weights = [0.0] * self.dimension
        for bucket, count in term_frequency.items():
            weights[bucket] = count * idf.get(bucket, 1.0)

        norm = math.sqrt(sum(w * w for w in weights))
        if norm == 0.0:
            # Every token collided into buckets that cancel to zero only
            # if the text was effectively all-stopword/empty after
            # tokenization; treat this the same as blank input.
            raise EmbeddingInputInvalidError("Text produced no embeddable tokens after normalization.")
        return tuple(w / norm for w in weights)


class SemanticEmbeddingProvider(BaseEmbeddingProvider):
    """Post-Phase-5F hardening: a REAL semantic embedding provider behind
    the unchanged `EmbeddingProvider` contract (see CLAUDE.md post-5F
    hardening). Fixes the documented Phase 5A/5F limitation where a
    heavily-paraphrased question sharing little exact vocabulary with the
    corpus ("How does the system decide when to buy a stock?") could fail
    to retrieve the correct document -- `LocalHashEmbeddingProvider` is
    lexical only, with no synonym/semantic understanding.

    Uses `fastembed` (ONNX Runtime; no PyTorch) with a small local
    sentence-embedding model (`BAAI/bge-small-en-v1.5`, 384 dimensions,
    ~130MB on disk) -- chosen specifically because it needs no GPU, no
    PyTorch (multi-GB), and downloads once to a local, cacheable
    directory rather than calling an external embeddings API on every
    request. Completely independent of Groq -- retrieval never touches
    LLM generation quota.

    The ONNX session is loaded ONCE, lazily, on the first embed call (not
    at import/construction time, so importing this module or building an
    `AgentDependencies` never requires the model to already be
    downloaded), and reused for every subsequent call -- never reloaded
    per request. `cache_dir` should point at a PERSISTENT directory (see
    `app.core.config.settings.embedding_model_cache_dir`) so the ~130MB
    model is downloaded once, not on every process start/container
    restart.

    Uses fastembed's `query_embed`/`passage_embed` (not the generic
    `embed`) so bge's asymmetric query/passage instruction prefixing is
    applied correctly -- required for this model family's retrieval
    quality; a plain symmetric `embed()` call would rank noticeably
    worse for query-vs-document similarity."""

    MODEL_NAME = "BAAI/bge-small-en-v1.5"
    DIMENSION = 384

    def __init__(self, cache_dir: str | Path | None = None):
        self.dimension = self.DIMENSION
        self._cache_dir = str(cache_dir) if cache_dir is not None else None
        self._model = None

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding  # imported lazily -- see class docstring

            self._model = TextEmbedding(model_name=self.MODEL_NAME, cache_dir=self._cache_dir)
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Embedding]:
        for text in texts:
            self._validate_text(text)
        model = self._get_model()
        vectors = [tuple(float(x) for x in vec) for vec in model.passage_embed(list(texts))]
        for vector in vectors:
            self._validate_embedding(vector)
        return vectors

    def embed_query(self, text: str) -> Embedding:
        self._validate_text(text)
        model = self._get_model()
        vector = tuple(float(x) for x in next(iter(model.query_embed([text]))))
        self._validate_embedding(vector)
        return vector
