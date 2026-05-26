# DeepAgents Playground — Beginner's Guide

> Everything you need to know to extend, modify, and understand the playground.

---

## Table of Contents

1. [How the YAML Config Works](#1-how-the-yaml-config-works)
2. [How to Add a New Tool](#2-how-to-add-a-new-tool)
3. [How to Add a New Static SubAgent](#3-how-to-add-a-new-static-subagent)
4. [How to Add a New MCP Server (Dynamic SubAgent Source)](#4-how-to-add-a-new-mcp-server-dynamic-subagent-source)
5. [How to Add a New Orchestrator](#5-how-to-add-a-new-orchestrator)
6. [How to Assign a SubAgent to Any Orchestrator](#6-how-to-assign-a-subagent-to-any-orchestrator)
7. [How the Wildcard prefix:* Works](#7-how-the-wildcard-prefix-works)
8. [How to Change the LLM Model](#8-how-to-change-the-llm-model)
9. [How to Add a New Environment Variable](#9-how-to-add-a-new-environment-variable)
10. [How to Add a New Backend](#10-how-to-add-a-new-backend)
11. [How the Data Flow Works](#11-how-the-data-flow-works)
12. [How to Debug When Something Fails](#12-how-to-debug-when-something-fails)
13. [Project File Cheatsheet](#13-project-file-cheatsheet)

---

## 1. How the YAML Config Works

The configuration is split across **3 files** under `src/agentbankz/orchestrators/`. The loader merges them automatically at startup.

### `defaults.yml` — Global defaults

```yaml
model: "openai:gpt-5.4-nano"    # Default model for ALL subagents
```

### `subagents.yml` — SubAgent definitions

Each entry describes one subagent or a group of dynamic subagents.

```yaml
subagents:
  python_indexer:
    source: static               # "static" = tools exist in Python code
    description: "..."           # Tells the LLM what this agent does
    tools: [index_python_chunk]  # Must exist in STATIC_TOOL_MAP
    prompt: "..."                # System prompt for this subagent

  gmail:
    source: dynamic:zapier       # "dynamic:zapier" = tools come from MCP at runtime
    description: "Gmail agents generated from Zapier MCP tools"
```

### `orchestrators.yml` — Orchestrator definitions

Each entry is one full orchestrator agent.

```yaml
orchestrators:
  main:
    model: "openai:gpt-5.4-nano"            # Can override the default
    backend: composite                       # Must match a key in backend_map
    tools: [retrieve_python_knowledge]       # Tools the orchestrator can use directly
    subagents:                               # Which subagents this orchestrator can delegate to
      - python_indexer                       #   Named subagent
      - gmail:*                              #   Wildcard: all gmail_* subagents
    system_prompt: "..."                     # Orchestrator's system prompt
```

### How merging works

`load_agent_configs()` in `loader.py` loads all 3 files and merges them into a single dict:

```python
cfg = load_agent_configs("src/agentbankz/orchestrators")
# Result:
# {
#   "model": "openai:gpt-5.4-nano",
#   "subagents": { ... },
#   "orchestrators": { ... },
# }
```

**Key rule:** Every name must match. The name in `subagents.yml` (YAML key) is referenced in the orchestrator's `subagents:` list.

**Backward compat:** If the split layout (`orchestrators/defaults.yml` + `orchestrators/orchestrators.yml` + `subagents/subagents.yml`) is absent, the loader falls back to a single monolithic `orchestrators.yml`.

---

## 2. How to Add a New Tool

Tools are Python functions decorated with `@tool` from `langchain_core.tools`. They live in `tools/knowledge.py` or a new file.

### Example: Add a `count_python_knowledge` tool

**Step 1: Write the tool function**

In `src/agentbankz/tools/knowledge.py`:

```python
@tool
def count_python_knowledge() -> str:
    """Returns the total number of vectors in the Python knowledge bank.

    Use this tool when you need a quick count of indexed items without
    retrieving the full list of IDs and metadata.
    """
    try:
        _, store = ensure_vector_store()
        collection = store._collection
        total = collection.count()
        return f"The knowledge bank contains {total} indexed vectors."
    except Exception as e:
        return f"Error counting vectors in Chroma: {e}"
```

**Step 2: Register it in the tool map**

In `src/agentbankz/subagents/loader.py`, add to `STATIC_TOOL_MAP`:

```python
from agentbankz.tools.knowledge import (
    count_python_knowledge,   # <-- add this import
    delete_python_knowledge,
    index_python_chunk,
    inspect_collection_stats,
    retrieve_python_knowledge,
    update_or_upsert_knowledge,
)

STATIC_TOOL_MAP = {
    "count_python_knowledge": count_python_knowledge,   # <-- add this entry
    "index_python_chunk": index_python_chunk,
    ...
}
```

**Step 3: Verify**

```powershell
uv run python -c "from agentbankz.tools.knowledge import count_python_knowledge; print(count_python_knowledge.invoke({}))"
```

**Step 4 (optional):** Assign it to a subagent or orchestrator in YAML (see next section).

---

## 3. How to Add a New Static SubAgent

A static subagent is one whose tools are known at **write time** (regular Python `@tool` functions).

### Full example: Create a `python_summarizer` subagent

**Step 1:** Create the tool (if it doesn't exist yet)

In `tools/knowledge.py`:

```python
@tool
def summarize_knowledge(query: str) -> str:
    """Searches the knowledge bank and returns a concise summary of findings."""
    ...
```

**Step 2:** Register in `STATIC_TOOL_MAP` in `loader.py` (same as Step 2 above)

**Step 3:** Add the subagent definition in YAML

In `subagents/subagents.yml`:

```yaml
subagents:
  python_summarizer:
    source: static
    description: "Agent that searches knowledge and returns concise summaries."
    tools: [summarize_knowledge]
    prompt: >
      You are a summarization specialist. Your task is to search the knowledge
      bank using 'summarize_knowledge' and present the user with a concise,
      well-structured summary of the findings.

      Always cite the categories your results come from.
```

**Step 4:** Wire it into an orchestrator

In `orchestrators/orchestrators.yml`, under the orchestrator's `subagents:` list:

```yaml
orchestrators:
  main:
    subagents:
      - python_indexer
      - python_retriever
      - python_summarizer      # <-- new subagent
      - gmail:*
```

**Step 5:** Optionally describe it in the orchestrator's `system_prompt` so the LLM knows when to delegate to it:

```yaml
orchestrators:
  main:
    system_prompt: |
      ...
      You have a team of specialized subagents:
      - To SUMMARIZE knowledge bank findings: Delegate to 'python_summarizer'.
      ...
```

That's it. No new Python classes, no new imports in `main.py`.

---

## 4. How to Add a New MCP Server (Dynamic SubAgent Source)

Dynamic subagents are created at **runtime** from tools discovered by an external MCP server.
The architecture uses a **3-layer contract** to keep each new MCP source minimal:

```
Layer 1: mcp/<name>.py      — MCPConnectionConfig + create function (~5 lines)
Layer 2: subagents/<name>.py     — USAGE_GUIDE string only
Layer 3: subagents/loader.py, YAML — MCP_SOURCE_MAP entry + subagents/subagents.yml + orchestrators/orchestrators.yml
```

### Step-by-step: Add a Slack MCP server

**Step 1:** Create `src/agentbankz/mcp/slack.py`

```python
from .mcp_adapter import MCPConnectionConfig, MCPToolAdapter

SLACK_CONFIG = MCPConnectionConfig(
    name="slack",
    url="https://slack-mcp.example.com/mcp/",
    token_env_var="SLACK_BOT_TOKEN",
)

def create_slack_tools() -> list:
    adapter = MCPToolAdapter(SLACK_CONFIG)
    return adapter.create_langchain_tools()
```

The `MCPConnectionConfig` dataclass accepts:
- `name` — unique identifier for this source
- `url` — MCP server endpoint URL
- `token_env_var` — env var name for the bearer token (optional)
- `headers` — extra HTTP headers (optional)
- `verify` — SSL verification: `True` (default), `False` (skip), or a path to a CA bundle

**Step 2:** Create `src/agentbankz/subagents/slack.py`

```python
SLACK_USAGE_GUIDE = """Rules for Slack:

  slack_send_message(channel: str, text: str) — Post a message to a channel
  slack_list_channels(limit: int) — List public channels
  ...

## Rules
- Use exact channel names as they appear in Slack
- ...
"""
```

**Step 3:** Register in `MCP_SOURCE_MAP`

In `src/agentbankz/subagents/loader.py`:

```python
from agentbankz.subagents.slack import SLACK_USAGE_GUIDE

MCP_SOURCE_MAP: dict[str, dict[str, Any]] = {
    "zapier": {"guide": GMAIL_ZAPIER_USAGE_GUIDE, "prefix": "gmail"},
    "obsidian": {"guide": OBSIDIAN_USAGE_GUIDE, "prefix": "obsidian"},
    "slack": {"guide": SLACK_USAGE_GUIDE, "prefix": "slack"},   # ← add this
}
```

**Step 4:** Add YAML entry

In `src/agentbankz/subagents/subagents.yml`:

```yaml
  slack:
    source: dynamic:mcp
    mcp_name: slack
    description: "Slack agents dynamically generated from Slack MCP tools"
    model: "openai:gpt-4o-mini"
```

**Step 5:** Add to orchestrator

In `src/agentbankz/orchestrators/orchestrators.yml`:

```yaml
orchestrators:
  main:
    subagents:
      - slack:*                       # ← wildcard includes all slack_* subagents
    system_prompt: |
      ...
      Slack tools:
        slack_send_message — Post messages to channels
        slack_list_channels — List public channels
      ...
```

**Step 6:** Initialize tools in `main.py`

```python
from agentbankz.tools.slack import create_slack_tools

try:
    slack_tools = create_slack_tools()
    print(f"[INFO] Slack MCP conectado — {len(slack_tools)} herramientas disponibles.")
    mcp_tools_map["slack"] = slack_tools
except Exception as e:
    print(f"[WARN] No se pudo conectar Slack MCP: {e}")

orchestrator_factory = OrchestratorFactory(mcp_tools_map=mcp_tools_map)
```

### Architecture: How the generic adapter works

`mcp/mcp_adapter.py` provides:

| Class / Function | Purpose |
|---|---|
| `MCPConnectionConfig` | Dataclass holding URL, auth, SSL settings for one MCP server |
| `MCPToolAdapter` | Connects, discovers tools, wraps them as `StructuredTool` (LangChain) |
| `_pythonize_name()` | Converts `:`, `-` in MCP tool names to `_` |
| `_generate_docstring()` | Auto-generates docstring from MCP tool schema |
| `_create_args_schema()` | Creates Pydantic model from JSON Schema |

The adapter handles:
- Async event loop in a daemon thread (one per source)
- Bearer token auth from env vars
- SSL verification (can be disabled via `verify=False`)
- Streaming HTTP transport via `fastmcp`
- Auto-generated LangChain `StructuredTool` wrappers

The generic builder `subagents/mcp_builder.py::build_mcp_subagents()` creates one `SubAgent` per tool with naming `{prefix}_{tool_name}`, injecting the `USAGE_GUIDE` into each subagent's system prompt. This is shared by ALL MCP sources — no per-source builder function needed.

---

## 5. How to Add a New Orchestrator

An orchestrator is a fully independent agent with its own model, backend, tools, subagents, and system prompt.

### Example: Add a `gmail_assistant` orchestrator

**Step 1:** Define it in `orchestrators/orchestrators.yml`

```yaml
orchestrators:
  main:
    ...  # existing orchestrator

  gmail_assistant:
    model: "openai:gpt-5.4-nano"      # Same or different model
    backend: composite                  # Same or different backend
    tools: []                           # No direct tools for this one
    subagents:
      - gmail:*                         # Only Gmail subagents
    system_prompt: |
      You are a Gmail Assistant. Your only purpose is to handle email-related
      requests. You have no knowledge of code, Chroma, or anything else.

      Delegate all Gmail tasks to the appropriate gmail_* subagent:
      - To SEARCH emails: delegate to gmail_message (read action).
      - To SEND emails: delegate to gmail_message (write action).
      - To DELETE emails: delegate to gmail_delete_email.
      - To handle ATTACHMENTS: delegate to gmail_attachment.

      If the user asks about anything other than email, politely decline.
```

**Step 2:** Access it in `main.py`

```python
agents = orchestrator_factory.build_all(backend_map)
main_agent = agents["main"]
gmail_assistant = agents["gmail_assistant"]   # Access by YAML key name
```

**Step 3 (optional):** Run both agents on different threads, or route between them.

### Orchestrator without YAML (pure Python override)

If you need to override YAML config dynamically:

```python
agent = factory.build_one(
    "main",
    backend=backend_map["composite"],
    model="openai:gpt-4o",        # Override model
    system_prompt="Custom prompt", # Override prompt
)
```

---

## 6. How to Assign a SubAgent to Any Orchestrator

A subagent defined in `subagents:` can be assigned to **any** orchestrator by mentioning its name in that orchestrator's `subagents:` list.

**YAML key name** → referenced by that name in orchestrators.

```yaml
subagents:
  python_indexer:        # ← This is the name
    source: static
    ...

orchestrators:
  main:
    subagents:
      - python_indexer    # ← Assigned here

  code_analyzer:
    subagents:
      - python_indexer    # ← Also assigned here (same subagent, reusable)
```

**Important:** The SubAgent object is **shared by reference**. If you want independent instances per orchestrator (with different prompts, for example), create separate YAML entries:

```yaml
subagents:
  indexer_for_main:
    source: static
    prompt: "You index code for the main orchestrator."
    ...

  indexer_for_analyzer:
    source: static
    prompt: "You index code for the analysis orchestrator."
    ...
```

---

## 7. How the Wildcard `prefix:*` Works

The `:*` suffix is a shorthand to include all subagents whose names start with that prefix.

| Wildcard | Matches |
|---|---|
| `gmail:*` | `gmail_message`, `gmail_delete_email`, `gmail_attachment`, etc. |
| `slack:*` | `slack_send_message`, `slack_list_channels`, etc. |
| `python:*` | `python_indexer`, `python_retriever`, etc. |

**How it works in code** (`orchestrator_factory.py:_resolve_subagents`):

```python
if name.endswith(":*"):
    prefix = name[:-2] + "_"            # "gmail:*" → "gmail_"
    # Find all subagents starting with "gmail_"
    resolved.extend(
        subagent
        for subagent_name, subagent in self.subagent_map.items()
        if subagent_name.startswith(prefix)
    )
```

This is why `build_mcp_subagents()` in `subagents/mcp_builder.py` names subagents `{prefix}_{tool_name}`:
- `prefix="gmail"` → `gmail_message`, `gmail_delete_email`, etc.
- `prefix="obsidian"` → `obsidian_vault_read`, `obsidian_vault_write`, etc.

**You can create your own wildcard pattern** by setting the `prefix` in `MCP_SOURCE_MAP`:

```python
MCP_SOURCE_MAP = {
    "slack": {"guide": SLACK_USAGE_GUIDE, "prefix": "slack"},
}
```

```yaml
# In YAML:
subagents:
  - slack:*       # matches slack_send_message, slack_list_channels, ...
```

---

## 8. How to Change the LLM Model

Models are defined in **four levels**, each overriding the previous:

### Level 1: Top-level default in `defaults.yml` (applies to all subagents)

```yaml
model: "openai:gpt-5.4-nano"       # ← Default for every subagent
```

### Level 2: Per-subagent override in `subagents.yml`

```yaml
subagents:
  python_retriever:
    model: "openai:gpt-4o-mini"    # ← Only this subagent uses gpt-4o-mini
  gmail:
    source: dynamic:zapier
    model: "openai:gpt-4o-mini"    # ← All dynamic Gmail subagents inherit this
```

### Level 3: Per-orchestrator override in `orchestrators.yml`

```yaml
orchestrators:
  main:
    model: "openai:gpt-5.4-nano"   # ← Only this orchestrator
```

### Level 4: Runtime override (highest priority)

```python
factory.build_one(
    "main",
    backend=backend_map["composite"],
    model="openai:gpt-4o",          # ← Overrides everything
)
```

**Resolution order:** Runtime > Orchestrator YAML > SubAgent YAML > Top-level YAML.

---

## 9. How to Add a New Environment Variable

**Step 1:** Add to `.env`:

```
SLACK_BOT_TOKEN=xoxb-...
```

**Step 2:** Read it in your tool or factory:

```python
import os

slack_token = os.getenv("SLACK_BOT_TOKEN")
if not slack_token:
    raise RuntimeError("SLACK_BOT_TOKEN is not set in .env")
```

**Step 3 (optional):** Document it in `README.md` env vars table.

**Note:** `.env` is automatically loaded by `deepagents` or you can use `python-dotenv`. Check `pyproject.toml` for which library loads `.env`.

---

## 10. How to Add a New Backend

A backend handles **file storage** for the agent's virtual filesystem.

### Step 1: Implement the interface

In `src/agentbankz/backends/`, create `s3.py`:

```python
import json
from typing import Any


class S3Backend:
    def __init__(self, bucket: str, prefix: str = ""):
        import boto3
        self.client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix

    def save(self, path: str, data: Any) -> str:
        key = f"{self.prefix}{path}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data),
        )
        return key

    def load(self, path: str) -> Any:
        key = f"{self.prefix}{path}"
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())

    def list(self, prefix: str = "") -> list[str]:
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=f"{self.prefix}{prefix}",
        )
        return [
            obj["Key"][len(self.prefix):]
            for obj in response.get("Contents", [])
        ]

    def delete(self, path: str) -> bool:
        key = f"{self.prefix}{path}"
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True
```

### Step 2: Register in BackendFactory

In `src/agentbankz/backends/factory.py`:

```python
from .s3 import S3Backend

class BackendFactory:
    def build_all(self) -> dict[str, Any]:
        s3_backend = S3Backend(
            bucket=os.getenv("S3_BUCKET", "deepagents-playground-data"),
            prefix="memories/",
        )
        return {
            "composite": CompositeBackend(
                routes={
                    "/memories/": s3_backend,         # ← replaced PG with S3
                    "/chunks/": FilesystemBackend(...),
                    "/deepagents/": FilesystemBackend(...),
                },
                default=StateBackend(),
            )
        }
```

### Step 3: Reference in YAML

```yaml
orchestrators:
  main:
    backend: composite    # ← key must match what BackendFactory returns
```

---

## 11. How the Data Flow Works

```
                        ┌──────────────────────────────────┐
USER                    │         YAML CONFIG              │
  │                     │  orchestrators.yml               │
  │  "search my emails" │  ├── model, backend, tools       │
  ▼                     │  ├── subagents list              │
┌──────────┐            │  └── system_prompt               │
│  main.py │────read───▶└──────────────┬───────────────────┘
│  (entry) │                           │
└──────────┘                           ▼
                              ┌──────────────────┐
                              │ OrchestratorFactory│
                              │ .build_all()      │
                              └────────┬─────────┘
                                       │ creates
                                       ▼
                              ┌──────────────────┐
                              │  create_deep_agent│
                              │  (the LLM agent)  │
                              └────────┬─────────┘
                                       │ receives user query
                                       ▼
                              ┌──────────────────┐
                              │  Orchestrator LLM  │
                              │  decides: "this is │
                              │  an email request" │
                              └────────┬─────────┘
                                       │ delegates to
                                       ▼
                              ┌──────────────────┐
                              │ gmail_message     │
                              │ (SubAgent)        │
                              │  "search emails"  │
                              └────────┬─────────┘
                                       │ calls tool
                                       ▼
                              ┌──────────────────┐
                              │ Zapier MCP        │
                              │ → Gmail API       │
                              │ → returns results │
                              └────────┬─────────┘
                                       │ response flows back
                                       ▼
                              User sees results
```

**Key insight:** The LLM decides which subagent to use, not hardcoded routing.

---

## 12. How to Debug When Something Fails

### Problem: "Subagent 'X' does not exist"

```
KeyError: Subagent 'X' does not exist
```

**Causes:**
1. The name in orchestrator's `subagents:` list doesn't match any YAML key in `subagents:`
2. For `dynamic:zapier` sources, no dynamic subagents were generated (MCP didn't connect)
3. Typo in the name

**Fix:**
```yaml
# YAML key
subagents:
  python_indexer:          # ← check this name

# Reference
orchestrators:
  main:
    subagents:
      - python_indexer     # ← matches exactly
```

### Problem: "Tool 'X' does not exist in TOOL_MAP"

```
KeyError: Tool 'count_python_knowledge' does not exist in TOOL_MAP
```

**Causes:**
1. Tool not added to `STATIC_TOOL_MAP` in `loader.py`
2. Tool function name doesn't match the string in `tools:` list in YAML

**Fix:**
```python
# loader.py
STATIC_TOOL_MAP = {
    "count_python_knowledge": count_python_knowledge,  # ← add this
}
```

```yaml
# YAML — the string after "tools:" must match the dict key in STATIC_TOOL_MAP
tools: [count_python_knowledge]
```

### Problem: "Backend 'X' does not exist in backend_map"

```
KeyError: Backend 'composite' does not exist in backend_map
```

**Causes:**
1. `BackendFactory.build_all()` returned a dict without a key matching YAML's `backend:` field
2. Backend creation failed (e.g., PostgreSQL connection error) and was skipped

**Fix:** Check `backends/factory.py::build_all()` and make sure the return dict has the key your YAML references.

### Problem: Gmail tools are not available

```
[WARN] No se pudo conectar Zapier MCP: ...
```

**Causes:**
1. `ZAPIER_MCP_TOKEN` not set in `.env`
2. Zapier MCP server is down or unreachable
3. Network/firewall blocking the connection

**Fix:** Check `.env` has a valid `ZAPIER_MCP_TOKEN`. Restart Zapier MCP.

### Problem: Orchestrator says it doesn't know something

The orchestrator should use `/memories/` for personal information. If it says "I don't know":

**Fix:** Make sure the `system_prompt` instructs it to use memories:

```
## Strictly Forbidden to say you don't know a user's personal information or memory. You have
a /memories/ directory to consult for any question.
```

### Debug commands

```powershell
# 1. Check everything compiles
uv run python -m compileall main.py src

# 2. Check all imports resolve
uv run python -c "
from agentbankz.orchestrators import OrchestratorFactory
from agentbankz.subagents.gmail import GMAIL_ZAPIER_USAGE_GUIDE
from agentbankz.backends import BackendFactory
from agentbankz.tools.knowledge import index_python_chunk, retrieve_python_knowledge, delete_python_knowledge, update_or_upsert_knowledge, inspect_collection_stats
print('All imports OK')
"

# 3. Check the YAML config loads correctly
uv run python -c "
from agentbankz.subagents.loader import load_agent_configs
cfg = load_agent_configs('src/agentbankz/orchestrators')
print('Model:', cfg.get('model'))
print('Subagents:', list(cfg.get('subagents', {}).keys()))
print('Orchestrators:', list(cfg.get('orchestrators', {}).keys()))
"

# 4. Check Chroma connection
uv run python -c "
from agentbankz.tools.knowledge import inspect_collection_stats
print(inspect_collection_stats.invoke({'limit': 3}))
"
```

---

## 13. How to Create a New Orchestrator

Steps to add a brand new orchestrator (e.g. `code_analyzer`):

### 1. Define new subagents (if needed)

Add them to `subagents/subagents.yml`:

```yaml
subagents:
  code_linter:
    source: static
    description: "Lints Python code and returns violations."
    tools: [lint_python_file]
    prompt: >
      You are a code linter. Use the 'lint_python_file' tool to analyze
      Python source files and report all style and syntax violations.

  code_formatter:
    source: static
    description: "Auto-formats Python files to match PEP 8."
    tools: [format_python_file]
    prompt: >
      You are a code formatter. Use 'format_python_file' to rewrite
      Python files following PEP 8 conventions.
```

If you don't need new subagents, skip this step — you can reuse any existing ones from `subagents.yml`.

### 2. Define the orchestrator

Add it to `orchestrators/orchestrators.yml`:

```yaml
orchestrators:
  code_analyzer:
    model: "openai:gpt-4o"              # Optional — inherits default if omitted
    backend: composite                    # Must match a key from backend_map
    tools: [retrieve_python_knowledge]   # Tools the orchestrator can call directly
    subagents:
      - code_linter                      # References names from subagents.yml
      - code_formatter
      - python_auditor                   # Can reuse existing subagents
    system_prompt: |
      You are a code analysis orchestrator. Your team includes:
      - 'code_linter': checks Python files for violations.
      - 'code_formatter': auto-formats files to PEP 8.
      - 'python_auditor': inspects the Chroma vector collection.

      Delegate to the right subagent based on the user's request.
```

### 3. Wire it in `main.py`

Replace or extend the existing factory call:

```python
orchestrators = factory.build_all(backend_map)

# Run the code_analyzer orchestrator
orchestrators["code_analyzer"].run("Analyze all .py files in src/")
```

### Advanced: Runtime overrides

```python
orchestrator = factory.build_one(
    "code_analyzer",
    backend=backend_map["composite"],
    model="openai:gpt-4o-mini",  # Override model just for this run
)
```

### Advanced: Custom backend

If your orchestrator needs a completely different storage strategy, create a new backend class in
`backends/<name>.py`, register it in `backends/factory.py`, and pass it in `backend_map` from `main.py`.

---

## 14. Project File Cheatsheet

| What you want to do | File to edit |
|---|---|
| Add a new tool function | `src/agentbankz/tools/knowledge.py` |
| Register a tool so YAML can find it | `src/agentbankz/subagents/loader.py` (add to `STATIC_TOOL_MAP`) |
| Add/remove a subagent | `src/agentbankz/subagents/subagents.yml` |
| Add/remove an orchestrator | `src/agentbankz/orchestrators/orchestrators.yml` |
| Change a subagent system prompt | `src/agentbankz/subagents/subagents.yml` |
| Change the orchestrator system prompt | `src/agentbankz/orchestrators/orchestrators.yml` |
| Change the default model | `src/agentbankz/orchestrators/defaults.yml` |
| Override model per orchestrator | `src/agentbankz/orchestrators/orchestrators.yml` |
| Add a new MCP server source | Create `mcp/<name>.py` (config) + `subagents/<name>.py` (guide) + update `subagents/loader.py` (MCP_SOURCE_MAP) + `main.py` |
| Change MCP adapter behavior (all sources) | `src/agentbankz/mcp/mcp_adapter.py` |
| Change Zapier connection | `src/agentbankz/mcp/zapier.py` |
| Change Gmail subagent prompts | `src/agentbankz/subagents/gmail.py` (GMAIL_ZAPIER_USAGE_GUIDE) |
| Change Obsidian subagent prompts | `src/agentbankz/subagents/obsidian.py` (OBSIDIAN_USAGE_GUIDE) |
| Add a dependency | `pyproject.toml` (then `uv sync`) |
| Add a secret | `.env` |
