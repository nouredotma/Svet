from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("SECRET_KEY", "unit-test-secret-unit-test-secret-unit-test-secret")
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "gemini")
os.environ.setdefault("LLM_API_KEY", "test-llm")
os.environ.setdefault("LLM_MODEL", "gemini-2.5-flash")
os.environ.setdefault("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
os.environ.setdefault("ENVIRONMENT", "dev")

import app.db.models  # noqa: E402,F401
from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
async def engine():
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session



@pytest.fixture(autouse=True)
async def override_dependencies(engine):
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db

    yield

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def patch_agent_task_kiq(monkeypatch):
    from types import SimpleNamespace

    async def _kiq(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.routes.tasks.run_agent_task",
        SimpleNamespace(kiq=_kiq),
        raising=True,
    )
