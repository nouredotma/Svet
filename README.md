<p align="center">
  <img src="https://github.com/user-attachments/assets/128d647a-da2d-4a53-a7b1-a88af5cd2d12" alt="Dexter Logo" width="200">
</p>

# Dexter

Personal local AI agent built with FastAPI, PostgreSQL, Redis, Taskiq, and Qdrant.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)

## Prerequisites

- Docker & Docker Compose (recommended for local development)
- Python 3.12+ (optional if you run outside Docker)

## Quickstart

```bash
git clone <your-fork-url>
cd Dexter
copy .env.example .env   # PowerShell / Windows
# edit .env and fill API keys / secrets

docker compose up --build
```

The API listens on `http://localhost:8000`.

## Local mode (no auth)

This project is currently configured for **personal local use**:

- **No authentication** (no accounts, no API keys).
- Intended to run on your machine.
- If you deploy it later, you should re-add auth or restrict access.

## API overview

| Area | Endpoint | Notes |
|------|----------|-------|
| Health | `GET /health` | Public |
| Tasks | `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `DELETE /tasks/{id}`, `GET /tasks/{id}/logs` | Background execution via worker |
| WebSocket | `WS /ws/tasks/{task_id}` | Live task updates (optional) |
| Memory | `GET /memory/`, `DELETE /memory/` | Qdrant-backed episodic memory |

## How the agent works

1. A task is persisted with `pending` status and dispatched to a Taskiq worker.
2. The worker loads recent memory from Qdrant, builds an LLM prompt with tool definitions, and runs an agentic loop (up to 20 steps).
3. Each tool call executes an async Python tool, appends the tool output to the conversation, and logs structured steps on the task row.
4. When the model returns text, the final answer is stored, usage is logged, and memory is updated.

### LLM configuration

- Dexter uses a single OpenAI-compatible LLM provider configured through env values.
- Default setup is **Gemini 2.5 Flash** with:
  - `LLM_API_KEY`
  - `LLM_MODEL=gemini-2.5-flash`
  - `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`
- To switch providers later, update `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` only.
- Optional **`attachments`** on task creation accepts OpenAI-style multimodal parts (for example `{"type":"image_url","image_url":{"url":"https://..."}}`).

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest
```

## Adding a new tool

1. Create `app/agent/tools/<name>.py` with an `async def your_tool(... ) -> str`.
2. Register it in `app/agent/tools/__init__.py` (`TOOLS_REGISTRY` + `get_tools_schema()` JSON schema).
3. Restart API + worker processes.

## Project structure

```
app/
  main.py                 # FastAPI entrypoint + lifespan (Taskiq broker hooks)
  config.py               # Pydantic settings
  api/                    # HTTP routes + auth/rate-limit middleware
  db/                     # SQLAlchemy models + Alembic migrations
  agent/                  # LLM client, memory, orchestrator, tools
  workers/                # Taskiq broker + agent worker task
tests/                    # Pytest suite
docker/                   # Dockerfile for local dev
```
