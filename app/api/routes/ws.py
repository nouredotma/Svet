import asyncio

from fastapi import APIRouter, WebSocket, status
from sqlalchemy import select

from app.db.models import Task, TaskStatus
from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["websocket"])


@router.websocket("/tasks/{task_id}")
async def task_progress(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()

    try:
        while True:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Task).where(Task.id == task_id))
                task = result.scalar_one_or_none()

            if task is None:
                await websocket.send_json({"error": "not_found"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            steps = task.steps or []
            payload = {
                "status": task.status,
                "result": task.result,
                "error": task.error,
                "steps": steps,
                "step_count": len(steps),
            }
            await websocket.send_json(payload)

            terminal = {TaskStatus.done.value, TaskStatus.failed.value, TaskStatus.cancelled.value}
            if task.status in terminal:
                await websocket.close()
                return

            await asyncio.sleep(1)
    except Exception:
        await websocket.close()
