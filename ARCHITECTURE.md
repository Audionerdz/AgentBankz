# AgentVault Architecture Guide

> A comprehensive reference for extending, modifying, and scaling the AgentVault multi-agent system.

---

## 1. Repository Map

```
AgentVault/
│
├── main.py                              # Entry point — 7 lines of orchestration logic
├── pyproject.toml                       # Build config (setuptools, src/ layout)
│
├── src/agentvault/
│   │
│   ├── agents/                          # ██ ORCHESTRATOR & SUBAGENT SYSTEM ██
│   │   ├── __init__.py                  #   Exports: OrchestratorFactory
│   │   ├── defaults.yml           #   YAML: default model config
│   ├── subagents.yml          #   YAML: declarative subagent definitions
│   ├── orchestrators.yml      #   YAML: orchestrator definitions (refs subagents)
│   │   ├── orchestrator_factory.py      #   Factory: reads YAML → create_deep_agent()
│   │   ├── loader.py                    #   Resolver: YAML config → SubAgent objects
│   │   └── gmail.py                     #   Builder: generates SubAgents from Zapier MCP tools
│   │
│   ├── backends/                        # ██ STORAGE BACKENDS ██
│   │   ├── __init__.py                  #   Exports: BackendFactory
│   │   ├── factory.py                   #   Factory: builds CompositeBackend with routing
│   │   └── postgres.py                  #   SyncPostgresBackend implementation
│   │
│   └── tools/                           # ██ TOOL IMPLEMENTATIONS ██
│       ├── knowledge.py                 #   5 RAG tools (index, retrieve, update, delete, inspect)
│       └── zapier.py                     #   MCP client + adapter (create_zapier_tools)
│
├── data/                                # Runtime data (gitignored)
│   ├── chroma_db/                       #   ChromaDB persistent vector store
│   ├── chunks/                          #   FilesystemBackend: text chunks
│   └── deepagents/                      #   FilesystemBackend: agent state
│
├── ARCHITECTURE.md                      # This file
├── README.md                            # Project overview + quick start
└── .env                                 # Secrets (gitignored)
```

---

## 2. Data Flow

```
User Query
    │
    ▼
Orchestrator (main.py)
    │  create_deep_agent(model, backend, system_prompt, tools, subagents)
    │
    ├── LLM decides which SubAgent to delegate to
    │
    ├── python_retriever ──► retrieve_python_knowledge() ──► ChromaDB ──► Ollama
    ├── python_indexer   ──► index_python_chunk()       ──► ChromaDB ──► Ollama
    ├── python_modifier  ──► update_or_upsert_knowledge()──► ChromaDB
    ├── python_purger    ──► delete_python_knowledge()   ──► ChromaDB
    ├── python_auditor   ──► inspect_collection_stats()  ──► ChromaDB
    │
    └── gmail_message    ──► Zapier MCP (read/write)    ──► Gmail API
    └── gmail_delete_*   ──► Zapier MCP (write)          ──► Gmail API
    └── gmail_attachment ──► Zapier MCP (read)           ──► Gmail API

Backend (transparent to agent logic)
    ├── /memories/    ──► PostgreSQL (persistent across sessions)
    ├── /chunks/      ──► Filesystem (local temp storage)
    ├── /deepagents/  ──► Filesystem (agent configuration state)
    └── /             ──► StateBackend (ephemeral, in-memory)
```

---

## 3. Design Patterns — Deep Dive

### 3.1 Factory Pattern

**Where:** `OrchestratorFactory`, `BackendFactory`, `zapier.py`

Each factory encapsulates the **creation logic** of a family of objects:

```python
# orchestrator_factory.py
class OrchestratorFactory:
    def __init__(self, config_path, tool_map, zapier_tools):
        self.config = load_yaml_config(config_path)
        self.subagent_map = build_all_subagents(self.config, tool_map, zapier_tools)

    def build_one(self, name, backend, **overrides):
        # Reads YAML orchestrator block + overrides → create_deep_agent()
        ...

    def build_all(self, backend_map):
        # Iterates YAML orchestrators → build_one() for each
        ...
```

**To extend:** Add a new factory subclass (e.g. `SlackToolFactory`) that produces a different family of tools.

### 3.2 Strategy Pattern

**Where:** Every `SubAgent` in `orchestrators.yml`

Each subagent is a **strategy** — a self-contained agent with its own tools, prompt, and model. The LLM orchestrator chooses which strategy to use based on the user's intent.

```yaml
python_indexer:      # Strategy #1: Knowledge ingestion
  source: static
  tools: [index_python_chunk]
  prompt: "You are an expert technical indexer..."

python_retriever:    # Strategy #2: Knowledge retrieval
  source: static
  tools: [retrieve_python_knowledge, inspect_collection_stats]
  prompt: "You are the information retrieval specialist..."
```

**To extend:** Add a new entry to `subagents:` in YAML. No new Python class required.

### 3.3 Singleton Pattern

**Where:** `zapier.py`

```python
class ZapierClient:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

Ensures a single MCP connection across all Zapier tools. Thread-safe with double-checked locking.

### 3.4 Adapter Pattern

**Where:** `zapier.py`

Transforms MCP tool schemas (foreign interface) into LangChain `StructuredTool` objects (target interface):

```python
def build_zapier_tools(tool_defs: list[MCPToolDef]) -> list[StructuredTool]:
    for tool_def in tool_defs:
        args_schema = create_pydantic_model_from_schema(tool_def.input_schema)
        tool = StructuredTool.from_function(
            func=lambda **kwargs: mcp_client.call(tool_def.name, kwargs),
            args_schema=args_schema,
            ...
        )
```

**To extend:** Create a new adapter for any other MCP server (Slack, Jira, GitHub, etc.).

### 3.5 Composite Pattern

**Where:** `BackendFactory.build_all()`

```python
class CompositeBackend:
    def __init__(self, routes: dict[str, Backend], default: Backend):
        ...

    def save(self, path: str, data: Any):
        backend = self._match_route(path)
        return backend.save(path, data)

    def load(self, path: str):
        backend = self._match_route(path)
        return backend.load(path)
```

Routes path prefixes to different storage backends transparently.

---

## 4. How to Add a New Static SubAgent

Adding a new Chroma-powered subagent requires **no new Python class** — just YAML + a tool.

### Step 1: Create the tool

In `tools/knowledge.py`:

```python
@tool
def my_new_tool(param: str) -> str:
    """Does something useful with Chroma."""
    ...
```

### Step 2: Register in the tool map

In `agents/loader.py`, add to `STATIC_TOOL_MAP`:

```python
STATIC_TOOL_MAP = {
    ...
    "my_new_tool": my_new_tool,
}
```

### Step 3: Define the subagent in YAML

In `agents/subagents.yml`:

```yaml
subagents:
  my_specialist:
    source: static
    description: "Agent specialized in doing X."
    tools: [my_new_tool]
    prompt: >
      You are an expert in X. Use 'my_new_tool' to accomplish Y.
```

### Step 4: Wire into an orchestrator

In the orchestrator's `subagents:` list in `agents/orchestrators.yml`:

```yaml
orchestrators:
  main:
    subagents:
      - my_specialist
```

---

## 5. How to Add a New Dynamic Tool Source

For tools that are discovered at runtime (like MCP connections).

### Step 1: Create a builder function

Following the pattern in `agents/gmail.py`:

```python
def build_slack_subagents(slack_tools: list, model: str) -> list[SubAgent]:
    subagents = []
    for tool in slack_tools:
        name = tool.name
        subagents.append(SubAgent(
            name=f"slack_{name}",
            description=f"Slack operation: {name}",
            system_prompt=f"You are a Slack expert. Use the '{name}' tool when delegated.",
            model=model,
            tools=[tool],
        ))
    return subagents
```

### Step 2: Register in the YAML

In `agents/subagents.yml`:

```yaml
subagents:
  slack:
    source: dynamic:slack
    description: "Slack agents generated from Slack MCP tools"
```

### Step 3: Handle in the loader

In `agents/loader.py`, add a branch in `build_all_subagents()`:

```python
elif source == "dynamic:slack":
    for sa in build_slack_subagents(slack_tools, default_model):
        subagents[sa["name"]] = sa
```

### Step 4: Pass tools to the factory

In `main.py`:

```python
slack_tools = create_slack_tools()
OrchestratorFactory(zapier_tools=zapier_tools, slack_tools=slack_tools)
```

---

## 6. How to Add a New Backend

### Step 1: Implement the backend class

Following the pattern in `backends/postgres.py`:

```python
class S3Backend:
    def __init__(self, bucket: str, prefix: str = ""):
        self.client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix

    def save(self, path: str, data: Any) -> str:
        key = f"{self.prefix}{path}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(data))
        return key

    def load(self, path: str) -> Any:
        key = f"{self.prefix}{path}"
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())

    def list(self, prefix: str = "") -> list[str]:
        ...
```

### Step 2: Register in the factory

In `backends/factory.py`:

```python
s3_backend = S3Backend(bucket="agentvault-data", prefix="memories/")
backend_map["composite"] = CompositeBackend(
    routes={
        "/memories/": s3_backend,
        "/chunks/": FilesystemBackend(...),
        "/deepagents/": FilesystemBackend(...),
    },
    default=StateBackend(),
)
```

### Step 3: Reference in YAML

```yaml
orchestrators:
  main:
    backend: composite
```

---

## 7. How to Add a New Orchestrator

A new orchestrator = a new independent agent with its own model, backend, tools, and subagents.

### In YAML

```yaml
orchestrators:
  main:
    model: "openai:gpt-5.4-nano"
    backend: composite
    ...

  gmail_assistant:
    model: "openai:gpt-5.4-nano"
    backend: composite
    tools: []
    subagents:
      - gmail:*
    system_prompt: |
      You are a Gmail assistant. Delegate all Gmail tasks to the gmail_* subagents.
```

### Access in code

```python
agents = orchestrator_factory.build_all(backend_map)
main_agent = agents["main"]
gmail_assistant = agents["gmail_assistant"]
```

---

## 8. Scaling Considerations

| Component | Current | Scaled |
|---|---|---|
| **ChromaDB** | Single `chroma.sqlite3` file | Dedicated Chroma server + multi-collection sharding |
| **Embeddings** | Local Ollama | Remote embedding API or GPU cluster |
| **Zapier MCP** | Single connection | Queue layer for rate limiting + retry |
| **Orchestrator** | Single orchestrator | Multi-orchestrator with hierarchical routing |
| **Backend** | Local PostgreSQL + Filesystem | S3/MinIO + Cloud SQL + Redis caching |
| **LLM** | Single GPT-5.4-nano | Model router: cheap model for simple tasks, expensive for complex |

### Performance Patterns

```python
# Before: synchronous MCP call
result = await mcp_client.call_tool("gmail_message", params)

# After: add caching + rate limiting
@lru_cache(maxsize=128)
@rate_limit(calls=10, window=60)
def cached_zapier_call(action: str, params: tuple) -> Any:
    return mcp_client.call(action, dict(params))
```

---

## 9. Configuration Reference

The config is split across **3 files** under `agents/`. The loader merges them automatically:

### `agents/defaults.yml`

```yaml
model: str                                    # Default model for all subagents
```

### `agents/subagents.yml`

```yaml
subagents:                                     # SubAgent definitions
  <name>:
    source: "static" | "dynamic:zapier" | ...  # How to build this agent
    description: str                           # Shown to orchestrator LLM
    tools?: list[str]                          # Tools (required for static)
    prompt?: str                               # System prompt (required for static)
    model?: str                                # Optional model override
```

### `agents/orchestrators.yml`

```yaml
orchestrators:                                 # Orchestrator definitions
  <name>:
    model: str                                 # Orchestrator model
    backend: str                               # Key into backend_map
    tools?: list[str]                          # Orchestrator's direct tools
    subagents?: list[str]                      # Subagents: <name> or <prefix>:*
    system_prompt: str                         # Orchestrator's system prompt
```

### Wildcard syntax

```
gmail:*    → matches all subagents with prefix "gmail_"
python:*   → matches all subagents with prefix "python_"
```

### Backward compatibility

If `defaults.yml` or `subagents.yml` are missing, `load_agent_configs()` falls back to a single monolithic `orchestrators.yml` containing all three sections.

---

## 10. File Index

| File | Purpose | Touched when |
|---|---|---|
| `main.py` | Entry point (7 lines) | Never (architectural glue) |
| `agents/defaults.yml` | Default model config | Changing the default LLM model |
| `agents/subagents.yml` | SubAgent definitions | Adding/removing subagents |
| `agents/orchestrators.yml` | Orchestrator definitions | Adding/removing orchestrators |
| `agents/loader.py` | YAML → SubAgent resolution | Adding new `source:` types |
| `agents/orchestrator_factory.py` | `create_deep_agent()` from config | Adding new orchestrator features |
| `agents/gmail.py` | Gmail SubAgent builder | Changing Gmail behavior |
| `backends/factory.py` | Backend construction | Adding new storage backends |
| `backends/postgres.py` | PostgreSQL backend | Changing PG behavior |
| `tools/knowledge.py` | ChromaDB tool functions | Adding/modifying RAG tools |
| `tools/zapier.py` | MCP client + adapter | Changing MCP transport or schema handling |

