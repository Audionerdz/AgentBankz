import asyncio
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from langchain_core.tools import StructuredTool
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import Field, create_model


@dataclass
class MCPConnectionConfig:
    name: str
    url: str
    token_env_var: str | None = None
    headers: dict[str, str] | None = None
    verify: bool | str | None = None


class MCPToolAdapter:
    def __init__(self, config: MCPConnectionConfig) -> None:
        self.config = config
        self._client: Client | None = None
        self._tools: list[Tool] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def _build_url(self) -> str:
        url = self.config.url
        return url

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.config.token_env_var:
            token = os.environ.get(self.config.token_env_var)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        if self.config.headers:
            headers.update(self.config.headers)
        return headers

    def ensure_connected(self) -> None:
        with self._lock:
            if self._client is not None:
                return
            self._run(self._connect_async())

    def _ensure_loop(self) -> None:
        if self._loop is not None and self._loop_thread is not None and self._loop_thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop,
            name=f"mcp-{self.config.name}-loop",
            daemon=True,
        )
        self._loop_thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro):
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    async def _connect_async(self) -> None:
        transport = StreamableHttpTransport(
            self._build_url(),
            headers=self._build_headers(),
            verify=self.config.verify,
        )
        self._client = Client(transport)
        await self._client.__aenter__()
        self._tools = await self._client.list_tools()

    def list_tools(self) -> list[Tool]:
        self.ensure_connected()
        return list(self._tools or [])

    def get_tool_schemas(self) -> list[dict]:
        self.ensure_connected()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": dict(t.inputSchema),
            }
            for t in self._tools or []
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.ensure_connected()
        result: CallToolResult = self._run(
            self._client.call_tool(name, arguments)
        )
        parts: list[str] = []
        for item in result.content:
            if isinstance(item, TextContent):
                parts.append(item.text)
            else:
                parts.append(str(item))
        text = "\n".join(parts)
        if result.is_error:
            raise RuntimeError(f"MCP tool '{name}' error: {text}")
        return text

    def close(self) -> None:
        with self._lock:
            if self._client is not None and self._loop is not None:
                self._run(self._client.__aexit__(None, None, None))
            self._client = None
            self._tools = None
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread is not None and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=5)
            self._loop = None
            self._loop_thread = None

    def create_langchain_tools(self) -> list[StructuredTool]:
        schemas = self.get_tool_schemas()
        tools: list[StructuredTool] = []
        for schema in schemas:
            mcp_name: str = schema["name"]
            py_name: str = _pythonize_name(mcp_name)
            doc: str = _generate_docstring(mcp_name, schema["inputSchema"])
            args_schema = _create_args_schema(mcp_name, schema["inputSchema"])

            def _build_tool_fn(mcp_name: str):
                def wrapped(**kwargs: Any) -> str:
                    arguments = {key: value for key, value in kwargs.items() if value is not None}
                    try:
                        return self.call_tool(mcp_name, arguments)
                    except Exception as exc:
                        return f"MCP tool '{mcp_name}' failed: {exc}"
                return wrapped

            tools.append(
                StructuredTool.from_function(
                    func=_build_tool_fn(mcp_name),
                    name=py_name,
                    description=doc,
                    args_schema=args_schema,
                )
            )
        return tools


def _pythonize_name(name: str) -> str:
    return re.sub(r"[:\-]", "_", name)


def _generate_docstring(name: str, schema: dict[str, Any]) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines: list[str] = [f"Invoke the MCP tool '{name}'.\n"]
    if props:
        lines.append("Args:")
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "any")
            desc = pinfo.get("description", "").strip()
            req = " (required)" if pname in required else ""
            lines.append(f"    {pname} ({ptype}){req}: {desc}")
    return "\n".join(lines)


def _schema_type(prop: dict[str, Any]) -> Any:
    prop_type = prop.get("type")
    if isinstance(prop_type, list):
        prop_type = next((item for item in prop_type if item != "null"), None)
    match prop_type:
        case "string":
            return str
        case "integer":
            return int
        case "number":
            return float
        case "boolean":
            return bool
        case "array":
            return list[Any]
        case "object":
            return dict[str, Any]
        case _:
            return Any


def _create_args_schema(name: str, schema: dict[str, Any]):
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for pname, pinfo in props.items():
        field_type = _schema_type(pinfo)
        default = ... if pname in required else None
        if pname not in required and field_type is not Any:
            field_type = field_type | None
        fields[pname] = (
            field_type,
            Field(default, description=pinfo.get("description", "")),
        )
    model_name = f"{_pythonize_name(name).title().replace('_', '')}Args"
    return create_model(model_name, **fields)
