from pathlib import Path
from typing import Any

import yaml
from deepagents.middleware.subagents import SubAgent

from agentbankz.agents.gmail import build_gmail_subagents
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
    zapier_tools: list[Any],
) -> dict[str, SubAgent]:
    default_model = config.get("model", "openai:gpt-5.4-nano")
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

        elif source == "dynamic:zapier":
            model = item.get("model", default_model)
            for sa in build_gmail_subagents(zapier_tools, model):
                subagents[sa["name"]] = sa

    return subagents


def resolve_tools(tool_names: list[str], tool_map: dict[str, Any]) -> list[Any]:
    return [_resolve_tool(name, tool_map) for name in tool_names]


def _resolve_tool(name: str, tool_map: dict[str, Any]) -> Any:
    try:
        return tool_map[name]
    except KeyError as exc:
        raise KeyError(f"Tool '{name}' does not exist in TOOL_MAP") from exc
