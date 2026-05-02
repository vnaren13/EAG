"""Verify the FastMCP server exposes all 3 tools and they execute via the
Model Context Protocol — using FastMCP's in-process Client for speed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "diffractions.json"


@pytest.fixture
def isolated_data():
    backup = None
    if DATA_FILE.exists():
        backup = DATA_FILE.read_text(encoding="utf-8")
        DATA_FILE.unlink()
    yield
    if backup is not None:
        DATA_FILE.write_text(backup, encoding="utf-8")


@pytest.mark.asyncio
async def test_tools_registered(isolated_data):
    """All 3 tools must be discoverable via the MCP list_tools handshake."""
    from server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == {"fetch_coverage", "manage_diffraction", "show_diffractor"}


@pytest.mark.asyncio
async def test_manage_diffraction_via_mcp(isolated_data):
    """CRUD round-trip through the MCP boundary, not just direct function call."""
    from server import mcp

    async with Client(mcp) as client:
        empty = await client.call_tool("manage_diffraction", {"op": "list"})
        assert empty.data["count"] == 0

        created = await client.call_tool(
            "manage_diffraction",
            {
                "op": "create",
                "topic": "MCP test",
                "articles": [
                    {"outlet": "BBC", "url": "https://bbc.com/x", "headline": "A",
                     "lead_snippet": "lead a", "framing_notes": ["x", "y"]},
                ],
                "synthesis": "via mcp",
                "tags": ["mcp"],
            },
        )
        assert created.data["ok"] is True
        diff_id = created.data["diffraction"]["id"]

        listed = await client.call_tool("manage_diffraction", {"op": "list"})
        assert listed.data["count"] == 1

        deleted = await client.call_tool(
            "manage_diffraction", {"op": "delete", "diffraction_id": diff_id}
        )
        assert deleted.data["ok"] is True


@pytest.mark.asyncio
async def test_show_diffractor_via_mcp(isolated_data, monkeypatch):
    """show_diffractor returns a URL with the right shape regardless of whether
    a Prefab webapp is reachable. (When unreachable, tool returns ok=False but
    still surfaces a usable URL + diagnostic message.)
    """
    import webbrowser

    # Disable webbrowser.open in tests.
    monkeypatch.setattr(webbrowser, "open", lambda *a, **kw: False)
    # Use a port nothing is listening on so the self-healing path doesn't try
    # to spawn an actual prefab subprocess for this fast unit test.
    monkeypatch.setenv("PREFAB_PORT", "59999")

    # Short-circuit the spawn-and-wait path so this test stays fast.
    from tools import ui as ui_module
    monkeypatch.setattr(ui_module, "_spawn_prefab", lambda port: None)

    from server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool("show_diffractor", {})
        # ok will be False because we deliberately blocked the spawn — but
        # the URL must still be well-formed so the user can inspect it.
        assert result.data["url"].startswith("http://localhost:59999/")
        assert "url" in result.data
        assert "message" in result.data
