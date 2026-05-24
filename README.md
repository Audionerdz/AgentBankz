<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/built%20with-uv-black?logo=uv" alt="Built with uv">
  <img src="https://img.shields.io/badge/ollama-qwen3--embedding-8A2BE2" alt="Ollama">
</p>

<h1 align="center">AgentVault</h1>

<p align="center">
  <strong>YAML-driven multi-agent orchestration</strong> — ChromaDB RAG, Gmail automation via Zapier MCP, and a composite Postgres + Filesystem backend. Built on LangGraph + deepagents.
</p>

<p align="center">
  <code>docker compose up</code> · <a href="#-quick-start">Quick Start</a> · <a href="./ARCHITECTURE.md">Architecture</a> · <a href="./GUIDE.md">Guide</a>
</p>

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

The frontend comes preconfigured — no manual setup needed.

> First run takes a few minutes (Ollama downloads `qwen3-embedding:latest` into a persistent volume).

---

## 🧠 What It Does

| Capability | How |
|-----------|-----|
| **🤖 Multi-Agent Orchestrator** | Central agent delegates to specialized subagents via YAML |
| **🔍 ChromaDB Vector RAG** | Index, semantic search, upsert, delete, inspect — 5 built-in tools |
| **📧 Gmail Automation** | Send, search, delete, handle attachments via Zapier MCP |
| **🗄️ Fully Swappable Backends** | Composite routing — swap Postgres, Filesystem, State, or bring your own |
| **🧩 Plug & Play SubAgents + Tools** | Add or swap agents and tools via YAML — zero Python changes |
| **🧬 Declarative YAML Config** | Define orchestrators, subagents, tools, backends — all from `.yml` |

---

## 🏗️ Architecture

```
┌──────────────┐     Orchestrator resolves from YAML
│ orchestrators.yml│──────────┐
└────────────────┘          │
                             ▼
                   ┌──────────────────────┐
                   │   Orchestrator       │
                   │   (main.py)          │
                   │   Central Agent      │
                   └──────┬───────────────┘
                          │ delegates to
             ┌────────────┼────────────────┐
             ▼            ▼                ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ python_*     │ │ gmail_*  │ │ Backends     │
    │ Chroma RAG   │ │ Zapier   │ │ Composite    │
    │ SubAgents    │ │ MCP Sub  │ │ PostgreSQL   │
    │ (5 tools)    │ │ Agents   │ │ Filesystem   │
    └──────┬───────┘ └──────────┘ └──────┬───────┘
           ▼                             ▼
    ┌────────────┐              ┌────────────────┐
    │ ChromaDB   │              │ /memories/  → PG│
    │ Ollama     │              │ /chunks/    → FS│
    │ embeddings │              │ /deepagents/→ FS│
    └────────────┘              │ / (root) → State│
                                └────────────────┘
```

**Stack:** Python 3.12 · LangGraph · ChromaDB · Ollama · PostgreSQL · Next.js · Zapier MCP

---

## ⚙️ Environment

| Variable | Default | Required |
|----------|---------|----------|
| `OPENAI_API_KEY` | — | ✅ Yes |
| `DB_USER` | `postgres` | ❌ |
| `DB_PASSWORD` | `agentvault` | ❌ |
| `DB_NAME` | `agentvault` | ❌ |
| `EMBEDDINGS_MODEL` | `qwen3-embedding:latest` | ❌ |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | ❌ |
| `ZAPIER_MCP_TOKEN` | — | ❌ (Gmail tools disabled) |
| `LANGSMITH_API_KEY` | — | ❌ |
| `SERVER_PORT` | `8123` | ❌ |

All Docker defaults are set via `.env.example` — just add your `OPENAI_API_KEY`.

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
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Repo map, data flow, 5 design patterns, YAML schema, extension guide |
| [`GUIDE.md`](./GUIDE.md) | Beginner's tutorial — YAML config, adding tools, subagents, debugging |

---

## 🤝 Contributing

1. Fork & branch (`feature/my-feature`)
2. Make changes
3. Verify: `uv run python -m compileall main.py src`
4. Open a Pull Request

---

<p align="center">MIT · Built with <a href="https://docs.astral.sh/uv/">uv</a></p>
