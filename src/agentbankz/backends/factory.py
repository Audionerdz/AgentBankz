from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

from .postgres import SyncPostgresBackend, build_postgres_config, ensure_postgres_storage


class BackendFactory:
    def __init__(self) -> None:
        self.postgres_config = build_postgres_config()

    def build_all(self) -> dict[str, Any]:
        return {
            "composite": self.build_composite(),
        }

    def build_composite(self) -> CompositeBackend:
        Path("data/chunks").mkdir(parents=True, exist_ok=True)
        Path("data/deepagents").mkdir(parents=True, exist_ok=True)

        ensure_postgres_storage(self.postgres_config)

        memories_backend = SyncPostgresBackend(self.postgres_config)
        chunks_backend = FilesystemBackend(
            root_dir="data/chunks",
            virtual_mode=True,
        )
        deepagents_backend = FilesystemBackend(
            root_dir="data/deepagents",
            virtual_mode=True,
        )

        return CompositeBackend(
            default=StateBackend(),
            routes={
                "/memories/": memories_backend,
                "/chunks/": chunks_backend,
                "/deepagents/": deepagents_backend,
            },
        )
