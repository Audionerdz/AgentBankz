import re
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from .client import ZapierClient


def _pythonize_name(name: str) -> str:
    return re.sub(r"[:\-]", "_", name)


def _generate_docstring(name: str, schema: dict[str, Any]) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines: list[str] = [f"Invoca la herramienta Zapier '{name}' en Gmail.\n"]
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


def create_zapier_tools() -> list:  # noqa: UP006
    client = ZapierClient()
    schemas = client.get_tool_schemas()

    tools: list = []
    for schema in schemas:
        fn = _build_tool(schema)
        tools.append(fn)

    return tools


def _build_tool(schema: dict[str, Any]):
    mcp_name: str = schema["name"]
    py_name: str = _pythonize_name(mcp_name)
    doc: str = _generate_docstring(mcp_name, schema["inputSchema"])
    args_schema = _create_args_schema(mcp_name, schema["inputSchema"])

    def wrapped(**kwargs: Any) -> str:
        client = ZapierClient()
        arguments = {key: value for key, value in kwargs.items() if value is not None}
        return client.call_tool(mcp_name, arguments)

    return StructuredTool.from_function(
        func=wrapped,
        name=py_name,
        description=doc,
        args_schema=args_schema,
    )
