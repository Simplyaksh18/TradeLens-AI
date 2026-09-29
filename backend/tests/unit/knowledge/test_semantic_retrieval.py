"""Post-Phase-5F hardening: semantic retrieval acceptance evaluation
(CLAUDE.md post-5F hardening). Uses the REAL `SemanticEmbeddingProvider`
(fastembed/ONNX, no PyTorch, no Groq) against the real Phase 5A corpus --
not mocked, since this is a fully local, deterministic-per-model
computation with no external LLM involved. The model is cached under
`data/embedding_model_cache` (persistent across runs/containers); a
completely fresh checkout needs network once to populate that cache, same
as any other pinned dependency's first install.

Six required paraphrase concepts (CLAUDE.md Phase 5F Part D), each phrased
to share little exact vocabulary with its target document -- specifically
including the exact paraphrase Phase 5F proved the lexical provider
fails on."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.knowledge.embedding import SemanticEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore


@pytest.fixture(scope="module")
def semantic_retriever() -> ResearchKnowledgeRetriever:
    # Same persistent cache path the application itself uses (see
    # app.agent.dependencies.build_agent_dependencies) -- not recomputed
    # independently, so this test can never accidentally point at a
    # different directory than production/Docker use.
    provider = SemanticEmbeddingProvider(cache_dir=settings.embedding_model_cache_dir)
    retriever = ResearchKnowledgeRetriever(provider, InMemoryVectorStore())
    retriever.index_corpus()
    return retriever


def _document_ids(retriever: ResearchKnowledgeRetriever, query: str, top_k: int = 5) -> set[str]:
    return {r.chunk.source.document_id for r in retriever.retrieve(query, top_k=top_k)}


# 1. BUY methodology -- the exact paraphrase Phase 5F proved fails under
# LocalHashEmbeddingProvider (see tests/unit/agent/test_phase5f_final_evaluation.py).
def test_previously_failing_buy_paraphrase_now_retrieves_correctly(semantic_retriever):
    assert "strategy_trend_momentum_v1" in _document_ids(semantic_retriever, "How does the system decide when to buy a stock?")


def test_alternate_buy_methodology_paraphrase(semantic_retriever):
    assert "strategy_trend_momentum_v1" in _document_ids(semantic_retriever, "What combination of price and momentum triggers a purchase?")


# 2. Backtest execution timing
def test_backtest_timing_paraphrase(semantic_retriever):
    assert "backtesting_methodology" in _document_ids(semantic_retriever, "When is a trade actually filled after a signal appears?")


# 3. Unavailable 10-bar outcomes
def test_unavailable_outcome_paraphrase(semantic_retriever):
    ids = _document_ids(semantic_retriever, "What does it mean if there isn't enough future price history yet?")
    assert "signal_outcomes" in ids or "failure_investigation" in ids


# 4. Strategy auditing / hindsight
def test_audit_hindsight_paraphrase(semantic_retriever):
    assert "strategy_auditing" in _document_ids(semantic_retriever, "How is a historical buy decision reviewed using only what was known at that time?")


# 5. Failure investigation
def test_failure_investigation_paraphrase(semantic_retriever):
    assert "failure_investigation" in _document_ids(semantic_retriever, "How does the platform study periods when the strategy underperformed?")


# 6. Unsupported/unrelated topic -- retrieval still returns results (by
# design, see Phase 5A), but they must all still carry real, non-fabricated
# provenance; sufficiency judgment happens elsewhere (Phase 5B's
# EvidenceSufficiencyAssessor / the LLM), not in the retriever itself.
def test_unsupported_topic_still_returns_real_provenance_not_fabricated(semantic_retriever):
    results = semantic_retriever.retrieve("What is the weather in Mumbai today?", top_k=5)
    assert len(results) == 5
    for r in results:
        assert r.chunk.source.document_id
        assert r.chunk.source.chunk_id


def test_semantic_provider_is_selected_by_default_configuration():
    assert settings.research_embedding_provider == "semantic"
