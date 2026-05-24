import asyncio
import os
import threading
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult, TextContent, Tool


load_dotenv()

class ZapierClient:
    _instance: "ZapierClient | None" = None

    def __new__(cls) -> "ZapierClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client: Client | None = None
            cls._instance._tools: list[Tool] | None = None
            cls._instance._loop: asyncio.AbstractEventLoop | None = None
            cls._instance._loop_thread: threading.Thread | None = None
            cls._instance._lock = threading.RLock()
        return cls._instance

    @staticmethod
    def _build_url() -> str:
        token = os.environ.get("ZAPIER_MCP_TOKEN")
        if not token:
            raise RuntimeError(
                "ZAPIER_MCP_TOKEN no está definido. "
                "Agrégalo al archivo .env"
            )
        return f"https://mcp.zapier.com/api/v1/connect?token={token}"

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
            name="zapier-mcp-loop",
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
        transport = StreamableHttpTransport(self._build_url())
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
            raise RuntimeError(f"Zapier tool '{name}' error: {text}")
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
