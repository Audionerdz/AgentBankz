from typing import Any

from deepagents.middleware.subagents import SubAgent


def build_mcp_subagents(
    tools: list[Any],
    prefix: str,
    model: str,
    usage_guide: str = "",
) -> list[SubAgent]:
    subagents: list[SubAgent] = []
    for tool in tools:
        name = tool.name if hasattr(tool, "name") else tool.__name__
        subagents.append(
            SubAgent(
                name=f"{prefix}_{name}",
                description=f"{prefix.title()} operation '{name}' via MCP.",
                system_prompt=(
                    f"You are a {prefix.title()} expert agent. Your only task is to invoke the "
                    f"'{name}' tool when the orchestrator requests it. Execute it with the exact "
                    f"parameters you receive. Do not invent values or modify the request.\n\n"
                    f"{usage_guide}"
                ).strip(),
                model=model,
                tools=[tool],
            )
        )
    return subagents
