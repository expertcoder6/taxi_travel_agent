import json
from typing import List, Dict, Any
from backend.mcp_server.server import mcp_server

class MCPClientBridge:
    """Bridges OpenAI tool-calling interfaces with the custom MCP Server."""

    @staticmethod
    def get_openai_tools() -> List[Dict[str, Any]]:
        """Transforms MCP tool definitions into OpenAI function-calling specifications."""
        tools = []
        for defn in mcp_server.get_tool_definitions():
            tools.append({
                "type": "function",
                "function": {
                    "name": defn["name"],
                    "description": defn["description"],
                    "parameters": defn["parameters"],
                },
            })
        return tools

    @staticmethod
    def execute_tool_call(name: str, arguments_json: str) -> Dict[str, Any]:
        """Parses arguments and calls the underlying MCP tool on the server."""
        try:
            args = json.loads(arguments_json) if isinstance(arguments_json, str) else arguments_json
        except Exception as exc:
            return {"error": f"Invalid JSON arguments: {str(exc)}"}

        return mcp_server.execute_tool(name, args)

mcp_client = MCPClientBridge()
