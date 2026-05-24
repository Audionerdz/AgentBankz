# macOS Setup Guide

Run AgentBankz natively on macOS without Docker.

---

## Prerequisites

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install tools
brew install uv postgresql@16 ollama
```

---

## 1. PostgreSQL — First Time Setup

### Start and enable at login

```bash
brew services start postgresql@16
```

### Verify it's running

```bash
pg_isready
# → /var/run/postgresql.socket:5432 - accepting connections
```

### Create the database user (if first install)

Homebrew creates a default `postgres` superuser automatically. If you get authentication errors:

```bash
# Create the postgres role with a password
psql -c "ALTER USER postgres PASSWORD 'agentbankz';"
```

### Create the application database (optional)

The app auto-creates the database on first run, but you can do it manually:

```bash
createdb deepagents
```

> **Note:** The code defaults to `DB_NAME=deepagents`. If you set `DB_NAME=agentbankz` in `.env`, use `createdb agentbankz` instead. Just keep them consistent.

### Test connection

```bash
psql -d deepagents -c "SELECT 1 AS ok;"
# →  ok
# → ──
# →   1
```

---

## 2. Ollama — Embedding Model

```bash
# Start Ollama
brew services start ollama

# Verify
ollama list

# Pull the embedding model
ollama pull qwen3-embedding:latest
```

---

## 3. ChromaDB

ChromaDB runs **embedded** — no server to install. It's a Python library that persists vectors to `./data/chroma_db` automatically. Just run `uv sync` and it works.

---

## 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum set:

```env
OPENAI_API_KEY=sk-...
```

Default values already point to your local services:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=deepagents
DB_USER=postgres
DB_PASSWORD=agentbankz
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 5. Start Backend

```bash
uv sync
uv run langgraph dev --port 8123
```

Server starts at http://localhost:8123.

---

## 6. Start Frontend

In a separate terminal:

```bash
cd deep-agents-ui
npm install
npm run dev
```

Opens at http://localhost:3000.

---

## Useful Commands

```bash
# Stop services
brew services stop postgresql@16
brew services stop ollama

# Drop and recreate database
dropdb deepagents && createdb deepagents

# Check Chroma vector count
uv run python -c "from agentbankz.tools.knowledge import inspect_collection_stats; print(inspect_collection_stats.invoke({}))"

# Rebuild Python deps
uv sync --frozen
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `psycopg` connection error | `brew services restart postgresql@16` then `pg_isready` |
| `role "postgres" does not exist` | `createuser -s postgres` |
| `FATAL: password authentication failed` | Run `psql -c "ALTER USER postgres PASSWORD 'agentbankz';"` |
| Ollama not responding | `brew services restart ollama` — wait 5s |
| ChromaDB errors | Make sure Ollama is running (Chroma uses Ollama for embeddings) |
| Frontend can't reach backend | Set `NEXT_PUBLIC_LANGGRAPH_DEPLOYMENT_URL=http://localhost:8123` |
| `uv` command not found | `brew install uv` or restart terminal |
