<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python" alt="Python 3.12+" title="⚠️ Experimental">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/built%20with-uv-black?logo=uv" alt="Built with uv">
  <img src="https://img.shields.io/badge/ollama-qwen3--embedding-8A2BE2" alt="Ollama">
</p>

<h1 align="center">DeepAgents Playground</h1>

<blockquote>
  <strong>⚡ YAML-driven multi-agent playground</strong> — swap backends, tools, prompts, subagents, and orchestrators without touching Python.
  <br><br>
  The goal is to build this repo into a <strong>reference bank</strong> for creating thousands of DeepAgents applications across different use cases. Here you'll find:
  <br><br>
  <strong>🧰 Tools</strong> — LangChain <code>@tool</code>-decorated functions ready to use<br>
  <strong>🤖 SubAgents</strong> — pre-built with prompts, tools, and models assigned<br>
  <strong>🗄️ Backends</strong> — storage implementations (Postgres, Filesystem, S3, State)<br>
  <strong>⚙️ Configs</strong> — pre-built YAML configs for orchestrators, subagents, and MCP servers<br>
  <strong>📓 Notebooks</strong> — practical DeepAgents examples for quick learning<br>
  <strong>🔌 MCP Servers</strong> — ready-to-connect integrations (Zapier, Obsidian, and more)
  <br><br>
  All powered by the <a href="https://github.com/DiTo97/deepagents">Deep Agents</a> library from LangGraph.
</blockquote>

<p align="center">
  <code>docker compose up</code> · <a href="#-quick-start">Quick Start</a> · <a href="./ARCHITECTURE.md">Architecture</a> · <a href="./GUIDE.md">Guide</a>
</p>

---

## 💡 Concept

**DeepAgents Playground** is a template-based multi-agent architecture where everything is declarative.

| Layer | What you define in YAML |
|-------|------------------------|
| **Orchestrators** | Central agents with system prompts, tool lists, subagent routing |
| **SubAgents** | Specialized agents with their own model, tools, and prompts |
| **Tools** | Static Python tools + dynamic MCP server tools (Zapier, Obsidian, etc.) |
| **Backends** | Composite routing — Postgres, Filesystem, State — per orchestrator |
| **MCP Servers** | Plug any MCP server via `servers.yml` — tools auto-discovered |

Add or swap any layer by editing a `.yml` file. No Python changes needed.

### 🧩 Branch Strategy

| Branch | Purpose |
|--------|---------|
| `master` | Templates, base architecture, shared patterns |
| `prototype/*` | Specific use-case prototypes (e.g., `prototype/support-agent`, `prototype/research-agent`) |

Master contains the generic building blocks. Branches assemble them into test apps.

---

## 🚀 Quick Start

**Prerequisite:** Docker Desktop or Docker Engine.

```bash
cp .env.example .env   # then edit OPENAI_API_KEY
docker compose up --build
```

That's it. Open:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| LangGraph API | http://localhost:8123 |
| API Docs | http://localhost:8123/docs |

The frontend connects automatically — no manual setup.

> First run takes a few minutes (Ollama downloads `qwen3-embedding:latest` into a persistent volume).

---

## 🧠 Capabilities

| Capability | How |
|-----------|-----|
| **🤖 Multi-Orchestrator** | Multiple orchestrators defined in YAML, each with its own subagent set |
| **🔍 ChromaDB Vector RAG** | Index, semantic search, upsert, delete, inspect — 5 built-in tools |
| **📧 Gmail Automation** | Send, search, delete, handle attachments via Zapier MCP |
| **📝 Obsidian Vault Tools** | Read, write, search, tag, patch notes via Obsidian MCP |
| **🗄️ Swappable Backends** | Composite routing — Postgres, Filesystem, State, or custom |
| **🧩 Plug & Play Tools** | Static tools + auto-discovered MCP tools from any server |
| **🧬 Declarative YAML Config** | Orchestrators, subagents, tools, backends — all from `.yml` |

---

## 🏗️ Architecture

```
┌──────────────────┐       Orchestrator resolves from YAML
│ orchestrators.yml│──────────┐
│ subagents.yml    │          │
│ servers.yml      │          │
│ tools/           │          │
└──────────────────┘          │
                              ▼
                    ┌──────────────────────────┐
                    │   Orchestrator           │
                    │   (YAML-defined)         │
                    │   Central Agent          │
                    └──────┬───────────────────┘
                           │ delegates to
              ┌────────────┼─────────────────┐
              ▼            ▼                  ▼
     ┌──────────────┐ ┌──────────┐  ┌──────────────────┐
     │ python_*     │ │ gmail_*  │  │ obsidian_*       │
     │ Chroma RAG   │ │ Zapier   │  │ Obsidian         │
     │ SubAgents    │ │ MCP      │  │ MCP SubAgents    │
     │ (5 tools)    │ │ SubAgents│  │ (16 tools)       │
     └──────┬───────┘ └──────────┘  └──────┬───────────┘
            ▼                              ▼
     ┌────────────┐               ┌────────────────┐
     │ ChromaDB   │               │ /memories/  → PG│
     │ Ollama     │               │ /chunks/    → FS│
     │ embeddings │               │ /deepagents/→ FS│
     └────────────┘               │ / (root) → State│
                                  └────────────────┘
```

**Stack:** Python 3.12 · LangGraph · ChromaDB · Ollama · PostgreSQL · Next.js · Zapier MCP · Obsidian MCP

---

## 🧰 Tool & SubAgent Inventory

### ChromaDB CRUD — 5 tools covering the full vector store lifecycle

| Tool | CRUD | Description |
|------|------|-------------|
| `index_python_chunk` | **C**reate | Index a code/document chunk into ChromaDB with Ollama embeddings |
| `retrieve_python_knowledge` | **R**ead | Semantic search over the Python knowledge base |
| `update_or_upsert_knowledge` | **U**pdate | Update content or metadata of an existing document |
| `delete_python_knowledge` | **D**elete | Delete documents by ID or metadata filter |
| `inspect_collection_stats` | Inspect | Count vectors, list IDs, inspect metadata |

### GitHub Repository Analysis

| Tool | Description |
|------|-------------|
| `list_repo_files` | Display directory tree of any public GitHub repository |
| `fetch_github_file` | Fetch raw content of a specific file from a GitHub repo |

### MCP Servers

#### Zapier MCP — Gmail

| Tool | Action |
|------|--------|
| `execute_zapier_read_action` | Read emails, attachments (search, get by ID) |
| `execute_zapier_write_action` | Send, delete, archive, drafts, labels, replies |
| `list_enabled_zapier_actions` | List available actions for an app |

#### Obsidian MCP — Vault

| Tool | Description |
|------|-------------|
| `vault_list` | List files and directories in the vault |
| `vault_read` | Read file content, frontmatter, and tags |
| `vault_write` | Create or overwrite a vault note |
| `vault_append` | Append content to the end of a note |
| `vault_patch` | Patch a heading, block, or frontmatter |
| `vault_delete` | Delete a file from the vault |
| `vault_move` | Move or rename a vault file |
| `vault_get_document_map` | List headings, blocks, and frontmatter fields |
| `active_file_get_path` | Get vault path of the currently open file |
| `periodic_note_get_path` | Get daily/weekly/monthly note path |
| `search_simple` | Full-text search across all notes |
| `search_query` | Structured JsonLogic search against metadata |
| `tag_list` | List all tags in the vault |
| `command_list` | List all registered Obsidian commands |
| `command_execute` | Execute an Obsidian command by ID |
| `open_file` | Open a file in the Obsidian UI |

### SubAgents

| SubAgent | Source | Tools | Description |
|----------|--------|-------|-------------|
| `python_indexer` | static | `index_python_chunk` | Index code fragments into ChromaDB |
| `python_retriever` | static | `retrieve_python_knowledge`, `inspect_collection_stats` | Semantic search over stored knowledge |
| `python_modifier` | static | `update_or_upsert_knowledge` | Correct or enrich existing records |
| `python_purger` | static | `delete_python_knowledge` | Delete obsolete or duplicate records |
| `python_auditor` | static | `inspect_collection_stats` | Inspect collection count, IDs, metadata |
| `github_researcher` | static | `list_repo_files`, `fetch_github_file` | Explore and analyze GitHub repositories |
| `gmail:*` | dynamic MCP | auto-discovered from Zapier | One subagent per Gmail operation |
| `obsidian:*` | dynamic MCP | auto-discovered from Obsidian | One subagent per vault operation |

---

## ⚙️ Environment

| Variable | Default | Required |
|----------|---------|----------|
| `OPENAI_API_KEY` | — | ✅ Yes |
| `DB_USER` | `postgres` | ❌ |
| `DB_PASSWORD` | `deepagents-playground` | ❌ |
| `DB_NAME` | `deepagents-playground` | ❌ |
| `EMBEDDINGS_MODEL` | `qwen3-embedding:latest` | ❌ |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | ❌ |
| `ZAPIER_MCP_TOKEN` | — | ❌ (Gmail tools disabled) |
| `OBSIDIAN_MCP_URL` | — | ❌ (Obsidian tools disabled) |
| `LANGSMITH_API_KEY` | — | ❌ |
| `SERVER_PORT` | `8123` | ❌ |

All Docker defaults are set via `.env.example` — just add your `OPENAI_API_KEY` and any MCP tokens.

---

## 🧪 Commands

```powershell
# Start everything
docker compose up --build

# Stop (data preserved)
docker compose down

# Wipe persisted data (Postgres, Ollama, Chroma)
docker compose down -v

# Rebuild after code changes
docker compose up --build

# Run locally without Docker
uv sync
uv run python main.py

# Compile check
uv run python -m compileall main.py src
```

---

## 📚 Docs

| Guide | What's Inside |
|-------|--------------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Repo map, data flow, design patterns, YAML schema, extension guide |
| [`GUIDE.md`](./GUIDE.md) | Beginner's tutorial — YAML config, adding tools, subagents, debugging |

---

## 🤝 Contributing

1. Fork & branch (`feature/my-feature` or `prototype/my-app`)
2. Make changes
3. Verify: `uv run python -m compileall main.py src`
4. Open a Pull Request

---

<p align="center">MIT · Powered by <a href="https://github.com/DiTo97/deepagents">Deep Agents</a> + <a href="https://langchain-ai.github.io/langgraph/">LangGraph</a> + <a href="https://github.com/DiTo97/deepagents-ui">Deep Agents UI</a> · <a href="https://docs.astral.sh/uv/">uv</a></p>
