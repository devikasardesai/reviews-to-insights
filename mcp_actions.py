"""Runs ONLY after the approval gate. Calls real MCP servers listed in mcp_servers.json, e.g.
{"docs":  {"command":"npx","args":["-y","<docs-mcp-server>"],"tool":"append_to_document","args":{"document_id":"..."}},
 "gmail": {"command":"npx","args":["-y","<gmail-mcp-server>"],"tool":"create_draft","args":{"to":"team@example.com"}}}
Tool names/arg schemas differ per server: check each with session.list_tools()."""
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call(spec, extra):
    params = StdioServerParameters(command=spec["command"], args=spec.get("args", []), env=spec.get("env"))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await s.call_tool(spec["tool"], {**spec.get("args_static", {}), **extra})

async def run(cfg, p, subject, body):
    print("docs :", await call(cfg["docs"], {"text": json.dumps(p, indent=2, ensure_ascii=False)}))
    print("gmail:", await call(cfg["gmail"], {"subject": subject, "body": body}))  # draft only, never send
