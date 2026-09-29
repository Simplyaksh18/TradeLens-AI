"""Phase 5C: the explicit tool allowlist. `run_research_agent` (agent.py)
NEVER dynamically imports or resolves a model-provided function name --
it only ever looks a proposed tool name up in this registry. A name not
present here is rejected before any execution is attempted, regardless of
how it is phrased (see CLAUDE.md Phase 5C section 5)."""

from __future__ import annotations

from app.agent.models import ToolDefinition
from app.agent.tools import TOOL_DEFINITIONS

TOOL_REGISTRY: dict[str, ToolDefinition] = {tool.name: tool for tool in TOOL_DEFINITIONS}


def get_tool(name: str) -> ToolDefinition | None:
    """Returns the registered tool for `name`, or `None` if `name` is not
    an allowlisted tool -- callers must treat `None` as "refuse to
    execute", never as "look elsewhere."""
    return TOOL_REGISTRY.get(name)
