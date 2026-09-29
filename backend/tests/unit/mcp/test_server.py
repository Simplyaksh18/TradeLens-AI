"""Phase 5D: MCP server construction tests -- `create_server()` registers
handlers without starting any transport loop, so this never blocks
pytest. No network, no Groq, no stdio."""

from __future__ import annotations

from mcp.server.lowlevel import Server

from app.mcp.server import SERVER_NAME, create_server


def test_importing_mcp_server_module_does_not_start_a_server():
    # If import had side effects (starting stdio, blocking on a socket),
    # collecting this test file would already have hung/failed.
    import app.mcp.server  # noqa: F401

    assert True


def test_create_server_returns_a_configured_server_without_blocking(deps):
    server = create_server(deps)
    assert isinstance(server, Server)
    assert server.name == SERVER_NAME


def test_create_server_registers_list_tools_and_call_tool_handlers(deps):
    import mcp.types as types

    server = create_server(deps)
    assert types.ListToolsRequest in server.request_handlers
    assert types.CallToolRequest in server.request_handlers
