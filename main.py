# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "chromadb>=1.5.9",
#     "copilotkit>=0.1.89",
#     "deepagents>=0.6.1",
#     "langchain-chroma>=1.1.0",
#     "langchain-ollama>=1.1.0",
#     "langchain-openai>=1.2.1",
#     "deepagents-backends @ git+https://github.com/DiTo97/deepagents-backends.git"
# ]
# ///

#!/usr/bin/env python3
import os
import sys
import fnmatch
import json
from pathlib import Path

import psycopg

# Importaciones específicas y nativas de DeepAgents
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
from deepagents.backends import FilesystemBackend, StateBackend, CompositeBackend
from deepagents.backends.protocol import FileData, GlobResult, GrepResult, LsResult, ReadResult

## Importaciones para el Backend PostGress
from deepagents_backends import PostgresBackend, PostgresConfig

# =====================================================================
# 0. CONFIGURACIÓN DE HERRAMIENTAS (CHROMA)
# =====================================================================
# Importación directa y limpia desde tu paquete modularizado
from chroma_tools import (
    index_python_chunk,
    retrieve_python_knowledge,
    delete_python_knowledge,
    update_or_upsert_knowledge,
    inspect_collection_stats
)

# =====================================================================
# 1. CONFIGURACIÓN DE STORAGE Y BACKENDS (HÍBRIDO)
# =====================================================================
# Directorios locales para Chunks y configuraciones internas de DeepAgents
Path("data/chunks").mkdir(parents=True, exist_ok=True)
Path("data/deepagents").mkdir(parents=True, exist_ok=True)    

# Configuración estructurada de PostgreSQL utilizando variables de entorno (Recomendado)
# Si prefieres hardcodear, puedes reemplazar el os.environ.get por tus strings fijos.
postgres_config = PostgresConfig(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", 5432)),
    database=os.environ.get("DB_NAME", "deepagents"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "postgres"),
    table="agent_files",  # Tabla autogestionada por el backend (JSONB estructurado)
    schema=os.environ.get("DB_SCHEMA", "public"),
)


def ensure_postgres_storage(config: PostgresConfig) -> None:
    """Crea base, schema, tabla e índices requeridos por PostgresBackend."""
    import psycopg
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


ensure_postgres_storage(postgres_config)


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


# Creamos la instancia del backend de base de datos para /memories/
memories_backend = SyncPostgresBackend(postgres_config)

chunks_backend = FilesystemBackend(
    root_dir="data/chunks",
    virtual_mode=True
)

deepagents_backend = FilesystemBackend(
    root_dir="data/deepagents",
    virtual_mode=True
)

# Crear CompositeBackend ruteando las memorias hacia PostgreSQL
composite_backend = CompositeBackend(
    default=StateBackend(),  # Para archivos temporales efímeros en la raíz
    routes={
        "/memories/": memories_backend,   # Redireccionado a PostgreSQL de forma segura
        "/chunks/": chunks_backend,       # Almacenamiento en disco local
        "/deepagents/": deepagents_backend, # Almacenamiento en disco local
    }
)

# =====================================================================
# 1. CONTEXTO Y CONFIGURACIÓN DE SUBAGENTES
# =====================================================================
subagents = [
    SubAgent(
        name="python_indexer",
        description="Agente encargado de indexar fragmentos de código en Chroma.",
        system_prompt=(
            "Eres un indexador técnico experto. Tu única tarea es estructurar, formatear e "
            "indexar fragmentos de código, payloads o documentación valiosa de Python en "
            "Chroma usando la herramienta 'index_python_chunk'. Clasifica siempre el contenido "
            "en categorías lógicas (ej. 'exploits', 'network', 'decorators', 'async') para "
            "optimizar búsquedas futuras."
        ),
        model="openai:gpt-5.4-nano",
        tools=[index_python_chunk]
    ),
    SubAgent(
        name="python_retriever",
        description="Agente encargado de buscar conocimiento en la base de datos de vectores Chroma.",
        system_prompt=(
            "Eres el especialista en recuperación de información. Tu objetivo es buscar contexto "
            "técnico relevante, soluciones previas o documentación almacenada usando la herramienta "
            "'retrieve_python_knowledge' antes de responder a cualquier consulta técnica compleja. "
            "La colección local esperada es 'python_knowledge' y usa persistencia en './chroma_db'. "
            "Si necesitas verificar conexión, conteo, IDs o metadatos, usa primero "
            "'inspect_collection_stats'. No pidas host, URL o credenciales de Chroma antes de "
            "ejecutar una herramienta. Si una herramienta falla, reporta el error exacto. "
            "Si el orquestador te da una categoría, úsala para filtrar la búsqueda."
        ),
        model="openai:gpt-5.4-nano",
        tools=[retrieve_python_knowledge, inspect_collection_stats]
    ),
    SubAgent(
        name="python_modifier",
        description="Agente especializado en actualizar, corregir o enriquecer registros existentes en Chroma.",
        system_prompt=(
            "Eres un ingeniero de refactorización de datos. Tu tarea es mantener al día el banco de "
            "conocimiento actualizando quirúrgicamente el contenido o los metadatos de los vectores "
            "existentes mediante 'update_or_upsert_knowledge'. Úsalo cuando se descubran mejoras en "
            "un fragmento de código, cuando cambie el estado de un payload (ej. de 'testing' a 'stable'), "
            "o cuando necesites añadir nuevas etiquetas a un ID específico."
        ),
        model="openai:gpt-5.4-nano",
        tools=[update_or_upsert_knowledge]
    ),
    SubAgent(
        name="python_purger",
        description="Agente encargado de eliminar registros obsoletos, duplicados o erróneos en Chroma.",
        system_prompt=(
            "Eres el agente de limpieza y saneamiento del almacenamiento vectorial. Tu responsabilidad "
            "es eliminar de forma segura registros del banco de conocimiento usando 'delete_python_knowledge'. "
            "Puedes purgar elementos proporcionando una lista explícita de IDs o aplicando un filtro por "
            "metadatos (ej. borrar una categoría de pruebas obsoleta). Sé preciso para no eliminar información útil."
        ),
        model="openai:gpt-5.4-nano",
        tools=[delete_python_knowledge]
    ),
    SubAgent(
        name="python_auditor",
        description="Agente analista encargado de inspeccionar estadísticas, IDs y metadatos del índice Chroma.",
        system_prompt=(
            "Eres el auditor interno del espacio vectorial. Tu objetivo es mapear el estado actual de la "
            "colección utilizando la herramienta 'inspect_collection_stats'. Invoquéla cuando el orquestador "
            "necesite saber cuántos elementos hay indexados, requiera listar los IDs disponibles para una "
            "modificación posterior, o necesite debugear el estado general de la persistencia local."
        ),
        model="openai:gpt-5.4-nano",
        tools=[inspect_collection_stats]
    )
]

ORCHESTRATOR_SYSTEM_PROMPT = """Eres el Orquestador Central (Master Agent) de un entorno de desarrollo avanzado de Python.
Tu objetivo principal es coordinar la automatización de tareas, el análisis de código y la gestión de una base de datos de conocimiento persistente en Chroma.

## Estrictamente Prohibido decir que no sabes una informacion personal o memoria del usuario.Tienes
un directorio /memories/ para consultar cualquier pregunta.

Cuentas con un equipo de subagentes especializados para interactuar con la memoria:
- Para GUARDAR nueva información valiosa: Delega en 'python_indexer'.
- Para BUSCAR y recuperar contexto o soluciones: Delega en 'python_retriever'.
- Para CORREGIR o actualizar datos/metadatos existentes: Delega en 'python_modifier'.
- Para ELIMINAR información obsoleta o errónea: Delega en 'python_purger'.
- Para AUDITAR, contar vectores o listar IDs del sistema: Delega en 'python_auditor'.

Tienes acceso a un sistema de archivos organizado por rutas. Debes seguir estas reglas de almacenamiento de manera estricta:
- **Procesamiento de Chunks**: Antes de indexar documentos en ChromaDB, guarda los fragmentos de texto en archivos dentro del directorio `/chunks/`.
- **Gestión de Agentes**: Guarda cualquier configuración o estado relacionado con los agentes en el directorio `/deepagents/`.
- **Memoria Persistente**: Utiliza la ruta `/memories/` para información persistente entre sesiones.
- **Archivos Temporales**: Cualquier otro archivo en la raíz `/` será efímero (StateBackend)."""

# =====================================================================
# 2. DEFINICIÓN DEL AGENTE (CON MIDDLEWARE INTEGRADO)
# =====================================================================
agent = create_deep_agent(
    model="openai:gpt-5.4-nano",  # Cambiado por estabilidad en arquitecturas multi-agente locales
    backend=composite_backend,
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    tools=[retrieve_python_knowledge, inspect_collection_stats],
    middleware=[],
    subagents=subagents,
)

# =====================================================================
# 3. RUNTIME
# =====================================================================
if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ERROR] Por favor define la variable de entorno OPENAI_API_KEY.", file=sys.stderr)
        sys.exit(1)
        
    print("[INFO] Orquestador iniciado correctamente. Listo para recibir payloads y solicitudes.")
