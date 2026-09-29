"""Phase 5A: retriever tests, including the required retrieval-quality
evaluation set (see CLAUDE.md Phase 5A)."""

from __future__ import annotations

import pytest

from app.core.exceptions import RetrievalInputInvalidError
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore


def _indexed_retriever() -> ResearchKnowledgeRetriever:
    retriever = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    retriever.index_corpus()
    return retriever


def test_rejects_blank_query():
    retriever = _indexed_retriever()
    with pytest.raises(RetrievalInputInvalidError):
        retriever.retrieve("   ", top_k=3)


def test_rejects_invalid_top_k():
    retriever = _indexed_retriever()
    with pytest.raises(RetrievalInputInvalidError):
        retriever.retrieve("RSI", top_k=0)


def test_rejects_retrieve_before_indexing():
    retriever = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    with pytest.raises(RetrievalInputInvalidError):
        retriever.retrieve("RSI", top_k=3)


def test_deterministic_retrieval():
    a = _indexed_retriever().retrieve("What conditions trigger Trend + Momentum v1?", top_k=3)
    b = _indexed_retriever().retrieve("What conditions trigger Trend + Momentum v1?", top_k=3)
    assert [(r.chunk.chunk_id, r.score) for r in a] == [(r.chunk.chunk_id, r.score) for r in b]


def test_provenance_preserved_in_results():
    retriever = _indexed_retriever()
    results = retriever.retrieve("What does an unavailable 10-bar outcome mean?", top_k=3)
    for result in results:
        assert result.chunk.source.document_id
        assert result.chunk.source.document_title
        assert result.chunk.source.source_path
        assert result.chunk.source.chunk_id == result.chunk.chunk_id


def test_no_duplicate_chunks_in_results():
    retriever = _indexed_retriever()
    results = retriever.retrieve("strategy", top_k=10)
    ids = [r.chunk.chunk_id for r in results]
    assert len(ids) == len(set(ids))


def test_requested_top_k_is_respected():
    retriever = _indexed_retriever()
    results = retriever.retrieve("strategy", top_k=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Retrieval-quality evaluation set (CLAUDE.md Phase 5A section 10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_document_ids",
    [
        ("What conditions trigger Trend + Momentum v1?", {"strategy_trend_momentum_v1"}),
        (
            "What does an unavailable 10-bar outcome mean?",
            {"signal_outcomes", "failure_investigation"},
        ),
        ("When is a backtest entry executed?", {"backtesting_methodology"}),
        (
            "Does a failed signal mean the strategy caused the loss?",
            {"failure_investigation", "research_limitations"},
        ),
        ("What information is allowed in a point-in-time audit?", {"strategy_auditing"}),
    ],
)
def test_canonical_query_returns_expected_authoritative_document(query, expected_document_ids):
    retriever = _indexed_retriever()
    results = retriever.retrieve(query, top_k=5)
    retrieved_document_ids = {r.chunk.document_id for r in results}
    assert retrieved_document_ids & expected_document_ids, (
        f"query {query!r} expected one of {expected_document_ids}, got {retrieved_document_ids}"
    )
