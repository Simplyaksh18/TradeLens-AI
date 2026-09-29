"""Phase 5E API representation of the accepted Phase 5C `ResearchAgentResult`.

Pure serialization -- no agent orchestration, no Groq call, no tool
execution, and no financial calculation happens here. `ResearchResponse`
exposes only safe, application-owned fields; nothing from the Groq SDK,
no chain-of-thought, no secret ever reaches this schema because
`ResearchAgentResult`/`ToolTraceEntry` themselves never carry one (see
CLAUDE.md Phase 5C)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.agent.models import ResearchAgentResult, ToolTraceEntry
from app.knowledge.models import SourceReference

MAX_QUESTION_LENGTH = 2000


class ResearchQuestionRequest(BaseModel):
    """`question` is preserved EXACTLY as submitted (never trimmed/
    rewritten) once past validation -- the only accepted validation
    behavior is rejecting a blank/whitespace-only or overlong question,
    mirroring `run_research_agent`'s own guard (defense in depth, not a
    duplicate financial/semantic check)."""

    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def _reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank.")
        return value


class ToolTraceEntrySchema(BaseModel):
    tool_name: str
    status: Literal["ok", "error", "rejected"]
    arguments: dict[str, Any]
    result_summary: str
    raw_result: Optional[dict[str, Any]] = None

    @classmethod
    def from_domain(cls, entry: ToolTraceEntry) -> "ToolTraceEntrySchema":
        return cls(
            tool_name=entry.tool_name,
            status=entry.status,
            arguments=entry.arguments,
            result_summary=entry.result_summary,
            raw_result=entry.raw_result,
        )


class KnowledgeSourceSchema(BaseModel):
    document_id: str
    document_title: str
    source_path: str
    chunk_id: str
    chunk_ordinal: int
    section_heading: Optional[str]
    trust: str

    @classmethod
    def from_domain(cls, source: SourceReference) -> "KnowledgeSourceSchema":
        return cls(
            document_id=source.document_id,
            document_title=source.document_title,
            source_path=source.source_path,
            chunk_id=source.chunk_id,
            chunk_ordinal=source.chunk_ordinal,
            section_heading=source.section_heading,
            trust=source.trust.value,
        )


class ResearchResponse(BaseModel):
    question: str
    answer: str
    stopped_reason: Literal["final_answer", "max_steps_reached", "insufficient_evidence"]
    completed_steps: int
    tool_trace: list[ToolTraceEntrySchema]
    knowledge_sources: list[KnowledgeSourceSchema]
    model: Optional[str] = None

    @classmethod
    def from_domain(cls, result: ResearchAgentResult) -> "ResearchResponse":
        return cls(
            question=result.question,
            answer=result.answer,
            stopped_reason=result.stopped_reason,
            completed_steps=result.completed_steps,
            tool_trace=[ToolTraceEntrySchema.from_domain(e) for e in result.tool_trace],
            knowledge_sources=[KnowledgeSourceSchema.from_domain(s) for s in result.knowledge_sources],
            model=result.model,
        )
