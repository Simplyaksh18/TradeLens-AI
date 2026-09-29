"""Phase 5A: vector-store abstraction. `VectorStore` decouples retrieval
from any one storage backend; `InMemoryVectorStore` is the only
implementation in v1 (see CLAUDE.md Phase 5A -- no pgvector/FAISS/Chroma/
Pinecone/Weaviate/Qdrant yet)."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import VectorStoreInputInvalidError


@dataclass(frozen=True)
class VectorRecord:
    """One stored vector, identified by an opaque caller-supplied id
    (Phase 5A's retriever uses a chunk_id)."""

    record_id: str
    vector: tuple[float, ...]


class VectorStore(ABC):
    """Conceptual interface every vector-store backend implements."""

    @abstractmethod
    def add(self, records: Sequence[VectorRecord]) -> None: ...

    @abstractmethod
    def query(self, vector: Sequence[float], top_k: int) -> list[tuple[str, float]]:
        """Return up to `top_k` (record_id, cosine_similarity) pairs,
        ranked by descending similarity."""


class InMemoryVectorStore(VectorStore):
    """Deterministic, dependency-free in-memory vector store. Cosine
    similarity. The dimension of the first record added establishes the
    store's dimension; every subsequent add/query vector must match it
    exactly. Ties in similarity score break by `record_id` ascending, so
    result ordering is fully deterministic regardless of insertion or
    dict-iteration order."""

    def __init__(self):
        self._dimension: int | None = None
        self._records: dict[str, tuple[float, ...]] = {}

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def add(self, records: Sequence[VectorRecord]) -> None:
        for record in records:
            self._validate_vector(record.vector)
            self._records[record.record_id] = tuple(record.vector)

    def query(self, vector: Sequence[float], top_k: int) -> list[tuple[str, float]]:
        if top_k < 1:
            raise VectorStoreInputInvalidError(f"top_k must be >= 1, got {top_k}.")
        self._validate_vector(vector)

        scored = [(record_id, _cosine_similarity(vector, stored)) for record_id, stored in self._records.items()]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:top_k]

    def _validate_vector(self, vector: Sequence[float]) -> None:
        if self._dimension is None:
            if len(vector) == 0:
                raise VectorStoreInputInvalidError("Cannot establish store dimension from an empty vector.")
            self._dimension = len(vector)
        elif len(vector) != self._dimension:
            raise VectorStoreInputInvalidError(
                f"Vector has dimension {len(vector)}, store dimension is {self._dimension}."
            )
        if not all(math.isfinite(v) for v in vector):
            raise VectorStoreInputInvalidError("Vector contains a non-finite value.")


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
