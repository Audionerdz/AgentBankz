<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python" alt="Python 3.12+" title="⚠️ Experimental">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/built%20with-uv-black?logo=uv" alt="Built with uv">
  <img src="https://img.shields.io/badge/ollama-qwen3--embedding-8A2BE2" alt="Ollama">
</p>

<h1 align="center">DeepAgents Playground</h1>

<blockquote>
  <strong>⚡ YAML-driven multi-agent playground</strong> — swap backends, tools, prompts, subagents, and orchestrators without touching Python.
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

<p align="center">MIT · Built with <a href="https://github.com/DiTo97/deepagents">Deep Agents</a> + <a href="https://github.com/DiTo97/deepagents-ui">Deep Agents UI</a> · <a href="https://docs.astral.sh/uv/">uv</a></p>
