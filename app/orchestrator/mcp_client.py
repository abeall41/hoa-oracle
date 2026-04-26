"""
The ONLY path from the orchestrator to any agent tool.
Never import and call agent tool functions directly — always go through here.
This preserves the subprocess boundary that makes agents independently
deployable, testable, and replaceable without touching orchestrator code.
"""
import json
import logging
import sys
import time

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

GOVERNANCE_MCP_SCRIPT = "agents/governance-mcp/server.py"
CUSTOMER_SERVICE_SCRIPT = "agents/customer-service-mcp/server.py"

logger = logging.getLogger(__name__)


class MCPToolError(Exception):
    pass


async def _invoke_tool(server_script: str, tool_name: str, arguments: dict) -> dict:
    # Log inputs — redact compliance_facts (can be very large) but log a summary
    log_args = {
        k: (v[:300] + "…" if isinstance(v, str) and len(v) > 300 else v)
        for k, v in arguments.items()
    }
    logger.debug("→ tool=%s args=%s", tool_name, json.dumps(log_args))

    t0 = time.monotonic()
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if not result.content:
                raise MCPToolError(f"Tool {tool_name} returned no content")
            if result.isError:
                logger.error(
                    "← tool=%s FAILED in %dms: %s",
                    tool_name, elapsed_ms, result.content[0].text,
                )
                raise MCPToolError(
                    f"Tool {tool_name} raised an error: {result.content[0].text}"
                )

            parsed = json.loads(result.content[0].text)
            _log_tool_result(tool_name, parsed, elapsed_ms)
            return parsed


def _log_tool_result(tool_name: str, result: dict, elapsed_ms: int) -> None:
    if tool_name == "search_community_rules":
        chunks = result.get("results", [])
        tiers = result.get("tiers_searched", [])
        logger.info(
            "← tool=search_community_rules %dms — %d chunks from tiers=%s",
            elapsed_ms, len(chunks), tiers,
        )
        for i, chunk in enumerate(chunks):
            logger.debug(
                "  chunk[%d] score=%.3f tier=%s doc=%r section=%r text=%r",
                i,
                chunk.get("relevance_score", 0),
                chunk.get("tier", "?"),
                chunk.get("document_title", ""),
                chunk.get("section_ref", ""),
                chunk.get("chunk_text", "")[:200],
            )

    elif tool_name == "format_homeowner_response":
        response_text = result.get("response_text", "")
        sources = result.get("sources_cited", [])
        logger.info(
            "← tool=format_homeowner_response %dms — %d sources — response: %s",
            elapsed_ms, len(sources), response_text,
        )

    elif tool_name == "flag_for_escalation":
        logger.info(
            "← tool=flag_for_escalation %dms — urgency=%s reason=%s",
            elapsed_ms,
            result.get("urgency", "?"),
            result.get("reason", "?"),
        )

    else:
        logger.info("← tool=%s %dms", tool_name, elapsed_ms)


async def invoke_governance_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(GOVERNANCE_MCP_SCRIPT, tool_name, arguments)


async def invoke_customer_service_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(CUSTOMER_SERVICE_SCRIPT, tool_name, arguments)
