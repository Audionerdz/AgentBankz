import os
import uuid
from typing import Any, Dict, List, Optional

# Dependencias estrictas del módulo (fail-fast si no están instaladas)
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings

# --- Inicialización perezosa interna ---
_embeddings: Optional[OllamaEmbeddings] = None
_vector_store: Optional[Chroma] = None


def ensure_vector_store() -> tuple[OllamaEmbeddings, Chroma]:
    """Initializes and returns (embeddings, vector_store).

    Raises RuntimeError with a clear message if the on-demand
    infrastructure initialization fails.
    """
    global _embeddings, _vector_store
    if _embeddings is not None and _vector_store is not None:
        return _embeddings, _vector_store

    try:
        _embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDINGS_MODEL", "qwen3-embedding:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

        _vector_store = Chroma(
            collection_name="python_knowledge",
            embedding_function=_embeddings,
            persist_directory="./data/chroma_db",
        )
        return _embeddings, _vector_store
    except Exception as e:
        raise RuntimeError(f"Failed to initialize embeddings/Chroma: {e}")


# =====================================================================
# RAG CORE (AGENT TOOLS)
# =====================================================================

@tool
def index_python_chunk(content: str, category: str = "general") -> str:
    """Indexes a chunk of Python code or documentation into the knowledge bank.
    
    Use this tool when you discover or generate valuable Python information that should be remembered.
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
        return f"Success: Chunk successfully indexed in the knowledge bank with ID: {doc_id}."
    except Exception as e:
        return f"Error indexing into Chroma: {e}"


@tool
def retrieve_python_knowledge(query: str, category: Optional[str] = None) -> str:
    """Semantically searches for information, solutions, payloads, or documentation about Python 
    within the knowledge bank. Returns the most relevant fragments.
    """
    try:
        _, store = ensure_vector_store()
        search_filter = {"category": category} if category else None

        results = store.similarity_search(query, k=3, filter=search_filter)
        if not results and search_filter:
            results = store.similarity_search(query, k=3)

        if not results:
            return "No relevant information found in the Python knowledge bank."

        formatted_results = []
        for i, doc in enumerate(results, 1):
            meta = getattr(doc, 'metadata', {}) or getattr(doc, 'metadata_', {}) or {}
            content = getattr(doc, 'page_content', None) or getattr(doc, 'content', None) or str(doc)
            formatted_results.append(f"--- Result {i} (Category: {meta.get('category')}) ---\n{content}\n")

        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error performing Chroma retrieval: {e}"


# =====================================================================
# FULL CONTROL TOOLS (CRUD & ENGINEERING)
# =====================================================================

@tool
def delete_python_knowledge(ids: Optional[List[str]] = None, filter_dict: Optional[Dict[str, Any]] = None) -> str:
    """Deletes specific records from the vector database.
    
    You can delete by passing an explicit list of 'ids' OR by providing a 'filter_dict'
    (e.g. {"category": "deprecated_payloads"}) for bulk deletions based on metadata.
    """
    try:
        _, store = ensure_vector_store()

        if ids:
            store.delete(ids=ids)
            return f"Success: Records with IDs {ids} were deleted successfully."
        
        if filter_dict:
            collection = store._collection
            collection.delete(where=filter_dict)
            return f"Success: Vectors matching filter {filter_dict} were deleted successfully."
            
        return "Error: You must provide at least a list of 'ids' or a 'filter_dict' to execute the deletion."
    except Exception as e:
        return f"Error deleting records from Chroma: {e}"


@tool
def update_or_upsert_knowledge(doc_id: str, content: Optional[str] = None, metadata_updates: Optional[Dict[str, Any]] = None) -> str:
    """Surgically updates the content, metadata, or both of an existing vector using its ID.
    
    If you change the content, the embedding will be recalculated automatically. Metadata
    updates will be merged with existing ones or overwrite them.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        current_data = collection.get(ids=[doc_id])
        
        if not current_data or not current_data['ids']:
            return f"Error: No document found with ID: {doc_id}."
        
        current_metadata = current_data['metadatas'][0] if current_data['metadatas'] else {}
        if metadata_updates:
            current_metadata.update(metadata_updates)
        
        # 1. Re-indexación si el contenido de texto cambió
        if content:
            updated_doc = Document(page_content=content, metadata=current_metadata)
            store.update_documents(ids=[doc_id], documents=[updated_doc])
            return f"Success: Content and embeddings updated for ID: {doc_id}."
            
        # 2. Exclusive metadata mutation (No embedding recalculation, fast)
        if metadata_updates:
            collection.update(ids=[doc_id], metadatas=[current_metadata])
            return f"Success: Metadata surgically updated for ID: {doc_id}."
            
        return "Warning: Neither content nor metadata changes were provided."
    except Exception as e:
        return f"Error updating knowledge in Chroma: {e}"


@tool
def inspect_collection_stats(limit: int = 10, offset: int = 0) -> str:
    """Inspects the internal state of the knowledge bank. Returns the total count of
    indexed vectors and a paginated list of IDs with their respective metadata.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        total_count = collection.count()
        
        if total_count == 0:
            return "The knowledge bank is currently empty."
            
        peek_data = collection.get(limit=limit, offset=offset, include=["metadatas"])
        
        summary = [
            "=== KNOWLEDGE BANK STATUS ===",
            f"Total indexed vectors: {total_count}",
            f"Showing records from {offset} to {offset + len(peek_data['ids'])}:\n"
        ]
        
        for i, doc_id in enumerate(peek_data['ids']):
            meta = peek_data['metadatas'][i] if peek_data['metadatas'] else {}
            summary.append(f"-> ID: {doc_id} | Metadata: {meta}")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Error inspecting Chroma collection: {e}"
