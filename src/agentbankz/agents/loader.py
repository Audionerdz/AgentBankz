from pathlib import Path
from typing import Any

import yaml
from deepagents.middleware.subagents import SubAgent

from agentbankz.agents.mcp_builder import build_mcp_subagents
from agentbankz.agents.gmail import GMAIL_ZAPIER_USAGE_GUIDE
from agentbankz.agents.obsidian import OBSIDIAN_USAGE_GUIDE
from agentbankz.tools.knowledge import (
    delete_python_knowledge,
    index_python_chunk,
    inspect_collection_stats,
    retrieve_python_knowledge,
    update_or_upsert_knowledge,
)


STATIC_TOOL_MAP = {
    "index_python_chunk": index_python_chunk,
    "retrieve_python_knowledge": retrieve_python_knowledge,
    "delete_python_knowledge": delete_python_knowledge,
    "update_or_upsert_knowledge": update_or_upsert_knowledge,
    "inspect_collection_stats": inspect_collection_stats,
}

MCP_SOURCE_MAP: dict[str, dict[str, Any]] = {
    "zapier": {
        "guide": GMAIL_ZAPIER_USAGE_GUIDE,
        "prefix": "gmail",
    },
    "obsidian": {
        "guide": OBSIDIAN_USAGE_GUIDE,
        "prefix": "obsidian",
    },
}


# ──────────────────────────────────────────────
# YAML LOADING
# ──────────────────────────────────────────────

def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a single YAML file. Falls back to empty dict on missing file."""
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


DEF_FILENAMES = ["defaults.yml", "subagents.yml", "orchestrators.yml"]


def load_agent_configs(
    config_dir: str | Path,
) -> dict[str, Any]:
    """Load defaults.yml + subagents.yml + orchestrators.yml and merge into one dict.

    If the multi-file split doesn't exist, falls back to a single
    ``orchestrators.yml`` (backward compat with monolithic config).
    """
    config_dir = Path(config_dir)

    # Check if multi-file split exists
    multi_file_exists = all(
        config_dir.joinpath(fname).exists() for fname in DEF_FILENAMES
    )

    if multi_file_exists:
        config: dict[str, Any] = {}
        for fname in DEF_FILENAMES:
            partial = load_yaml_config(config_dir / fname)
            config.update(partial)
        # Ensure top-level keys exist even if empty
        config.setdefault("model", "openai:gpt-5.4-nano")
        config.setdefault("subagents", {})
        config.setdefault("orchestrators", {})
        return config

    # Fallback: single monolithic orchestrators.yml
    fallback = config_dir / "orchestrators.yml"
    if fallback.exists():
        return load_yaml_config(fallback)

    raise FileNotFoundError(
        f"No agent config found in {config_dir}. Expected either "
        f"{DEF_FILENAMES} or a monolithic orchestrators.yml."
    )


# ──────────────────────────────────────────────
# SUBAGENT BUILDING
# ──────────────────────────────────────────────

def build_all_subagents(
    config: dict[str, Any],
    tool_map: dict[str, Any],
    mcp_tools_map: dict[str, list[Any]] | None = None,
) -> dict[str, SubAgent]:
    default_model = config.get("model", "openai:gpt-5.4-nano")
    mcp_tools_map = mcp_tools_map or {}
    subagents: dict[str, SubAgent] = {}

    for name, item in config.get("subagents", {}).items():
        source = item.get("source", "static")

        if source == "static":
            tools = [_resolve_tool(t, tool_map) for t in item.get("tools", [])]
            subagents[name] = SubAgent(
                name=name,
                description=item["description"],
                system_prompt=item["prompt"],
                model=item.get("model", default_model),
                tools=tools,
            )

        elif source == "dynamic:mcp":
            mcp_name = item.get("mcp_name", name)
            model = item.get("model", default_model)
            mcp_cfg = MCP_SOURCE_MAP.get(mcp_name, {})
            tools = mcp_tools_map.get(mcp_name, [])
            for sa in build_mcp_subagents(
                tools=tools,
                prefix=mcp_cfg.get("prefix", mcp_name),
                model=model,
                usage_guide=mcp_cfg.get("guide", ""),
            ):
                subagents[sa["name"]] = sa

    return subagents


def resolve_tools(tool_names: list[str], tool_map: dict[str, Any]) -> list[Any]:
    return [_resolve_tool(name, tool_map) for name in tool_names]


def _resolve_tool(name: str, tool_map: dict[str, Any]) -> Any:
    try:
        return tool_map[name]
    except KeyError as exc:
        raise KeyError(f"Tool '{name}' does not exist in TOOL_MAP") from exc
