import os
import uuid
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# Inicializar embeddings usando una API compatible con OpenAI.
embeddings = OpenAIEmbeddings(
    model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"),
    base_url=os.getenv("EMBEDDINGS_BASE_URL"),
    api_key=os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY"),
    check_embedding_ctx_length=False,
)

# Configurar/Conectar a la base de datos persistente de Chroma
# Creamos o abrimos la colección 'python_knowledge'
vector_store = Chroma(
    collection_name="python_knowledge",
    embedding_function=embeddings,
    persist_directory="./chroma_db"  # Se guardará localmente en esta carpeta
)

@tool
def index_python_chunk(content: str, category: str = "general") -> str:
    """
    Indexa un fragmento (chunk) de código o documentación de Python en el banco de conocimiento.
    Usa esta herramienta cuando descubras o generes información valiosa sobre Python que deba recordarse.
    """
    try:
        # Generar un ID único para el documento
        doc_id = str(uuid.uuid4())
        
        # Estructurar los metadatos para optimizar filtros semánticos futuros
        metadata = {"category": category, "source": "agent_generation"}
        
        # Añadir al almacén de vectores
        vector_store.add_texts(
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
        # Configurar filtro opcional por categoría si el agente lo deduce
        search_filter = {"category": category} if category else None
        
        # Realizar la búsqueda por similitud (k=3 fragmentos relevantes)
        results = vector_store.similarity_search(query, k=3, filter=search_filter)
        if not results and search_filter:
            results = vector_store.similarity_search(query, k=3)
        
        if not results:
            return "No se encontró información relevante en el banco de conocimiento de Python."
        
        # Formatear la salida para el agente
        formatted_results = []
        for i, doc in enumerate(results, 1):
            formatted_results.append(f"--- Resultado {i} (Categoría: {doc.metadata.get('category')}) ---\n{doc.page_content}\n")
            
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error al realizar el retrieval en Chroma: {str(e)}"
