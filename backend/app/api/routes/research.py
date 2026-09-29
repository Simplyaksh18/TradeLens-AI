"""Phase 5E: the sole HTTP entry point to the accepted Phase 5C research
agent. Pure adapter -- no agent-loop duplication, no direct Groq call, no
direct tool execution, no MCP indirection, and no financial calculation
happens in this module. Calls `run_research_agent()` exactly once per
request, through the exact same `TOOL_REGISTRY`/provider boundary Phase
5C (and, independently, Phase 5D's MCP server) already use.

Post-Phase-5F hardening: this endpoint now REQUIRES an authenticated
TradeLens session (the existing Phase 1G `get_current_user` dependency,
unchanged), unlike the other research endpoints (market-data/indicators/
strategies/outcomes/backtests/analytics/audits/investigations), which
remain deliberately unauthenticated per the existing Phase 1G decision.
This one is different because it is the only endpoint that spends real,
metered Groq quota per call -- an anonymous caller could otherwise
exhaust the account's rate/daily-token budget for every real user (see
CLAUDE.md post-5F hardening for the full assessment, including why a
larger rate-limiting layer was deliberately NOT built here). An
unauthenticated request is rejected with the exact same
`SessionInvalidError` -> 401 `SESSION_INVALID` convention every other
protected TradeLens endpoint already uses -- no new error shape."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.agent import run_research_agent
from app.agent.dependencies import AgentDependencies
from app.agent.provider import ToolCallingLanguageModel
from app.api.dependencies import get_agent_dependencies, get_tool_calling_provider
from app.api.schemas.research import ResearchQuestionRequest, ResearchResponse
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter()


@router.post(
    "/research",
    response_model=ResearchResponse,
    summary="Phase 5C tool-using research agent over a natural-language TradeLens research question (authenticated)",
)
def post_research(
    request: ResearchQuestionRequest,
    current_user: User = Depends(get_current_user),
    deps: AgentDependencies = Depends(get_agent_dependencies),
    provider: ToolCallingLanguageModel = Depends(get_tool_calling_provider),
) -> ResearchResponse:
    result = run_research_agent(request.question, provider, deps)
    return ResearchResponse.from_domain(result)
