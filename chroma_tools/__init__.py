"""chroma_tools package -- exporta las herramientas públicas.

Hacemos la importación de submódulo de forma segura: si
chroma_tools.tools falla al importarse (p. ej. por falta de
dependencias pesadas), exponemos stubs mínimos para que
`import chroma_tools` no rompa y los atributos estén accesibles.
"""

try:
    from .tools import (
        embeddings,
        vector_store,
        index_python_chunk,
        retrieve_python_knowledge,
        delete_python_knowledge,
        update_or_upsert_knowledge,
        inspect_collection_stats,
    )
except Exception:
    # Stubs mínimos. Manténlos simples para no introducir comportamiento
    # inesperado en el import; fallan de forma explícita o devuelven mocks.
    embeddings = None
    vector_store = None

    def _stub_not_available(*a, **k):
        raise RuntimeError(
            "chroma_tools no está completamente disponible: instala langchain_chroma/langchain_openai o importa chroma_tools.tools directamente cuando las dependencias estén presentes"
        )

    def index_python_chunk(*a, **k):
        return "Mock: index_python_chunk - chroma no disponible"

    def retrieve_python_knowledge(*a, **k):
        return "Mock: retrieve_python_knowledge - chroma no disponible"

    def delete_python_knowledge(*a, **k):
        return "Mock: delete_python_knowledge - chroma no disponible"

    def update_or_upsert_knowledge(*a, **k):
        return "Mock: update_or_upsert_knowledge - chroma no disponible"

    def inspect_collection_stats(*a, **k):
        return "Mock: inspect_collection_stats - chroma no disponible"

__all__ = [
    "embeddings",
    "vector_store",
    "index_python_chunk",
    "retrieve_python_knowledge",
    "delete_python_knowledge",
    "update_or_upsert_knowledge",
    "inspect_collection_stats",
]
