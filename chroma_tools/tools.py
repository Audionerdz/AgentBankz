import os
import uuid
from typing import Any, Dict, List, Optional

# Las dependencias de LangChain/Chroma/OpenAI pueden no estar instaladas
# y provocan ImportError al importar el módulo. Para que el paquete pueda
# importarse desde main.py (y dejar que los errores reales ocurran sólo
# al usar las funciones), encapsulamos las importaciones y proporcionamos
# stubs mínimos que permiten la importación del módulo.
try:
    from langchain_core.tools import tool
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
except Exception:
    # No-op decorator para marcar funciones como herramientas cuando
    # langchain_core no está presente. Simplemente retorna la función.
    def tool(func=None, **_kwargs):
        if func is None:
            def _decorator(f):
                return f
            return _decorator
        return func

    # Stubs que levantan en tiempo de ejecución si se intentan instanciar.
    class Chroma:
        def __init__(self, *a, **kw):
            raise RuntimeError("langchain_chroma no está instalado; instanciar Chroma fallará en tiempo de ejecución")

    class OpenAIEmbeddings:
        def __init__(self, *a, **kw):
            raise RuntimeError("langchain_openai no está instalado; usar embeddings fallará en tiempo de ejecución")

# --- Inicialización perezosa ---
# Evitamos instanciar embeddings/Chroma en el tiempo de import para que
# `import chroma_tools` no falle cuando las dependencias no estén
# instaladas. Las herramientas llamarán a `ensure_vector_store()` antes
# de usar `vector_store`.
embeddings = None
vector_store = None

def ensure_vector_store():
    """Inicializa y devuelve (embeddings, vector_store).

    Lanza RuntimeError con un mensaje claro si las dependencias no están
    presentes o la inicialización falla.
    """
    global embeddings, vector_store
    if embeddings is not None and vector_store is not None:
        return embeddings, vector_store

    try:
        # Intenta crear embeddings y la instancia de Chroma bajo demanda
        embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"),
            base_url=os.getenv("EMBEDDINGS_BASE_URL"),
            api_key=os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY"),
            check_embedding_ctx_length=False,
        )

        vector_store = Chroma(
            collection_name="python_knowledge",
            embedding_function=embeddings,
            persist_directory="./chroma_db",
        )
        return embeddings, vector_store
    except Exception as e:
        # Normalizar el error para que sea fácil de depurar desde el orquestador
        raise RuntimeError(
            "No se pudo inicializar embeddings/Chroma: " + str(e)
        )

@tool
def index_python_chunk(content: str, category: str = "general") -> str:
    """
    Indexa un fragmento (chunk) de código o documentación de Python en el banco de conocimiento.
    Usa esta herramienta cuando descubras o generes información valiosa sobre Python que deba recordarse.
    """
    try:
        # Inicializar recursos si es necesario
        _, store = ensure_vector_store()

        # Generar un ID único para el documento
        doc_id = str(uuid.uuid4())

        # Estructurar los metadatos para optimizar filtros semánticos futuros
        metadata = {"category": category, "source": "agent_generation"}

        # Añadir al almacén de vectores
        store.add_texts(
            texts=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return f"Éxito: Chunk indexado correctamente en el banco 'Python' con ID: {doc_id}."
    except Exception as e:
        return f"Error al indexar en Chroma: {str(e)}"

@tool
def retrieve_python_knowledge(query: str, category: str = None) -> str:
    """
    Busca de manera semántica información, soluciones, payloads o documentación sobre Python 
    dentro del banco de conocimiento. Retorna los fragmentos más relevantes.
    """
    try:
        # Inicializar recursos si es necesario
        _, store = ensure_vector_store()

        # Configurar filtro opcional por categoría si el agente lo deduce
        search_filter = {"category": category} if category else None

        # Realizar la búsqueda por similitud (k=3 fragmentos relevantes)
        results = store.similarity_search(query, k=3, filter=search_filter)
        if not results and search_filter:
            results = store.similarity_search(query, k=3)

        if not results:
            return "No se encontró información relevante en el banco de conocimiento de Python."

        # Formatear la salida para el agente
        formatted_results = []
        for i, doc in enumerate(results, 1):
            # Compatibilidad con distintas representaciones
            meta = getattr(doc, 'metadata', {}) or getattr(doc, 'metadata_', {}) or {}
            content = getattr(doc, 'page_content', None) or getattr(doc, 'content', None) or str(doc)
            formatted_results.append(f"--- Resultado {i} (Categoría: {meta.get('category')}) ---\n{content}\n")

        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error al realizar el retrieval en Chroma: {str(e)}"

# --- Herramientas de control total (CRUD & ingeniería) ---

@tool
def delete_python_knowledge(ids: Optional[List[str]] = None, filter_dict: Optional[Dict[str, Any]] = None) -> str:
    """
    Borra registros específicos de la base de datos de vectores.
    Puedes borrar pasando una lista explícita de 'ids' O proporcionando un 'filter_dict' 
    (ej. {"category": "deprecated_payloads"}) para borrados masivos basados en metadatos.
    """
    try:
        _, store = ensure_vector_store()

        # Chroma en LangChain permite borrar por IDs directamente
        if ids:
            store.delete(ids=ids)
            return f"Éxito: Se eliminaron correctamente los registros con IDs: {ids}."
        
        # Si no hay IDs pero hay filtro, accedemos al cliente nativo de Chroma para borrado selectivo
        if filter_dict:
            # Acceso a la colección nativa de chromadb
            collection = store._collection
            collection.delete(where=filter_dict)
            return f"Éxito: Se eliminaron los vectores que coinciden con el filtro: {filter_dict}."
            
        return "Error: Debes proporcionar al menos una lista de 'ids' o un 'filter_dict' para ejecutar el borrado."
    except Exception as e:
        return f"Error al eliminar registros en Chroma: {str(e)}"


@tool
def update_or_upsert_knowledge(doc_id: str, content: Optional[str] = None, metadata_updates: Optional[Dict[str, Any]] = None) -> str:
    """
    Actualiza de forma quirúrgica el contenido, los metadatos o ambos de un vector existente usando su ID.
    Si cambias el contenido, el embedding se recalculará automáticamente. Las actualizaciones de 
    metadatos se fusionarán con las existentes o las sobrescribirán.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        # Recuperar el estado actual del documento de forma nativa
        current_data = collection.get(ids=[doc_id])
        
        if not current_data or not current_data['ids']:
            return f"Error: No se encontró ningún documento con el ID: {doc_id}."
        
        # 1. Re-indexación si el contenido de texto cambió
        if content:
            current_metadata = current_data['metadatas'][0] if current_data['metadatas'] else {}
            if metadata_updates:
                current_metadata.update(metadata_updates)
            
            # .update_documents recalcula el embedding del nuevo contenido
            from langchain_core.documents import Document
            updated_doc = Document(page_content=content, metadata=current_metadata)
            store.update_documents(ids=[doc_id], documents=[updated_doc])
            return f"Éxito: Contenido y embeddings actualizados para el ID: {doc_id}."
            
        # 2. Mutación exclusiva de metadatos (Sin recalcular embeddings, rápido)
        elif metadata_updates:
            current_metadata = current_data['metadatas'][0] if current_data['metadatas'] else {}
            current_metadata.update(metadata_updates)
            
            collection.update(
                ids=[doc_id],
                metadatas=[current_metadata]
            )
            return f"Éxito: Metadatos actualizados quirúrgicamente para el ID: {doc_id}."
            
        return "Advertencia: No se proporcionaron cambios ni de contenido ni de metadatos."
    except Exception as e:
        return f"Error al actualizar el conocimiento en Chroma: {str(e)}"


@tool
def inspect_collection_stats(limit: int = 10, offset: int = 0) -> str:
    """
    Inspecciona el estado interno del banco de conocimiento. Retorna el conteo total de 
    vectores indexados y una lista paginada de los IDs con sus respectivos metadatos.
    Útil para auditorías de datos, depuración o cuando el agente necesita saber qué IDs existen.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        total_count = collection.count()
        
        # Obtener una muestra de IDs y metadatos (omitimos embeddings y documentos por rendimiento)
        peek_data = collection.get(
            limit=limit,
            offset=offset,
            include=["metadatas"]
        )
        
        if total_count == 0:
            return "El banco de conocimiento está vacío actualmente."
            
        summary = [f"=== ESTADO DEL BANCO DE CONOCIMIENTO ===",
                   f"Total de vectores indexados: {total_count}",
                   f"Mostrando registros del {offset} al {offset + len(peek_data['ids'])}:\n"]
        
        for i in range(len(peek_data['ids'])):
            doc_id = peek_data['ids'][i]
            meta = peek_data['metadatas'][i] if peek_data['metadatas'] else {}
            summary.append(f"-> ID: {doc_id} | Metadatos: {meta}")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Error al inspeccionar la colección Chroma: {str(e)}"
