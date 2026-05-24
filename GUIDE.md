# AgentBankz — Beginner's Guide

> Everything you need to know to extend, modify, and understand this repo.

---

## Table of Contents

1. [How the YAML Config Works](#1-how-the-yaml-config-works)
2. [How to Add a New Tool](#2-how-to-add-a-new-tool)
3. [How to Add a New Static SubAgent](#3-how-to-add-a-new-static-subagent)
4. [How to Add a New Dynamic SubAgent Source](#4-how-to-add-a-new-dynamic-subagent-source)
5. [How to Add a New Orchestrator](#5-how-to-add-a-new-orchestrator)
6. [How to Assign a SubAgent to Any Orchestrator](#6-how-to-assign-a-subagent-to-any-orchestrator)
7. [How the Wildcard gmail: Works](#7-how-the-wildcard-gmail-works)
8. [How to Change the LLM Model](#8-how-to-change-the-llm-model)
9. [How to Add a New Environment Variable](#9-how-to-add-a-new-environment-variable)
10. [How to Add a New Backend](#10-how-to-add-a-new-backend)
11. [How the Data Flow Works](#11-how-the-data-flow-works)
12. [How to Debug When Something Fails](#12-how-to-debug-when-something-fails)
13. [Project File Cheatsheet](#13-project-file-cheatsheet)

---

## 1. How the YAML Config Works

The configuration is split across **3 files** under `src/agentbankz/agents/`. The loader merges them automatically at startup.

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
cfg = load_agent_configs("agents/")
# Result:
# {
#   "model": "openai:gpt-5.4-nano",
#   "subagents": { ... },
#   "orchestrators": { ... },
# }
```

**Key rule:** Every name must match. The name in `subagents.yml` (YAML key) is referenced in the orchestrator's `subagents:` list.

**Backward compat:** If `defaults.yml` or `subagents.yml` don't exist, the loader falls back to a single monolithic `orchestrators.yml` containing all three sections.

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

In `src/agentbankz/agents/loader.py`, add to `STATIC_TOOL_MAP`:

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

In `agents/subagents.yml`:

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

In `agents/orchestrators.yml`, under the orchestrator's `subagents:` list:

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

## 4. How to Add a New Dynamic SubAgent Source

Dynamic subagents are created at **runtime** from tools discovered by an external MCP server.

### Example: Add Slack MCP tools as subagents

**Step 1:** Create a builder function

Create `src/agentbankz/agents/slack.py`:

```python
from typing import Any
from deepagents.middleware.subagents import SubAgent


def build_slack_subagents(slack_tools: list[Any], model: str) -> list[SubAgent]:
    subagents: list[SubAgent] = []

    for tool in slack_tools:
        name = tool.name if hasattr(tool, "name") else tool.__name__
        subagents.append(
            SubAgent(
                name=f"slack_{name}",
                description=f"Slack operation '{name}' via MCP.",
                system_prompt=(
                    f"You are a Slack expert. Your only task is to invoke the "
                    f"'{name}' tool when the orchestrator requests it. "
                    f"Execute it with the exact parameters you receive.\n\n"
                    f"Mandatory rules for Slack:\n"
                    f"- Use the exact action keys provided.\n"
                    f"- Do not invent parameters.\n"
                ),
                model=model,
                tools=[tool],
            )
        )

    return subagents
```

**Step 2:** Create a Slack tool factory

Create `src/agentbankz/tools/slack.py`:

```python
# Slack MCP tool creation (similar to tools/zapier.py)
```

**Step 3:** Register the new `source:` type in the loader

In `src/agentbankz/agents/loader.py`:

```python
from agentbankz.agents.slack import build_slack_subagents

def build_all_subagents(config, tool_map, zapier_tools, slack_tools=None):
    ...
    for name, item in config.get("subagents", {}).items():
        source = item.get("source", "static")

        if source == "static":
            ...

        elif source == "dynamic:zapier":
            for sa in build_gmail_subagents(zapier_tools, default_model):
                subagents[sa["name"]] = sa

        elif source == "dynamic:slack":
            for sa in build_slack_subagents(slack_tools or [], default_model):
                subagents[sa["name"]] = sa

    return subagents
```

**Step 4:** Add to YAML

In `agents/subagents.yml`:

```yaml
subagents:
  slack:
    source: dynamic:slack
    description: "Slack agents dynamically generated from Slack MCP tools"
```

**Step 5:** Pass slack tools in `main.py`

```python
slack_tools = create_slack_tools()  # your function
OrchestratorFactory(
    zapier_tools=zapier_tools,
    slack_tools=slack_tools,
).build_all(backend_map)
```

---

## 5. How to Add a New Orchestrator

An orchestrator is a fully independent agent with its own model, backend, tools, subagents, and system prompt.

### Example: Add a `gmail_assistant` orchestrator

**Step 1:** Define it in `agents/orchestrators.yml`

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

## 7. How the Wildcard `gmail:*` Works

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

This is why `build_gmail_subagents()` names its subagents `gmail_<tool_name>` — so they match `gmail:*`.

**You can create your own wildcard pattern** by making sure your builder function uses the correct prefix:

```python
# In your builder:
SubAgent(name=f"slack_{tool.name}", ...)

# In YAML:
subagents:
  - slack:*
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
            bucket=os.getenv("S3_BUCKET", "agentbankz-data"),
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
from agentbankz.agents import OrchestratorFactory
from agentbankz.agents.gmail import build_gmail_subagents
from agentbankz.backends import BackendFactory
from agentbankz.tools.knowledge import index_python_chunk, retrieve_python_knowledge, delete_python_knowledge, update_or_upsert_knowledge, inspect_collection_stats
print('All imports OK')
"

# 3. Check the YAML config loads correctly
uv run python -c "
from agentbankz.agents.loader import load_agent_configs
cfg = load_agent_configs('src/agentbankz/agents')
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

Add them to `agents/subagents.yml`:

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

Add it to `agents/orchestrators.yml`:

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
| Register a tool so YAML can find it | `src/agentbankz/agents/loader.py` (add to `STATIC_TOOL_MAP`) |
| Add/remove a subagent | `src/agentbankz/agents/subagents.yml` |
| Add/remove an orchestrator | `src/agentbankz/agents/orchestrators.yml` |
| Change a subagent system prompt | `src/agentbankz/agents/subagents.yml` |
| Change the orchestrator system prompt | `src/agentbankz/agents/orchestrators.yml` |
| Change the default model | `src/agentbankz/agents/defaults.yml` |
| Override model per orchestrator | `src/agentbankz/agents/orchestrators.yml` |
| Add a dynamic MCP source (Slack, etc.) | Create `agents/<name>.py` + update `loader.py` |
| Add a new storage backend | Create `backends/<name>.py` + update `backends/factory.py` |
| Change the entry point | `main.py` (~7 lines, rarely touched) |
| Change Zapier connection behavior or tool schema handling | `src/agentbankz/tools/zapier.py` |
| Change Gmail subagent prompts | `src/agentbankz/agents/gmail.py` |
| Add a dependency | `pyproject.toml` (then `uv sync`) |
| Add a secret | `.env` |
