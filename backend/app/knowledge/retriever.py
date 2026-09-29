"""Phase 5A: `ResearchKnowledgeRetriever` composes the loader, chunker,
embedding provider, and vector store into one deterministic
index-then-retrieve pipeline. Returns evidence (ranked chunks with
provenance), never synthesized prose -- there is no LLM anywhere in this
module (see CLAUDE.md Phase 5A)."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import RetrievalInputInvalidError
from app.knowledge.chunker import chunk_document
from app.knowledge.embedding import EmbeddingProvider
from app.knowledge.loader import DEFAULT_CORPUS_DIR, load_corpus
from app.knowledge.models import KnowledgeChunk, RetrievalResult
from app.knowledge.vector_store import VectorRecord, VectorStore


class ResearchKnowledgeRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore):
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._chunks_by_id: dict[str, KnowledgeChunk] = {}
        self._indexed = False

    def index_corpus(self, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> int:
        """Load, chunk, embed, and store the controlled corpus. Returns the
        number of chunks indexed. Safe to call again to re-index (e.g. a
        fresh retriever instance per test) -- it replaces the previous
        in-memory index."""
        documents = load_corpus(corpus_dir)

        chunks: list[KnowledgeChunk] = []
        for document in documents:
            chunks.extend(chunk_document(document))

        self._chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}

        vectors = self._embedding_provider.embed_texts([chunk.content for chunk in chunks])
        records = [
            VectorRecord(record_id=chunk.chunk_id, vector=vector) for chunk, vector in zip(chunks, vectors)
        ]
        self._vector_store.add(records)
        self._indexed = True
        return len(chunks)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self._indexed:
            raise RetrievalInputInvalidError("Cannot retrieve before index_corpus() has been called.")
        if not query or not query.strip():
            raise RetrievalInputInvalidError("Query must not be blank.")
        if top_k < 1:
            raise RetrievalInputInvalidError(f"top_k must be >= 1, got {top_k}.")

        query_vector = self._embedding_provider.embed_query(query)
        hits = self._vector_store.query(query_vector, top_k)

        results = [RetrievalResult(chunk=self._chunks_by_id[record_id], score=score) for record_id, score in hits]

        seen_chunk_ids = {result.chunk.chunk_id for result in results}
        assert len(seen_chunk_ids) == len(results), "retrieval must never return duplicate chunks"

        return results
