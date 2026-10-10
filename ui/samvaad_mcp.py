"""Minimal client for the hosted Samvaad MCP server (https://mcp.sarvam.ai/voice-agents), used only to place the
free test call to a verified number (`place_test_call`).

The public REST API dials out only through a telephony connection, and this workspace has none, so the test call
exists only as an MCP tool. The token comes from, in order:
  1. SAMVAAD_MCP_TOKEN in the environment (.env), or
  2. the sign-in Claude Code already holds for the samvaad MCP server (~/.claude/.credentials.json), if
     DISHA_USE_CLAUDE_MCP_LOGIN=1 is set. That token lasts about a day; refresh it with /mcp in Claude Code.
"""
import json
import os
import time

import httpx

URL = "https://mcp.sarvam.ai/voice-agents"
CREDS = os.path.expanduser("~/.claude/.credentials.json")


class McpError(RuntimeError):
    pass


def _token() -> str:
    if os.getenv("SAMVAAD_MCP_TOKEN"):
        return os.environ["SAMVAAD_MCP_TOKEN"]
    if os.getenv("DISHA_USE_CLAUDE_MCP_LOGIN") != "1":
        raise McpError("phone calls need the Samvaad MCP sign-in: set DISHA_USE_CLAUDE_MCP_LOGIN=1 (reuse Claude "
                       "Code's samvaad login) or SAMVAAD_MCP_TOKEN, or add a telephony connection")
    try:
        entries = json.load(open(CREDS)).get("mcpOAuth", {})
    except OSError as e:
        raise McpError(f"cannot read Claude Code credentials: {e}") from e
    for key, v in entries.items():
        if key.startswith("samvaad|") and v.get("accessToken"):
            if v.get("expiresAt") and v["expiresAt"] / 1000 < time.time():
                raise McpError("Samvaad MCP sign-in expired: run /mcp in Claude Code and re-authenticate samvaad")
            return v["accessToken"]
    raise McpError("no Samvaad MCP sign-in found: connect the samvaad MCP server in Claude Code first")


def _parse(r: httpx.Response) -> dict:
    if r.status_code == 401:
        raise McpError("Samvaad MCP rejected the sign-in (401): run /mcp in Claude Code and re-authenticate samvaad")
    r.raise_for_status()
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        for line in r.text.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:])
                if "result" in msg or "error" in msg:
                    return msg
        raise McpError("empty event stream from Samvaad MCP")
    return r.json()


async def call_tool(name: str, arguments: dict) -> dict:
    """One MCP session: initialize, then tools/call. Returns the tool's JSON result."""
    h = {"Authorization": f"Bearer {_token()}", "Accept": "application/json, text/event-stream",
         "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as c:
        init = await c.post(URL, headers=h, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "disha-console", "version": "1"}}})
        _parse(init)
        if sid := init.headers.get("mcp-session-id"):
            h["Mcp-Session-Id"] = sid
        await c.post(URL, headers=h, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        msg = _parse(await c.post(URL, headers=h, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}}))
    if "error" in msg:
        raise McpError(f"{name}: {msg['error'].get('message')}")
    res = msg["result"]
    text = "".join(p.get("text", "") for p in res.get("content", []) if p.get("type") == "text")
    if res.get("isError"):
        raise McpError(f"{name}: {text[:500]}")
    try:
        return json.loads(text)
    except ValueError:
        return {"text": text}
