import os
import uuid
from typing import Any, Dict, List, Optional

# Dependencias estrictas del módulo (fail-fast si no están instaladas)
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings

# --- Inicialización perezosa interna ---
_embeddings: Optional[OpenAIEmbeddings] = None
_vector_store: Optional[Chroma] = None


def ensure_vector_store() -> tuple[OpenAIEmbeddings, Chroma]:
    """Inicializa y devuelve (embeddings, vector_store).

    Lanza RuntimeError con un mensaje claro si la inicialización de la
    infraestructura bajo demanda falla.
    """
    global _embeddings, _vector_store
    if _embeddings is not None and _vector_store is not None:
        return _embeddings, _vector_store

    try:
        _embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"),
            base_url=os.getenv("EMBEDDINGS_BASE_URL"),
            api_key=os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY"),
            check_embedding_ctx_length=False,
        )

        _vector_store = Chroma(
            collection_name="python_knowledge",
            embedding_function=_embeddings,
            persist_directory="./chroma_db",
        )
        return _embeddings, _vector_store
    except Exception as e:
        raise RuntimeError(f"No se pudo inicializar embeddings/Chroma: {e}")


# =====================================================================
# NÚCLEO RAG (HERRAMIENTAS PARA AGENTES)
# =====================================================================

@tool
def index_python_chunk(content: str, category: str = "general") -> str:
    """Indexa un fragmento (chunk) de código o documentación de Python en el banco de conocimiento.
    
    Usa esta herramienta cuando descubras o generes información valiosa sobre Python que deba recordarse.
    """
    try:
        _, store = ensure_vector_store()
        doc_id = str(uuid.uuid4())
        metadata = {"category": category, "source": "agent_generation"}

        store.add_texts(
            texts=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return f"Éxito: Chunk indexado correctamente en el banco 'Python' con ID: {doc_id}."
    except Exception as e:
        return f"Error al indexar en Chroma: {e}"


@tool
def retrieve_python_knowledge(query: str, category: Optional[str] = None) -> str:
    """Busca de manera semántica información, soluciones, payloads o documentación sobre Python 
    dentro del banco de conocimiento. Retorna los fragmentos más relevantes.
    """
    try:
        _, store = ensure_vector_store()
        search_filter = {"category": category} if category else None

        results = store.similarity_search(query, k=3, filter=search_filter)
        if not results and search_filter:
            results = store.similarity_search(query, k=3)

        if not results:
            return "No se encontró información relevante en el banco de conocimiento de Python."

        formatted_results = []
        for i, doc in enumerate(results, 1):
            meta = getattr(doc, 'metadata', {}) or getattr(doc, 'metadata_', {}) or {}
            content = getattr(doc, 'page_content', None) or getattr(doc, 'content', None) or str(doc)
            formatted_results.append(f"--- Resultado {i} (Categoría: {meta.get('category')}) ---\n{content}\n")

        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error al realizar el retrieval en Chroma: {e}"


# =====================================================================
# HERRAMIENTAS DE CONTROL TOTAL (CRUD & INGENIERÍA)
# =====================================================================

@tool
def delete_python_knowledge(ids: Optional[List[str]] = None, filter_dict: Optional[Dict[str, Any]] = None) -> str:
    """Borra registros específicos de la base de datos de vectores.
    
    Puedes borrar pasando una lista explícita de 'ids' O proporcionando un 'filter_dict' 
    (ej. {"category": "deprecated_payloads"}) para borrados masivos basados en metadatos.
    """
    try:
        _, store = ensure_vector_store()

        if ids:
            store.delete(ids=ids)
            return f"Éxito: Se eliminaron correctamente los registros con IDs: {ids}."
        
        if filter_dict:
            collection = store._collection
            collection.delete(where=filter_dict)
            return f"Éxito: Se eliminaron los vectores que coinciden con el filtro: {filter_dict}."
            
        return "Error: Debes proporcionar al menos una lista de 'ids' o un 'filter_dict' para ejecutar el borrado."
    except Exception as e:
        return f"Error al eliminar registros en Chroma: {e}"


@tool
def update_or_upsert_knowledge(doc_id: str, content: Optional[str] = None, metadata_updates: Optional[Dict[str, Any]] = None) -> str:
    """Actualiza de forma quirúrgica el contenido, los metadatos o ambos de un vector existente usando su ID.
    
    Si cambias el contenido, el embedding se recalculará automáticamente. Las actualizaciones de 
    metadatos se fusionarán con las existentes o las sobrescribirán.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        current_data = collection.get(ids=[doc_id])
        
        if not current_data or not current_data['ids']:
            return f"Error: No se encontró ningún documento con el ID: {doc_id}."
        
        current_metadata = current_data['metadatas'][0] if current_data['metadatas'] else {}
        if metadata_updates:
            current_metadata.update(metadata_updates)
        
        # 1. Re-indexación si el contenido de texto cambió
        if content:
            updated_doc = Document(page_content=content, metadata=current_metadata)
            store.update_documents(ids=[doc_id], documents=[updated_doc])
            return f"Éxito: Contenido y embeddings actualizados para el ID: {doc_id}."
            
        # 2. Mutación exclusiva de metadatos (Sin recalcular embeddings, rápido)
        if metadata_updates:
            collection.update(ids=[doc_id], metadatas=[current_metadata])
            return f"Éxito: Metadatos actualizados quirúrgicamente para el ID: {doc_id}."
            
        return "Advertencia: No se proporcionaron cambios ni de contenido ni de metadatos."
    except Exception as e:
        return f"Error al actualizar el conocimiento en Chroma: {e}"


@tool
def inspect_collection_stats(limit: int = 10, offset: int = 0) -> str:
    """Inspecciona el estado interno del banco de conocimiento. Retorna el conteo total de 
    vectores indexados y una lista paginada de los IDs con sus respectivos metadatos.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        total_count = collection.count()
        
        if total_count == 0:
            return "El banco de conocimiento está vacío actualmente."
            
        peek_data = collection.get(limit=limit, offset=offset, include=["metadatas"])
        
        summary = [
            "=== ESTADO DEL BANCO DE CONOCIMIENTO ===",
            f"Total de vectores indexados: {total_count}",
            f"Mostrando registros del {offset} al {offset + len(peek_data['ids'])}:\n"
        ]
        
        for i, doc_id in enumerate(peek_data['ids']):
            meta = peek_data['metadatas'][i] if peek_data['metadatas'] else {}
            summary.append(f"-> ID: {doc_id} | Metadatos: {meta}")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Error al inspeccionar la colección Chroma: {e}"