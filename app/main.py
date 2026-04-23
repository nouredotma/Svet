import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router
from app.api.routes.ws import router as ws_router
from app.config import get_settings
from app.workers.broker import broker, shutdown_broker, startup_broker


async def _wait_for_postgres(max_attempts: int = 20, delay_seconds: float = 1.5) -> None:
    settings = get_settings()
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn = await asyncpg.connect(settings.database_url)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            logger.info("PostgreSQL is ready (attempt {}/{})", attempt, max_attempts)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "PostgreSQL not ready yet (attempt {}/{}): {}",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                await asyncio.sleep(delay_seconds)
    raise RuntimeError(f"PostgreSQL did not become ready after {max_attempts} attempts") from last_exc


async def _run_startup_migrations() -> None:
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[1]
    alembic_ini = project_root / "alembic.ini"
    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic config not found at {alembic_ini}")

    def _upgrade() -> None:
        cfg = Config(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")

    await asyncio.to_thread(_upgrade)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await _wait_for_postgres()
        await _run_startup_migrations()
        logger.info("Database migrations are up to date")
    except Exception as exc:
        logger.exception("Failed to apply startup migrations")
        raise RuntimeError("Startup migration failed") from exc

    try:
        await startup_broker()
    except Exception as exc:
        logger.warning("Broker startup failed (worker may still run separately): {}", exc)

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

    app = FastAPI(title="Svet", lifespan=lifespan)

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

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(tasks_router)
    app.include_router(admin_router)
    app.include_router(ws_router, prefix="/ws")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
