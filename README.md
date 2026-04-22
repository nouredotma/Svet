<p align="center">
  <img src="https://github.com/user-attachments/assets/128d647a-da2d-4a53-a7b1-a88af5cd2d12" alt="Svet Logo" width="200">
</p>

# Svet

AI agent orchestration API built with FastAPI, PostgreSQL, Redis, Taskiq, and Qdrant.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)

## Prerequisites

- Docker & Docker Compose (recommended for local development)
- Python 3.12+ (optional if you run outside Docker)

## Quickstart

```bash
git clone <your-fork-url>
cd Svet
copy .env.example .env   # PowerShell / Windows
# edit .env and fill API keys / secrets

docker compose up --build
```

The API listens on `http://localhost:8000`.

## API overview

| Area | Endpoint | Notes |
|------|----------|-------|
| Health | `GET /health` | Public |
| Register | `POST /auth/register` | Public |
| Login | `POST /auth/token` | Public |
| Refresh | `POST /auth/refresh` | Refresh token body |
| API keys | `POST /auth/api-keys`, `DELETE /auth/api-keys/{key_id}` | Returned secret shown once |
| Profile | `GET/PATCH /users/me` | JWT/API key |
| Memory | `GET/DELETE /users/me/memory` | Qdrant-backed episodic memory |
| Usage | `GET /users/me/usage` | Paginated usage logs |
| Tasks | `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `DELETE /tasks/{id}`, `GET /tasks/{id}/logs` | Authenticated + rate limited |
| WebSocket | `WS /ws/tasks/{task_id}?token=<jwt>` | Live task updates |

## How the agent works

1. A task is persisted with `pending` status and dispatched to a Taskiq worker.
2. The worker loads recent memory from Qdrant, builds an LLM prompt with tool definitions, and runs an agentic loop (up to 20 steps).
3. Each tool call executes an async Python tool, appends the tool output to the conversation, and logs structured steps on the task row.
4. When the model returns text, the final answer is stored, usage is logged, and memory is updated.

### LLM routing (`DEFAULT_LLM_PROVIDER=auto` by default)

- **Cerebras** (OpenAI-compatible API, `CEREBRAS_*`): used for short, text-only turns when the estimated input context is at or below `LLM_LONG_CONTEXT_THRESHOLD_TOKENS` (default **8000** estimated tokens).
- **Gemini 2.5 Flash** (Google AI Studio, OpenAI-compatible `GOOGLE_AI_API_KEY` + `GEMINI_MODEL`): used when the task includes **vision** (`image_url` blocks in `POST /tasks` `attachments`, multimodal message content, or obvious image URLs / `data:image` in text), or when estimated context is **strictly above** that threshold.
- Optional **`attachments`** on task creation accepts OpenAI-style multimodal parts (for example `{"type":"image_url","image_url":{"url":"https://..."}}`).

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest
```

## Adding a new tool

1. Create `app/agent/tools/<name>.py` with an `async def your_tool(... ) -> str`.
2. Register it in `app/agent/tools/__init__.py` (`TOOLS_REGISTRY` + `get_tools_schema()` JSON schema).
3. Redeploy/restart API + worker processes.

## Project structure

```
app/
  main.py                 # FastAPI entrypoint + lifespan (Taskiq broker hooks)
  config.py               # Pydantic settings
  dependencies.py         # Shared DI helpers
  api/                    # HTTP routes + auth/rate-limit middleware
  db/                     # SQLAlchemy models + Alembic migrations
  agent/                  # LLM client, memory, orchestrator, tools
  workers/                # Taskiq broker + agent worker task
tests/                    # Pytest suite
docker/                   # Production-oriented Dockerfile
```
