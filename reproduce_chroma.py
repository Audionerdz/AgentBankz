import traceback
import os


def mask_secret(value):
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"

def main():
    print("--- ENVIRONMENT ---")
    for var in ["OPENAI_API_KEY", "EMBEDDINGS_API_KEY", "EMBEDDINGS_BASE_URL", "EMBEDDINGS_MODEL"]:
        value = os.environ.get(var)
        if "KEY" in var:
            value = mask_secret(value)
        print(f"{var} = {value!r}")

    try:
        print("\nImporting chroma_tools...")
        import chroma_tools.tools as chroma_tools_module

        retrieve_python_knowledge = chroma_tools_module.retrieve_python_knowledge
        inspect_collection_stats = chroma_tools_module.inspect_collection_stats
        print("Imported chroma_tools OK")
        print("embeddings object:", chroma_tools_module.embeddings)
        print("vector_store object:", type(chroma_tools_module.vector_store), chroma_tools_module.vector_store)
    except Exception as e:
        print("Import of chroma_tools failed:")
        traceback.print_exc()
        return

    def call_tool(t, *a, **k):
        # Tools may be plain callables (mocks) or StructuredTool objects from langchain_core.
        if callable(t):
            return t(*a, **k)
        # Common wrapper attributes that hold the underlying function
        for attr in ("func", "run", "call", "_fn"):
            if hasattr(t, attr):
                return getattr(t, attr)(*a, **k)
        raise RuntimeError("Unsupported tool object type: cannot call")

    try:
        print("\nInspecting collection (inspect_collection_stats)...")
        print(call_tool(inspect_collection_stats))
    except Exception:
        print("inspect_collection_stats raised:")
        traceback.print_exc()

    try:
        print("\nRunning retrieve_python_knowledge('test query')...")
        print(call_tool(retrieve_python_knowledge, 'test query'))
    except Exception:
        print("retrieve_python_knowledge raised:")
        traceback.print_exc()

    try:
        print("\nIf embeddings object exists, trying a small embed call (if supported)...")
        embeddings = chroma_tools_module.embeddings
        if embeddings is None:
            print("embeddings is None")
        else:
            # Try common method names safely
            for method in ("embed_query", "embed_documents", "embed"):
                if hasattr(embeddings, method):
                    try:
                        fn = getattr(embeddings, method)
                        print(f"Calling embeddings.{method}('hello') ->")
                        vector = fn("hello")
                        print(f"embedding length={len(vector)}, first_5={vector[:5]}")
                        break
                    except Exception:
                        print(f"embeddings.{method} raised:")
                        traceback.print_exc()
    except Exception:
        print("Embeddings test raised:")
        traceback.print_exc()

if __name__ == '__main__':
    main()
