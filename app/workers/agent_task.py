import asyncio
import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import run as run_orchestrator
from app.db.models import Task, TaskStatus, User
from app.db.session import AsyncSessionLocal
from app.workers.broker import broker


@broker.task
async def run_agent_task(task_id: str) -> None:
    last_error: str | None = None
    for attempt in range(4):
        try:
            await _run_once(task_id)
            return
        except Exception as exc:
            last_error = str(exc)
            logger.exception("Agent task {} attempt {} failed", task_id, attempt + 1)
            if attempt >= 3:
                break
            delay = (2**attempt) * 0.5
            await asyncio.sleep(delay)

    async with AsyncSessionLocal() as session:
        await _mark_failed(session, task_id, last_error or "Unknown failure")


async def _mark_failed(session: AsyncSession, task_id: str, error: str) -> None:
    tid = uuid.UUID(task_id)
    result = await session.execute(select(Task).where(Task.id == tid))
    task = result.scalar_one_or_none()
    if task is None:
        return
    task.status = TaskStatus.failed
    task.error = error
    task.completed_at = datetime.now(tz=UTC)
    await session.commit()


async def _run_once(task_id: str) -> None:
    tid = uuid.UUID(task_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == tid))
        task = result.scalar_one_or_none()
        if task is None:
            raise RuntimeError(f"Task {task_id} not found")

        user_result = await session.execute(select(User).where(User.id == task.user_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            raise RuntimeError("User not found for task")

        prompt = task.prompt
        user_id = str(task.user_id)
        attachments = task.attachments

        task.status = TaskStatus.running
        task.started_at = datetime.now(tz=UTC)
        await session.commit()

    orch_result = await run_orchestrator(
        prompt=prompt,
        user_id=user_id,
        task_id=task_id,
        llm_provider="gemini",
        db_session_factory=AsyncSessionLocal,
        attachments=attachments,
    )

    async with AsyncSessionLocal() as session:
        reload = await session.execute(select(Task).where(Task.id == tid))
        task_row = reload.scalar_one()

        task_row.result = orch_result.result
        task_row.tokens_used = orch_result.tokens_used
        task_row.steps = orch_result.steps
        task_row.status = TaskStatus.done
        task_row.completed_at = datetime.now(tz=UTC)

        await session.commit()
