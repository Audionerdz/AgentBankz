import os

from dotenv import load_dotenv

from .mcp_adapter import MCPConnectionConfig, MCPToolAdapter


load_dotenv()


def _build_zapier_url() -> str:
    token = os.environ.get("ZAPIER_MCP_TOKEN")
    if not token:
        raise RuntimeError(
            "ZAPIER_MCP_TOKEN no está definido. Agrégalo al archivo .env"
        )
    return f"https://mcp.zapier.com/api/v1/connect?token={token}"


def create_zapier_tools() -> list:
    config = MCPConnectionConfig(
        name="zapier",
        url=_build_zapier_url(),
    )
    adapter = MCPToolAdapter(config)
    return adapter.create_langchain_tools()
