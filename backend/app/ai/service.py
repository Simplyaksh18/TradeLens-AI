"""Phase 5B: the retrieval -> grounded-explanation pipeline.

`explain_research_question` is the only public entry point. It composes
the accepted Phase 5A retriever with the Phase 5B evidence-sufficiency
check, prompt construction, and LLM provider -- validating input,
preserving retrieval order, and reconstructing every returned source
from the ACTUAL retrieved chunks, never from anything the model says.
"""

from __future__ import annotations

from app.ai.models import GroundedResearchExplanation, LanguageModelRequest
from app.ai.prompt import SYSTEM_INSTRUCTION, build_user_prompt
from app.ai.provider import ResearchLanguageModel
from app.ai.sufficiency import EvidenceSufficiencyAssessor
from app.core.exceptions import ResearchExplanationInputInvalidError
from app.knowledge.models import SourceReference
from app.knowledge.retriever import ResearchKnowledgeRetriever

INSUFFICIENT_EVIDENCE_ANSWER = (
    "The available TradeLens knowledge does not establish an answer to this question. "
    "TradeLens only explains its own accepted, documented methodology -- it does not "
    "speculate beyond the retrieved evidence."
)

DEFAULT_TOP_K = 5


def explain_research_question(
    question: str,
    retriever: ResearchKnowledgeRetriever,
    sufficiency_assessor: EvidenceSufficiencyAssessor,
    provider: ResearchLanguageModel,
    top_k: int = DEFAULT_TOP_K,
) -> GroundedResearchExplanation:
    """Answer a TradeLens-methodology question, grounded in Phase 5A
    evidence. Raises ResearchExplanationInputInvalidError for a blank
    question or an invalid top_k (mirroring Phase 5A's own retriever
    validation, applied before retrieval is even attempted). Never
    mutates any retrieved chunk."""
    if not question or not question.strip():
        raise ResearchExplanationInputInvalidError("Question must not be blank.")
    if top_k < 1:
        raise ResearchExplanationInputInvalidError(f"top_k must be >= 1, got {top_k}.")

    results = retriever.retrieve(question, top_k=top_k)
    retrieved_chunks = [result.chunk for result in results]

    sources = _deduplicated_sources(retrieved_chunks)

    if not sufficiency_assessor.is_sufficient(question):
        return GroundedResearchExplanation(
            question=question,
            answer=INSUFFICIENT_EVIDENCE_ANSWER,
            sources=sources,
            evidence_count=len(retrieved_chunks),
            sufficient=False,
            model=None,
        )

    user_prompt = build_user_prompt(question, retrieved_chunks)
    request = LanguageModelRequest(system_instruction=SYSTEM_INSTRUCTION, user_prompt=user_prompt)
    response = provider.generate(request)

    return GroundedResearchExplanation(
        question=question,
        answer=response.text,
        sources=sources,
        evidence_count=len(retrieved_chunks),
        sufficient=True,
        model=provider.model_name,
    )


def _deduplicated_sources(chunks) -> tuple[SourceReference, ...]:
    seen: dict[str, SourceReference] = {}
    for chunk in chunks:
        seen.setdefault(chunk.source.chunk_id, chunk.source)
    return tuple(seen.values())
