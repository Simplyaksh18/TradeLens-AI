"""Phase 5D: TradeLens's MCP server. STDIO transport only (the accepted
Phase 5D transport -- see CLAUDE.md). Exposes ONLY the 8 allowlisted
Phase 5C tools (`app.agent.registry.TOOL_REGISTRY`) via `app.mcp.adapter`
-- no financial calculation, no LLM/Groq call, no filesystem/shell/
environment/arbitrary-network access happens anywhere in this module.

Importing this module never starts a server and never requires
GROQ_API_KEY -- `create_server()` only registers handlers; a transport
loop only starts inside `run_stdio()`/`main()`.

Entry point:

    python -m app.mcp.server
"""

from __future__ import annotations

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from app.agent.dependencies import AgentDependencies, build_agent_dependencies
from app.mcp.adapter import call_mcp_tool, list_mcp_tools

SERVER_NAME = "tradelens"
SERVER_VERSION = "5D"


def create_server(deps: AgentDependencies) -> Server:
    """Builds a `Server` with `list_tools`/`call_tool` handlers closed
    over the given, already-constructed `AgentDependencies` -- deps are
    injected, never constructed here, so tests can pass deterministic
    fakes without touching real market data/network (see
    tests/unit/mcp/conftest.py)."""

    server: Server = Server(SERVER_NAME, version=SERVER_VERSION)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return list_mcp_tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> types.CallToolResult:
        return call_mcp_tool(name, arguments, deps)

    return server


async def run_stdio(deps: AgentDependencies) -> None:
    """Runs the TradeLens MCP server over STDIO until the client
    disconnects. The accepted Phase 5D transport -- no HTTP/SSE server is
    started."""

    server = create_server(deps)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def main() -> None:
    deps = build_agent_dependencies()
    await run_stdio(deps)


if __name__ == "__main__":
    anyio.run(main)
