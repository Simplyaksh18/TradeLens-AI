"""Phase 5C: bundles the already-accepted, already-constructed services
every tool handler needs. Built once by the caller (see
build_agent_dependencies() below / tests/unit/agent/conftest.py) and
passed through the agent loop -- tools never construct their own service
instances."""

from __future__ import annotations

from dataclasses import dataclass

from app.instruments.master import InstrumentMaster
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.market_data.service import MarketDataService


@dataclass(frozen=True)
class AgentDependencies:
    market_data_service: MarketDataService
    instrument_master: InstrumentMaster
    knowledge_retriever: ResearchKnowledgeRetriever


def build_agent_dependencies() -> AgentDependencies:
    """Constructs a real `AgentDependencies` from the same accepted
    singletons the REST API uses (`app.api.dependencies`) plus a freshly
    indexed Phase 5A retriever -- the exact construction previously
    inlined in `scripts/phase5c_manual_verification.py`, extracted here
    (Phase 5D) as the one shared factory so both the Groq agent and the
    Phase 5D MCP server build the identical, accepted dependency set
    without duplicating this wiring. No network call happens here beyond
    what the reused singletons already do lazily (market-data
    fetches/instrument-master load happen on first real use, not here);
    `index_corpus()` is local/offline (Phase 5A, no network).

    Post-Phase-5F hardening: the embedding provider is selected explicitly
    via `settings.research_embedding_provider` ("semantic" by default --
    `SemanticEmbeddingProvider`/fastembed; "lexical" opts back into the
    original `LocalHashEmbeddingProvider`). An unrecognized value is a
    startup error, and a "semantic" selection that fails to load the
    model is also a startup error -- this never silently downgrades to
    lexical retrieval, which would make callers believe semantic
    retrieval occurred when it didn't (see CLAUDE.md post-5F hardening)."""

    from app.api.dependencies import get_cache, get_instrument_master, get_market_data_service, get_provider
    from app.core.config import settings
    from app.core.exceptions import KnowledgeCorpusInvalidError
    from app.knowledge.embedding import EmbeddingProvider, LocalHashEmbeddingProvider, SemanticEmbeddingProvider
    from app.knowledge.vector_store import InMemoryVectorStore

    mode = settings.research_embedding_provider.strip().lower()
    embedding_provider: EmbeddingProvider
    if mode == "semantic":
        embedding_provider = SemanticEmbeddingProvider(cache_dir=settings.embedding_model_cache_dir)
    elif mode == "lexical":
        embedding_provider = LocalHashEmbeddingProvider()
    else:
        raise KnowledgeCorpusInvalidError(
            f"Unrecognized RESEARCH_EMBEDDING_PROVIDER {mode!r}; expected 'semantic' or 'lexical'."
        )

    instrument_master = get_instrument_master()
    retriever = ResearchKnowledgeRetriever(embedding_provider, InMemoryVectorStore())
    retriever.index_corpus()
    return AgentDependencies(
        market_data_service=get_market_data_service(get_provider(), get_cache(), instrument_master),
        instrument_master=instrument_master,
        knowledge_retriever=retriever,
    )
