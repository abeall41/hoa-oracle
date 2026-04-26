"""
The ONLY path from the orchestrator to any agent tool.
Never import and call agent tool functions directly — always go through here.
This preserves the subprocess boundary that makes agents independently
deployable, testable, and replaceable without touching orchestrator code.
"""
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

GOVERNANCE_MCP_SCRIPT = "agents/governance-mcp/server.py"
CUSTOMER_SERVICE_SCRIPT = "agents/customer-service-mcp/server.py"


class MCPToolError(Exception):
    pass


async def _invoke_tool(server_script: str, tool_name: str, arguments: dict) -> dict:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if not result.content:
                raise MCPToolError(f"Tool {tool_name} returned no content")
            if result.isError:
                raise MCPToolError(
                    f"Tool {tool_name} raised an error: {result.content[0].text}"
                )
            return json.loads(result.content[0].text)


async def invoke_governance_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(GOVERNANCE_MCP_SCRIPT, tool_name, arguments)


async def invoke_customer_service_tool(tool_name: str, arguments: dict) -> dict:
    return await _invoke_tool(CUSTOMER_SERVICE_SCRIPT, tool_name, arguments)
