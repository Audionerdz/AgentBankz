import fnmatch
import json
import os
from pathlib import Path

import psycopg
from deepagents.backends.protocol import FileData, GlobResult, GrepResult, LsResult, ReadResult
from deepagents_backends import PostgresBackend, PostgresConfig


def build_postgres_config() -> PostgresConfig:
    return PostgresConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        database=os.environ.get("DB_NAME", "deepagents"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        table="agent_files",
        schema=os.environ.get("DB_SCHEMA", "public"),
    )


def ensure_postgres_storage(config: PostgresConfig) -> None:
    """Crea base, schema, tabla e índices requeridos por PostgresBackend."""
    from psycopg import sql

    admin_database = os.environ.get("DB_ADMIN_DATABASE", "postgres")
    connect_kwargs = {
        "host": config.host,
        "port": config.port,
        "user": config.user,
        "password": config.password,
        "sslmode": config.sslmode,
        "connect_timeout": config.connection_timeout,
    }

    try:
        with psycopg.connect(dbname=admin_database, autocommit=True, **connect_kwargs) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (config.database,),
            ).fetchone()

            if not exists:
                conn.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(config.database))
                )

        with psycopg.connect(dbname=config.database, autocommit=True, **connect_kwargs) as conn:
            conn.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(config.schema)
                )
            )
            conn.execute(
                sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {} (
                        path TEXT PRIMARY KEY,
                        content JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """).format(sql.Identifier(config.schema, config.table))
            )
            conn.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (path text_pattern_ops)").format(
                    sql.Identifier(f"idx_{config.table}_path_prefix"),
                    sql.Identifier(config.schema, config.table),
                )
            )
            conn.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (modified_at DESC)").format(
                    sql.Identifier(f"idx_{config.table}_modified"),
                    sql.Identifier(config.schema, config.table),
                )
            )
    except psycopg.Error as exc:
        raise RuntimeError(
            f"No se pudo preparar la base PostgreSQL '{config.database}'. "
            "Verifica DB_HOST, DB_PORT, DB_USER, DB_PASSWORD y permisos CREATEDB."
        ) from exc


class SyncPostgresBackend(PostgresBackend):
    """PostgresBackend síncrono para evitar el loop async incompatible de Windows."""

    def _connect(self):
        return psycopg.connect(
            host=self._config.host,
            port=self._config.port,
            dbname=self._config.database,
            user=self._config.user,
            password=self._config.password,
            sslmode=self._config.sslmode,
            connect_timeout=self._config.connection_timeout,
        )

    def ls(self, path: str) -> LsResult:
        prefix = path if path.endswith("/") or path == "/" else path + "/"
        storage_prefix = self._storage_path(prefix)
        like_all = (storage_prefix + "%") if storage_prefix else "%"
        like_nested = (storage_prefix + "%/%") if storage_prefix else "%/%"
        substr_start = len(storage_prefix) + 1

        with self._connect() as conn:
            file_rows = conn.execute(
                f"""
                SELECT path, modified_at,
                       COALESCE(jsonb_array_length(content->'content'), 0)
                FROM {self._table}
                WHERE path LIKE %s AND path NOT LIKE %s
                ORDER BY path
                """,
                (like_all, like_nested),
            ).fetchall()
            dir_rows = conn.execute(
                f"""
                SELECT DISTINCT SPLIT_PART(SUBSTR(path, %s), '/', 1)
                FROM {self._table}
                WHERE path LIKE %s
                ORDER BY 1
                """,
                (substr_start, like_nested),
            ).fetchall()

        entries = [
            {
                "path": self._virtual_path(row[0]),
                "is_dir": False,
                "size": row[2],
                "modified_at": row[1].isoformat() if row[1] else None,
            }
            for row in file_rows
        ]
        entries.extend(
            {"path": self._virtual_path(storage_prefix + dir_name + "/"), "is_dir": True}
            for (dir_name,) in dir_rows
        )
        entries.sort(key=lambda item: item.get("path", ""))
        return LsResult(entries=entries)

    async def als(self, path: str) -> LsResult:
        return self.ls(path)

    def glob(self, pattern: str, path: str = "/") -> GlobResult:
        storage_prefix = self._storage_path(path)
        like_prefix = storage_prefix + "%" if storage_prefix else "%"

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT path, modified_at,
                       COALESCE(jsonb_array_length(content->'content'), 0)
                FROM {self._table}
                WHERE path LIKE %s
                ORDER BY path
                """,
                (like_prefix,),
            ).fetchall()

        matches = []
        for storage_path, modified_at, line_count in rows:
            virtual_path = self._virtual_path(storage_path)
            rel_path = virtual_path[len(path):].lstrip("/") if path != "/" else virtual_path[1:]
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(virtual_path, pattern):
                matches.append(
                    {
                        "path": virtual_path,
                        "is_dir": False,
                        "size": line_count,
                        "modified_at": modified_at.isoformat() if modified_at else None,
                    }
                )

        return GlobResult(matches=matches)

    async def aglob(self, pattern: str, path: str = "/") -> GlobResult:
        return self.glob(pattern, path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT content FROM {self._table} WHERE path = %s",
                (self._storage_path(file_path),),
            ).fetchone()

        if not row:
            return ReadResult(error=f"File '{file_path}' not found")

        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        lines = data.get("content", [])
        if offset >= len(lines) and lines:
            return ReadResult(error=f"Line offset {offset} exceeds file length ({len(lines)} lines)")

        content = "\n".join(lines[offset : offset + limit])
        return ReadResult(file_data=FileData(content=content, encoding="utf-8"))

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return self.read(file_path, offset, limit)

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        search_prefix = self._storage_path(path or "/")
        like_pattern = search_prefix + "%" if search_prefix else "%"

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT path, content->'content' FROM {self._table} WHERE path LIKE %s ORDER BY path",
                (like_pattern,),
            ).fetchall()

        matches = []
        for storage_path, content_arr in rows:
            virtual_path = self._virtual_path(storage_path)
            if glob and not fnmatch.fnmatch(Path(virtual_path).name, glob):
                continue
            lines = content_arr if isinstance(content_arr, list) else []
            for line_num, line in enumerate(lines, 1):
                if pattern in line:
                    matches.append({"path": virtual_path, "line": line_num, "text": line})

        return GrepResult(matches=matches)

    async def agrep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        return self.grep(pattern, path, glob)
