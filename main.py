#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Importaciones de LangChain y LangGraph
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

# Importaciones específicas y nativas de DeepAgents
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
from deepagents.backends import FilesystemBackend, StoreBackend, StateBackend, CompositeBackend
# Middleware oficial de integración nativa. Lo hacemos opcional para que
# el agente pueda arrancar en entornos de diagnóstico sin copilotkit.
try:
    from copilotkit import CopilotKitMiddleware
except ImportError:
    CopilotKitMiddleware = None

# =====================================================================
# 0. CONFIGURACIÓN DE HERRAMIENTAS (CHROMA)
# =====================================================================
# =====================================================================
# 0. CONFIGURACIÓN DE HERRAMIENTAS (CHROMA)
# =====================================================================
try:
    from chroma_tools.tools import (
        index_python_chunk,
        retrieve_python_knowledge,
        delete_python_knowledge,
        update_or_upsert_knowledge,
        inspect_collection_stats
    )
except ImportError:
    @tool
    def index_python_chunk(content: str, category: str = "general") -> str:
        """
        Indexa un fragmento (chunk) de código o documentación de Python en el banco de conocimiento.
        Usa esta herramienta cuando descubras o generes información valiosa sobre Python que deba recordarse.
        """
        return "Éxito: Chunk indexado correctamente en el banco 'Python' con ID: (Mock-ID-1234)."

    @tool
    def retrieve_python_knowledge(query: str, category: str = None) -> str:
        """
        Busca de manera semántica información, soluciones, payloads o documentación sobre Python 
        dentro del banco de conocimiento. Retorna los fragmentos más relevantes.
        """
        return "--- Resultado 1 (Categoría: Mock) ---\n[Contenido de prueba simulado debido a fallo de importación]\n"

    @tool
    def delete_python_knowledge(ids: list[str] = None, filter_dict: dict = None) -> str:
        """
        Borra registros específicos de la base de datos de vectores.
        Puedes borrar pasando una lista explícita de 'ids' O proporcionando un 'filter_dict' 
        (ej. {"category": "deprecated_payloads"}) para borrados masivos basados en metadatos.
        """
        if ids:
            return f"Éxito: Se eliminaron correctamente los registros con IDs: {ids} (Simulado)."
        if filter_dict:
            return f"Éxito: Se eliminaron los vectores que coinciden con el filtro: {filter_dict} (Simulado)."
        return "Error: Debes proporcionar al menos una lista de 'ids' o un 'filter_dict' para ejecutar el borrado."

    @tool
    def update_or_upsert_knowledge(doc_id: str, content: str = None, metadata_updates: dict = None) -> str:
        """
        Actualiza de forma quirúrgica el contenido, los metadatos o ambos de un vector existente usando su ID.
        Si cambias el contenido, el embedding se recalculará automáticamente. Las actualizaciones de 
        metadatos se fusionarán con las existentes o las sobrescribirán.
        """
        if content:
            return f"Éxito: Contenido y embeddings actualizados para el ID: {doc_id} (Simulado)."
        if metadata_updates:
            return f"Éxito: Metadatos actualizados quirúrgicamente para el ID: {doc_id} (Simulado)."
        return "Advertencia: No se proporcionaron cambios ni de contenido ni de metadatos."

    @tool
    def inspect_collection_stats(limit: int = 10, offset: int = 0) -> str:
        """
        Inspecciona el estado interno del banco de conocimiento. Retorna el conteo total de 
        vectores indexados y una lista paginada de los IDs con sus respectivos metadatos.
        Útil para auditorías de datos, depuración o cuando el agente necesita saber qué IDs existen.
        """
        return (
            "=== ESTADO DEL BANCO DE CONOCIMIENTO (MODO SIMULADO) ===\n"
            "Total de vectores indexados: 2\n"
            "-> ID: mock-id-abc | Metadatos: {'category': 'core', 'source': 'mock'}\n"
            "-> ID: mock-id-xyz | Metadatos: {'category': 'payload', 'source': 'mock'}"
        )
    
# ============================
# Crear directorios necesarios
# ============================

Path("data/memories").mkdir(parents=True, exist_ok=True)
Path("data/chunks").mkdir(parents=True, exist_ok=True)
Path("data/deepagents").mkdir(parents=True, exist_ok=True)    

memories_backend = FilesystemBackend(
    root_dir="data/memories",
    virtual_mode=True
)

chunks_backend = FilesystemBackend(
    root_dir="data/chunks",
    virtual_mode=True
)

deepagents_backend = FilesystemBackend(
    root_dir="data/deepagents",
    virtual_mode=True
)


# ======================================
# Crear CompositeBackend con las 3 rutas
# ======================================

composite_backend = CompositeBackend(
    default=StateBackend(),  # Para archivos temporales
    routes={
        "/memories/": memories_backend,
        "/chunks/": chunks_backend,
        "/deepagents/": deepagents_backend,
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
        model="openai:gpt-4o-mini",
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
        model="openai:gpt-4o-mini",
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
        model="openai:gpt-4o-mini",
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
        model="openai:gpt-4o-mini",
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
        model="openai:gpt-4o-mini",
        tools=[inspect_collection_stats]
    )
]
ORCHESTRATOR_SYSTEM_PROMPT = """Eres el Orquestador Central (Master Agent) de un entorno de desarrollo avanzado de Python.
Tu objetivo principal es coordinar la automatización de tareas, el análisis de código y la gestión de una base de datos de conocimiento persistente en Chroma.
La colección local principal es 'python_knowledge' y se persiste en './chroma_db'. No asumas que falta conexión ni pidas host/URL/credenciales de Chroma hasta haber delegado una auditoría o una búsqueda y haber recibido un error real.

Cuentas con un equipo de subagentes especializados para interactuar con la memoria:
- Para GUARDAR nueva información valiosa: Delega en 'python_indexer'.
- Para BUSCAR y recuperar contexto o soluciones: Delega en 'python_retriever'.
- Para CORREGIR o actualizar datos/metadatos existentes: Delega en 'python_modifier'.
- Para ELIMINAR información obsoleta o errónea: Delega en 'python_purger'.
- Para AUDITAR, contar vectores o listar IDs del sistema: Delega en 'python_auditor'.

Tienes acceso a un sistema de archivos organizado por rutas. Debes seguir estas reglas de almacenamiento de manera estricta:

- **Procesamiento de Chunks**: Antes de indexar documentos en ChromaDB, guarda los fragmentos de texto en archivos dentro del directorio `/chunks/` (ej. `/chunks/documento_v1.txt`).
- **Gestión de Agentes**: Guarda cualquier configuración, metadatos o estado relacionado con los agentes en el directorio `/deepagents/`.
- **Memoria Persistente**: Utiliza la ruta `/memories/` para información que deba persistir entre diferentes sesiones.
- **Archivos Temporales**: Cualquier otro archivo puede guardarse en la raíz `/`, pero ten en cuenta que será efímero (almacenado en `StateBackend`).

Analiza la solicitud del usuario, determina la estrategia de gestión de memoria adecuada y delega la tarea al subagente correcto."""


# =====================================================================
# 2. DEFINICIÓN DEL AGENTE (CON MIDDLEWARE INTEGRADO)
# =====================================================================
# En DeepAgents, CopilotKitMiddleware mapea los estados y streams automáticamente.
agent = create_deep_agent(
    model="openai:gpt-5-mini-2025-08-07",
    backend=composite_backend,
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    tools=[retrieve_python_knowledge, inspect_collection_stats],
    middleware=[CopilotKitMiddleware()] if CopilotKitMiddleware else [],
    subagents=subagents,
    
)

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ERROR] Por favor define la variable de entorno OPENAI_API_KEY.", file=sys.stderr)
        sys.exit(1)

   
