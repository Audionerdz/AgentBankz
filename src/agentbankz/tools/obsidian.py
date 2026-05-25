from dotenv import load_dotenv

from .mcp_adapter import MCPConnectionConfig, MCPToolAdapter


load_dotenv()

OBSIDIAN_CONFIG = MCPConnectionConfig(
    name="obsidian",
    url="https://127.0.0.1:27124/mcp/",
    token_env_var="OBSIDIAN_API_KEY",
    verify=False,
)


def create_obsidian_tools() -> list:
    adapter = MCPToolAdapter(OBSIDIAN_CONFIG)
    return adapter.create_langchain_tools()
