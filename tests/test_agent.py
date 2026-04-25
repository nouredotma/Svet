from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.agent.orchestrator as orchestrator_mod
from app.agent.llm import LLMClient, LLMResponse
from app.agent.memory import AgentMemory
from app.agent.orchestrator import run as run_orchestrator


@pytest.mark.asyncio
async def test_llm_client_openai_compatible():
    fake_choice = MagicMock()
    fake_choice.message = MagicMock(content="ok", tool_calls=None)

    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]
    fake_completion.usage = MagicMock(prompt_tokens=3, completion_tokens=4)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_completion)

    with patch("app.agent.llm.AsyncOpenAI", return_value=fake_client):
        llm = LLMClient(api_key="x", model="gemini-2.5-flash", base_url="https://example.com/v1/")
        resp = await llm.call([{"role": "user", "content": "hi"}], [])

    assert resp.type == "text"
    assert resp.text == "ok"


@pytest.mark.asyncio
async def test_orchestrator_text_response(monkeypatch):
    async def fake_call(self, messages, tools):
        return LLMResponse(type="text", text="final answer", input_tokens=1, output_tokens=2)

    monkeypatch.setattr(LLMClient, "call", fake_call)

    async def fake_load(self, user_id: str, query: str):
        return []

    async def fake_save(self, user_id: str, prompt: str, result: str):
        return None

    monkeypatch.setattr(AgentMemory, "load", fake_load)
    monkeypatch.setattr(AgentMemory, "save", fake_save)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    import app.db.models  # noqa: F401
    from app.db.session import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    from app.db.models import Task, TaskStatus
    import uuid

    async with Session() as s:
        t = Task(
            user_id=str(uuid.uuid4()),
            prompt="hi",
            status=TaskStatus.pending,
            llm_provider="openai",
        )
        s.add(t)
        await s.commit()
        await s.refresh(t)
        task_id = str(t.id)

    result = await run_orchestrator(
        prompt="hi",
        user_id=str(uuid.uuid4()),
        task_id=task_id,
        llm_provider="openai",
        db_session_factory=Session,
    )

    assert "final answer" in result.result
    assert result.tokens_used >= 3


@pytest.mark.asyncio
async def test_orchestrator_tool_call(monkeypatch):
    calls = {"n": 0}

    async def fake_call(self, messages, tools):
        if calls["n"] == 0:
            calls["n"] += 1
            return LLMResponse(
                type="tool_call",
                tool_name="http_request_tool",
                tool_input={"url": "https://example.com", "method": "GET"},
                input_tokens=1,
                output_tokens=1,
            )
        return LLMResponse(type="text", text="done", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(LLMClient, "call", fake_call)

    async def fake_load(self, user_id: str, query: str):
        return []

    async def fake_save(self, user_id: str, prompt: str, result: str):
        return None

    monkeypatch.setattr(AgentMemory, "load", fake_load)
    monkeypatch.setattr(AgentMemory, "save", fake_save)

    monkeypatch.setitem(
        orchestrator_mod.TOOLS_REGISTRY,
        "http_request_tool",
        AsyncMock(return_value="status=200\nok"),
    )

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    import app.db.models  # noqa: F401
    from app.db.session import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)

    from app.db.models import Task, TaskStatus
    import uuid

    async with Session() as s:
        t = Task(
            user_id=str(uuid.uuid4()),
            prompt="hi",
            status=TaskStatus.pending,
            llm_provider="openai",
        )
        s.add(t)
        await s.commit()
        await s.refresh(t)
        task_id = str(t.id)

    result = await run_orchestrator(
        prompt="hi",
        user_id=str(uuid.uuid4()),
        task_id=task_id,
        llm_provider="openai",
        db_session_factory=Session,
    )

    assert result.result == "done"
    assert any(step.get("tool") == "http_request_tool" for step in result.steps)


@pytest.mark.asyncio
async def test_memory_save_and_load(monkeypatch):
    class FakeClient:
        def __init__(self) -> None:
            self.upserts = 0
            self.searches = 0

        def get_collections(self):
            return MagicMock(collections=[])

        def create_collection(self, **kwargs):
            return None

        def upsert(self, **kwargs):
            self.upserts += 1

        def search(self, **kwargs):
            self.searches += 1
            return [MagicMock(payload={"prompt": "a", "result": "b", "user_id": "u1", "timestamp": "2020-01-01T00:00:00+00:00"})]

    fake = FakeClient()
    monkeypatch.setattr("app.agent.memory.QdrantClient", lambda *a, **k: fake)

    class FakeModel:
        def embed(self, texts):
            for _ in texts:
                yield [0.0] * 384

    async def fake_get_model(cls):
        return FakeModel()

    monkeypatch.setattr(AgentMemory, "_get_model", classmethod(fake_get_model))

    mem = AgentMemory()
    await mem.save("u1", "hello", "world")
    assert fake.upserts == 1

    texts = await mem.load("u1", "hello")
    assert fake.searches == 1
    assert texts and "Past interaction" in texts[0]
