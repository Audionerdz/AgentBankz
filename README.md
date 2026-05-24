# Deep Agents Notebook

Sistema multi-agente con orquestador central, almacenamiento híbrido (PostgreSQL + ChromaDB + Neo4j), y frontend en Next.js.

## Requisitos

- **Windows 10/11** (target principal)
- **Python 3.12+** + [uv](https://docs.astral.sh/uv/)
- **Docker Desktop** (para Neo4j y PostgreSQL si no tienes uno local)
- **Ollama** (embeddings locales: `qwen3-embedding:latest`)
- **Node.js 20+** + **Yarn** (para el frontend)

## Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌────────────────┐
│  deep-agents-ui  │────▶│ LangGraph API   │────▶│  Agentes       │
│  (Next.js 3000)  │     │ Server (8123)   │     │  (main.py)     │
└─────────────────┘     └────────┬────────┘     └───────┬────────┘
                                 │                      │
                                 ▼                      ▼
                         ┌──────────────┐      ┌────────────────┐
                         │   Neo4j      │      │   ChromaDB     │
                         │  (7687/7474) │      │  (./chroma_db) │
                         └──────────────┘      └────────────────┘
                                                    │
                                                    ▼
                                            ┌────────────────┐
                                            │   Ollama       │
                                            │  (localhost:   │
                                            │   11434)       │
                                            └────────────────┘
```

- **Orquestador** en `main.py` — agente central con subagentes para Chroma + tools directas para Neo4j
- **ChromaDB** — almacenamiento vectorial persistente (embeddings con Ollama local)
- **Neo4j** — grafo de conocimiento (entidades y relaciones)
- **PostgreSQL** — memorias persistentes del sistema de archivos de los agentes

## Inicio rápido

### 1. Entorno Python

```powershell
uv sync
```

### 2. Base de datos PostgreSQL

Asegúrate de tener PostgreSQL corriendo en `localhost:5432`. La primera vez que inicies el agente, creará automáticamente la base `deepagents` y la tabla `agent_files`.

O usa Docker:
```powershell
docker run -d --name deepagents-pg `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=ladefensapirc@123 `
  -e POSTGRES_DB=deepagents `
  -p 5432:5432 `
  postgres:16
```

### 3. Ollama (embeddings locales)

```powershell
ollama pull qwen3-embedding:latest
```

### 4. Neo4j (grafo de conocimiento)

```powershell
docker compose up -d
# Browser UI: http://localhost:7474 (neo4j / deepagents)
```

### 5. Backend — LangGraph API Server

```powershell
langgraph dev --port 8123
```

Esto inicia el servidor en `http://localhost:8123`. El grafo `sample_agent` se define en `main.py:agent`.

### 6. Frontend — deep-agents-ui

```powershell
cd deep-agents-ui
yarn install
yarn dev
```

El frontend arranca en `http://localhost:3000` y se conecta al backend en `http://localhost:8123`.

## Variables de entorno (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | — | API key de OpenAI (modelo GPT-5.4-nano) |
| `LANGGRAPH_DEPLOYMENT_URL` | `http://127.0.0.1:8123` | URL del backend para el frontend |
| `DB_HOST` / `DB_PORT` | `localhost:5432` | PostgreSQL |
| `DB_NAME` | `deepagents` | Base de datos de memorias |
| `DB_USER` / `DB_PASSWORD` | `postgres` / — | Credenciales PostgreSQL |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / `deepagents` | Credenciales Neo4j |
| `EMBEDDINGS_MODEL` | `qwen3-embedding:latest` | Modelo de embeddings Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del servidor Ollama |

## Comandos útiles

```powershell
# Iniciar todo
docker compose up -d                    # Neo4j
langgraph dev --port 8123               # Backend
cd deep-agents-ui && yarn dev           # Frontend

# Detener Neo4j
docker compose down

# Ver logs de Neo4j
docker compose logs -f neo4j

# Probar conexión al grafo
uv run python -c "
from graph_tools import graph_get_schema
print(graph_get_schema.invoke({}))
"

# Tests de Chroma
uv run python -c "
from chroma_tools import inspect_collection_stats
print(inspect_collection_stats.invoke({'limit': 5}))
"
```

## Estructura del proyecto

```
deep-agents-notebook/
├── main.py                 # Agente orquestador + definición del grafo
├── chroma_tools/           # Herramientas ChromaDB (vector store)
│   ├── __init__.py
│   └── tools.py            # 5 tools: indexar, buscar, actualizar, borrar, inspeccionar
├── graph_tools/            # Herramientas Neo4j (grafo de conocimiento)
│   ├── __init__.py
│   └── tools.py            # 5 tools: entidades, relaciones, query, esquema, Cypher
├── deep-agents-ui/         # Frontend Next.js
├── notebooks/              # Notebooks Jupyter
│   └── graphrag.ipynb      # Demo de GraphRAG con Neo4j + Ollama
├── data/
│   ├── chunks/             # Chunks de texto (FilesystemBackend)
│   ├── memories/           # Memorias persistentes (PostgresBackend)
│   ├── deepagents/         # Config de agentes (FilesystemBackend)
│   └── graph/              # Archivos del grafo (FilesystemBackend)
├── docker-compose.yml      # Neo4j container
├── langgraph.json           # Config de LangGraph CLI
├── pyproject.toml           # Dependencias Python (uv)
└── .env                     # Variables de entorno
```
