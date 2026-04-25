import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.tasks import router as tasks_router
from app.api.routes.memory import router as memory_router
from app.api.routes.ws import router as ws_router
from app.config import get_settings
from app.db.session import AsyncSessionLocal, Base, engine
from app.workers.broker import broker, shutdown_broker, startup_broker
from app.db.models import User, Task
from app.security import hash_password
from uuid import UUID


async def _init_database() -> None:
    """Create all tables if they don't exist (SQLite auto-creates the file)."""
    settings = get_settings()

    # Ensure the data directory exists
    db_url = settings.database_url
    if "sqlite" in db_url:
        # Extract the file path from the URL
        # e.g. "sqlite+aiosqlite:///data/dexter.db" -> "data/dexter.db"
        parts = db_url.split("///", 1)
        if len(parts) == 2 and parts[1]:
            db_path = Path(parts[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables are ready")


async def _ensure_local_user() -> None:
    """Personal-local mode: ensure a single local user exists for FK compatibility."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        local_id = str(UUID(int=0))
        res = await session.execute(select(User).where(User.id == local_id))
        existing = res.scalar_one_or_none()
        if existing is None:
            session.add(
                User(
                    id=local_id,
                    email="local@dexter",
                    hashed_password=hash_password("local"),
                    full_name="Dexter",
                    is_active=True,
                    is_admin=True,
                    llm_provider="gemini",
                )
            )
            await session.commit()
            logger.info("Created local user")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _init_database()
        await _ensure_local_user()
    except Exception as exc:
        logger.exception("Failed to initialize database")
        raise RuntimeError("Database initialization failed") from exc

    try:
        await startup_broker()
    except Exception as exc:
        logger.warning("Broker startup failed: {}", exc)

    yield

    try:
        await shutdown_broker()
    except Exception as exc:
        logger.warning("Broker shutdown failed: {}", exc)


def create_app() -> FastAPI:
    settings = get_settings()

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

    app = FastAPI(title="Dexter", lifespan=lifespan)

    configured_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.environment == "dev" and settings.cors_origins == "*":
        cors_origins = ["*"]
        cors_credentials = False
    else:
        cors_origins = configured_origins or ["https://example.com"]
        cors_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tasks_router)
    app.include_router(memory_router)
    app.include_router(ws_router, prefix="/ws")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
