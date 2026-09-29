"""Phase 5A: in-memory vector store tests."""

from __future__ import annotations

import math

import pytest

from app.core.exceptions import VectorStoreInputInvalidError
from app.knowledge.vector_store import InMemoryVectorStore, VectorRecord


def test_cosine_ordering():
    store = InMemoryVectorStore()
    store.add(
        [
            VectorRecord("close", (1.0, 0.0)),
            VectorRecord("orthogonal", (0.0, 1.0)),
            VectorRecord("opposite", (-1.0, 0.0)),
        ]
    )
    results = store.query((1.0, 0.0), top_k=3)
    assert [r[0] for r in results] == ["close", "orthogonal", "opposite"]
    assert results[0][1] == pytest.approx(1.0)
    assert results[1][1] == pytest.approx(0.0)
    assert results[2][1] == pytest.approx(-1.0)


def test_top_k_limits_results():
    store = InMemoryVectorStore()
    store.add([VectorRecord(f"r{i}", (float(i), 1.0)) for i in range(5)])
    assert len(store.query((0.0, 1.0), top_k=2)) == 2


def test_invalid_top_k_rejected():
    store = InMemoryVectorStore()
    store.add([VectorRecord("a", (1.0, 0.0))])
    with pytest.raises(VectorStoreInputInvalidError):
        store.query((1.0, 0.0), top_k=0)


def test_dimension_mismatch_rejected_on_add():
    store = InMemoryVectorStore()
    store.add([VectorRecord("a", (1.0, 0.0))])
    with pytest.raises(VectorStoreInputInvalidError):
        store.add([VectorRecord("b", (1.0, 0.0, 0.0))])


def test_dimension_mismatch_rejected_on_query():
    store = InMemoryVectorStore()
    store.add([VectorRecord("a", (1.0, 0.0))])
    with pytest.raises(VectorStoreInputInvalidError):
        store.query((1.0, 0.0, 0.0), top_k=1)


def test_non_finite_rejected():
    store = InMemoryVectorStore()
    with pytest.raises(VectorStoreInputInvalidError):
        store.add([VectorRecord("a", (float("nan"), 0.0))])


def test_deterministic_ties_break_by_record_id():
    store = InMemoryVectorStore()
    store.add([VectorRecord("z", (1.0, 0.0)), VectorRecord("a", (1.0, 0.0)), VectorRecord("m", (1.0, 0.0))])
    results = store.query((1.0, 0.0), top_k=3)
    assert [r[0] for r in results] == ["a", "m", "z"]


def test_zero_vector_in_store_never_produces_nan_score():
    store = InMemoryVectorStore()
    store.add([VectorRecord("zero", (0.0, 0.0))])
    results = store.query((1.0, 0.0), top_k=1)
    assert results[0][1] == 0.0
    assert math.isfinite(results[0][1])
