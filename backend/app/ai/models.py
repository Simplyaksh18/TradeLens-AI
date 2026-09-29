"""Phase 5B: application-owned models for the grounded research
explanation engine. The LLM provider boundary (`app.ai.provider`) speaks
only `LanguageModelRequest`/`LanguageModelResponse` -- a raw Groq SDK
object never crosses into this module or any caller of it."""

from __future__ import annotations

from dataclasses import dataclass

from app.knowledge.models import SourceReference


@dataclass(frozen=True)
class LanguageModelRequest:
    """Everything a `ResearchLanguageModel` provider needs -- nothing
    more. No raw financial values, no hidden calculation inputs; only the
    already-constructed grounded prompt text."""

    system_instruction: str
    user_prompt: str


@dataclass(frozen=True)
class LanguageModelResponse:
    """Normalized provider output. Never chain-of-thought/hidden
    reasoning -- only the final answer text the provider produced."""

    text: str


@dataclass(frozen=True)
class GroundedResearchExplanation:
    """The Phase 5B result: an answer grounded in Phase 5A evidence, with
    provenance controlled entirely by deterministic application code
    (never typed/invented by the LLM -- see `app.ai.service`)."""

    question: str
    answer: str
    sources: tuple[SourceReference, ...]
    evidence_count: int
    sufficient: bool
    model: str | None = None
