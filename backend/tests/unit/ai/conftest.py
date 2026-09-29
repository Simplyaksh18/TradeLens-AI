"""Phase 5B test fixtures: a real (deterministic, no-network) indexed
retriever + sufficiency assessor over the real accepted Phase 5A corpus,
and a fake ResearchLanguageModel so no test ever touches the Groq SDK or
network."""

from __future__ import annotations

import pytest

from app.ai.models import LanguageModelRequest, LanguageModelResponse
from app.ai.provider import ResearchLanguageModel
from app.ai.sufficiency import EvidenceSufficiencyAssessor
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore


class FakeResearchLanguageModel(ResearchLanguageModel):
    """Records every request it receives; returns a fixed, inspectable
    response. Never makes a network call."""

    def __init__(self, response_text: str = "FAKE ANSWER"):
        self.response_text = response_text
        self.requests: list[LanguageModelRequest] = []
        self.call_count = 0

    def generate(self, request: LanguageModelRequest) -> LanguageModelResponse:
        self.call_count += 1
        self.requests.append(request)
        return LanguageModelResponse(text=self.response_text)

    @property
    def model_name(self) -> str | None:
        return "fake-model"


class FailingResearchLanguageModel(ResearchLanguageModel):
    def generate(self, request: LanguageModelRequest) -> LanguageModelResponse:
        raise RuntimeError("simulated provider failure")


@pytest.fixture(scope="module")
def retriever() -> ResearchKnowledgeRetriever:
    r = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    r.index_corpus()
    return r


@pytest.fixture(scope="module")
def sufficiency_assessor() -> EvidenceSufficiencyAssessor:
    return EvidenceSufficiencyAssessor()


@pytest.fixture
def fake_provider() -> FakeResearchLanguageModel:
    return FakeResearchLanguageModel()
