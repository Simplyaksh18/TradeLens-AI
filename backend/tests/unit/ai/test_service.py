"""Phase 5B: explain_research_question pipeline tests. Always uses the
fake in-process provider -- never Groq/network."""

from __future__ import annotations

import copy

import pytest

from app.ai.service import INSUFFICIENT_EVIDENCE_ANSWER, explain_research_question
from app.core.exceptions import ResearchExplanationInputInvalidError


def test_blank_question_rejected(retriever, sufficiency_assessor, fake_provider):
    with pytest.raises(ResearchExplanationInputInvalidError):
        explain_research_question("   ", retriever, sufficiency_assessor, fake_provider)
    assert fake_provider.call_count == 0


def test_invalid_top_k_rejected(retriever, sufficiency_assessor, fake_provider):
    with pytest.raises(ResearchExplanationInputInvalidError):
        explain_research_question(
            "What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, fake_provider, top_k=0
        )
    assert fake_provider.call_count == 0


def test_provider_invoked_exactly_once_for_a_sufficient_question(retriever, sufficiency_assessor, fake_provider):
    explain_research_question("What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, fake_provider)
    assert fake_provider.call_count == 1


def test_provider_not_invoked_for_insufficient_evidence(retriever, sufficiency_assessor, fake_provider):
    result = explain_research_question(
        "What is TradeLens's approved Elliott Wave strategy?", retriever, sufficiency_assessor, fake_provider
    )
    assert fake_provider.call_count == 0
    assert result.sufficient is False
    assert result.answer == INSUFFICIENT_EVIDENCE_ANSWER


def test_evidence_passed_to_provider_matches_retrieval(retriever, sufficiency_assessor, fake_provider):
    question = "What conditions trigger Trend + Momentum v1?"
    expected_chunks = [r.chunk for r in retriever.retrieve(question, top_k=5)]

    explain_research_question(question, retriever, sufficiency_assessor, fake_provider, top_k=5)

    prompt = fake_provider.requests[0].user_prompt
    for chunk in expected_chunks:
        assert chunk.source.chunk_id in prompt
        assert chunk.content in prompt


def test_retrieval_order_preserved_in_prompt(retriever, sufficiency_assessor, fake_provider):
    question = "What conditions trigger Trend + Momentum v1?"
    expected_chunks = [r.chunk for r in retriever.retrieve(question, top_k=5)]

    explain_research_question(question, retriever, sufficiency_assessor, fake_provider, top_k=5)

    prompt = fake_provider.requests[0].user_prompt
    positions = [prompt.index(chunk.source.chunk_id) for chunk in expected_chunks]
    assert positions == sorted(positions)


def test_returned_sources_come_from_retrieved_chunks_not_provider_text(retriever, sufficiency_assessor):
    from tests.unit.ai.conftest import FakeResearchLanguageModel

    provider = FakeResearchLanguageModel(response_text="I cite [document_id=totally-invented-source].")
    question = "What conditions trigger Trend + Momentum v1?"
    expected_chunk_ids = {r.chunk.source.chunk_id for r in retriever.retrieve(question, top_k=5)}

    result = explain_research_question(question, retriever, sufficiency_assessor, provider, top_k=5)

    returned_ids = {s.chunk_id for s in result.sources}
    assert returned_ids == expected_chunk_ids
    assert "totally-invented-source" not in returned_ids


def test_sources_carry_full_provenance(retriever, sufficiency_assessor, fake_provider):
    result = explain_research_question(
        "What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, fake_provider
    )
    assert result.sources
    for source in result.sources:
        assert source.document_id
        assert source.document_title
        assert source.source_path
        assert source.chunk_id
        assert source.trust is not None


def test_no_duplicate_sources(retriever, sufficiency_assessor, fake_provider):
    result = explain_research_question(
        "What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, fake_provider, top_k=5
    )
    ids = [s.chunk_id for s in result.sources]
    assert len(ids) == len(set(ids))


def test_controlled_provider_failure_propagates(retriever, sufficiency_assessor):
    from tests.unit.ai.conftest import FailingResearchLanguageModel

    with pytest.raises(RuntimeError):
        explain_research_question(
            "What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, FailingResearchLanguageModel()
        )


def test_no_mutation_of_retrieved_evidence(retriever, sufficiency_assessor, fake_provider):
    question = "What conditions trigger Trend + Momentum v1?"
    before = copy.deepcopy([r.chunk for r in retriever.retrieve(question, top_k=5)])

    explain_research_question(question, retriever, sufficiency_assessor, fake_provider, top_k=5)

    after = [r.chunk for r in retriever.retrieve(question, top_k=5)]
    assert before == after


def test_deterministic_prompt_for_same_inputs(retriever, sufficiency_assessor):
    from tests.unit.ai.conftest import FakeResearchLanguageModel

    provider_a = FakeResearchLanguageModel()
    provider_b = FakeResearchLanguageModel()
    question = "What conditions trigger Trend + Momentum v1?"

    explain_research_question(question, retriever, sufficiency_assessor, provider_a)
    explain_research_question(question, retriever, sufficiency_assessor, provider_b)

    assert provider_a.requests[0].user_prompt == provider_b.requests[0].user_prompt
    assert provider_a.requests[0].system_instruction == provider_b.requests[0].system_instruction


def test_model_metadata_present_when_sufficient(retriever, sufficiency_assessor, fake_provider):
    result = explain_research_question(
        "What conditions trigger Trend + Momentum v1?", retriever, sufficiency_assessor, fake_provider
    )
    assert result.model == "fake-model"


def test_model_metadata_absent_when_insufficient(retriever, sufficiency_assessor, fake_provider):
    result = explain_research_question(
        "What is TradeLens's approved Elliott Wave strategy?", retriever, sufficiency_assessor, fake_provider
    )
    assert result.model is None
