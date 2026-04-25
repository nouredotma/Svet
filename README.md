# Dexter

Personal AI agent that lives on your desktop. Voice-controlled, fully autonomous, with memory — runs entirely on your machine with zero external services.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)
![SQLite](https://img.shields.io/badge/database-SQLite-lightgrey.svg)
![License](https://img.shields.io/badge/license-personal-orange.svg)

## Features

- 🎙️ **Voice control** — Talk to Dexter with wake word ("hey dexter") or push-to-talk
- 🧠 **Episodic memory** — Remembers past interactions using vector search (Qdrant embedded)
- 🛠️ **Tool use** — Shell commands, desktop control, file operations, web search, browser, email, calendar, screenshots
- 🛡️ **Safety system** — Destructive actions (delete, shutdown, format) require your explicit confirmation
- 📊 **Dashboard** — Built-in UI to type prompts, view tasks, manage memory, toggle tools
- ⚡ **Instant startup** — No Docker, no servers, just double-click and go (~3 seconds)

## Prerequisites

- **Python 3.12+** — [Download](https://www.python.org/downloads/)
- **Windows 10/11** (desktop overlay and voice features are Windows-specific)

That's it. No Docker, no PostgreSQL, no Redis, no Node.js.

## Quickstart

### 1. Clone & configure

```powershell
git clone <your-fork-url>
cd Dexter
copy .env.example .env
```

Edit `.env` and set your **LLM API key**:
```
LLM_API_KEY=your-gemini-or-openai-api-key
```

### 2. Create virtual environment (first time only)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r desktop\requirements.txt
```

### 3. Launch

**Double-click `start_dexter.bat`** — or run:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# In a separate terminal:
.venv\Scripts\python.exe -m desktop.main
```

The API listens on `http://localhost:8000`. An orange icon appears in your system tray.

## How to use

| Method | How |
|--------|-----|
| **Dashboard** | Double-click tray icon → type a prompt → click Send |
| **Voice** | Right-click tray → "Listen Now" → speak |
| **Wake word** | Right-click tray → toggle "Wake Word ON" → say "hey dexter" |
| **API** | `POST http://localhost:8000/tasks/` with `{"prompt": "..."}` |

## Architecture

```
start_dexter.bat
  ├── uvicorn app.main:app     → FastAPI backend (~2s startup)
  └── desktop.main             → PyQt6 tray app + voice + dashboard
```

### Data storage (all local files)

| Data | Location | Backup |
|------|----------|--------|
| Tasks & user | `data/dexter.db` (SQLite) | Copy this file |
| Agent memory | `data/qdrant/` (Qdrant embedded) | Copy this folder |
| Settings | `.env` | Copy this file |
| Agent files | `C:/Users/<you>/dexter_agent_files/` | Copy this folder |

### How the agent works

1. A task is persisted to SQLite with `pending` status and dispatched to the in-process task runner.
2. The runner loads recent memory from Qdrant (embedded), builds an LLM prompt with tool definitions, and runs an agentic loop (up to 20 steps).
3. Each tool call executes an async Python function, appends the output to the conversation, and logs structured steps.
4. When the model returns text, the final answer is stored, usage is logged, and memory is updated.

### Safety system

Dexter has a 3-layer safety system to prevent destructive actions:

| Layer | What it does |
|-------|-------------|
| **Hard block** | Commands like `rm -rf /`, `format c:`, fork bombs are **never** executed |
| **Confirmation required** | `rm`, `del`, `shutdown`, `reboot`, file overwrites, etc. → agent stops and asks you first |
| **System prompt** | LLM is instructed to never retry or work around a blocked command |

## API overview

| Area | Endpoint | Notes |
|------|----------|-------|
| Health | `GET /health` | Status check |
| Tasks | `POST /tasks/`, `GET /tasks/`, `GET /tasks/{id}`, `DELETE /tasks/{id}`, `GET /tasks/{id}/logs` | Task management |
| WebSocket | `WS /ws/tasks/{task_id}` | Live task progress updates |
| Memory | `GET /memory/`, `DELETE /memory/` | Qdrant-backed episodic memory |

## LLM configuration

Dexter uses a single OpenAI-compatible LLM provider configured through `.env`:

- Default: **Gemini 2.5 Flash**
- To switch providers, update these 3 values:
  - `LLM_API_KEY` — your API key
  - `LLM_MODEL` — model name (e.g. `gpt-4o`, `claude-3-sonnet`)
  - `LLM_BASE_URL` — provider's OpenAI-compatible endpoint

## Available tools

| Tool | Description | Safety |
|------|-------------|--------|
| `shell_tool` | Run shell commands | Confirmation for destructive commands |
| `desktop_control_tool` | Mouse, keyboard, open apps | Confirmation for risky app launches |
| `read_file_tool` / `write_file_tool` | Read/write files | Sandboxed + confirmation for overwrites |
| `screenshot_tool` | Capture screen | Sandboxed output path |
| `web_search_tool` | Search the web via SerpAPI | Safe |
| `browser_tool` | Browse web pages (Playwright) | Safe |
| `send_email_tool` / `read_email_tool` | Send/read emails via SMTP/IMAP | Safe |
| `calendar_tool` | Google Calendar integration | Safe |
| `system_info_tool` | Get system info (CPU, RAM, disk) | Safe |

## Adding a new tool

1. Create `app/agent/tools/<name>.py` with an `async def your_tool(...) -> str`.
2. Register it in `app/agent/tools/__init__.py` (`TOOLS_REGISTRY` + `get_tools_schema()` JSON schema).
3. Restart the backend.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

## Project structure

```
Dexter/
├── .env                        # Config (API keys, settings)
├── start_dexter.bat            # One-click launcher
├── requirements.txt            # Backend Python dependencies
├── app/
│   ├── main.py                 # FastAPI entrypoint + lifespan
│   ├── config.py               # Pydantic settings from .env
│   ├── security.py             # Password hashing
│   ├── api/routes/             # REST API endpoints
│   ├── agent/
│   │   ├── orchestrator.py     # Agentic loop (LLM + tools)
│   │   ├── memory.py           # Qdrant embedded memory
│   │   └── tools/              # All agent tools
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models (SQLite)
│   │   └── session.py          # Async DB session
│   ├── schemas/                # Pydantic request/response models
│   └── workers/                # In-process task runner
├── desktop/
│   ├── main.py                 # Desktop app entry point
│   ├── dashboard.py            # Dashboard UI (tasks, memory, settings)
│   ├── api_client.py           # HTTP client for backend
│   ├── voice_controller.py     # Voice input/output
│   └── requirements.txt        # Desktop Python dependencies
├── data/                       # Created on first run
│   ├── dexter.db               # SQLite database
│   └── qdrant/                 # Vector memory storage
└── tests/                      # Pytest suite
```
