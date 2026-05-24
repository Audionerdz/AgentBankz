from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent

from .loader import (
    STATIC_TOOL_MAP,
    build_all_subagents,
    load_agent_configs,
    resolve_tools,
)


class OrchestratorFactory:
    def __init__(
        self,
        config_dir: str | Path | None = None,
        tool_map: dict[str, Any] | None = None,
        zapier_tools: list[Any] | None = None,
    ) -> None:
        config_dir = config_dir or Path(__file__).parent
        self.config = load_agent_configs(config_dir)
        self.tool_map = {**STATIC_TOOL_MAP, **(tool_map or {})}
        self.subagent_map = build_all_subagents(
            self.config, self.tool_map, zapier_tools or []
        )

    def build_one(self, name: str, backend: Any, **overrides: Any) -> Any:
        orchestrators = self.config.get("orchestrators", {})
        if name not in orchestrators:
            raise KeyError(f"Orchestrator '{name}' does not exist in orchestrators.yml")

        config = {**orchestrators[name], **overrides}
        return create_deep_agent(
            model=config["model"],
            backend=backend,
            system_prompt=config["system_prompt"],
            tools=resolve_tools(config.get("tools", []), self.tool_map),
            middleware=config.get("middleware", []),
            subagents=self._resolve_subagents(config.get("subagents", [])),
        )

    def build_all(self, backend_map: dict[str, Any]) -> dict[str, Any]:
        agents: dict[str, Any] = {}
        for name, config in self.config.get("orchestrators", {}).items():
            backend_name = config.get("backend")
            if backend_name not in backend_map:
                raise KeyError(f"Backend '{backend_name}' does not exist in backend_map")
            agents[name] = self.build_one(name, backend=backend_map[backend_name])
        return agents

    def _resolve_subagents(self, names: list[str]) -> list[SubAgent]:
        resolved: list[SubAgent] = []
        for name in names:
            if name.endswith(":*"):
                prefix = name[:-2] + "_"
                resolved.extend(
                    subagent
                    for subagent_name, subagent in self.subagent_map.items()
                    if subagent_name.startswith(prefix)
                )
                continue

            try:
                resolved.append(self.subagent_map[name])
            except KeyError as exc:
                raise KeyError(f"Subagent '{name}' does not exist") from exc

        return resolved
