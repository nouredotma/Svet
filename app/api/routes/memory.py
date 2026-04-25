from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status

from app.agent.memory import AgentMemory
from app.schemas.users import MemoryEntryResponse

router = APIRouter(prefix="/memory", tags=["memory"])

_LOCAL_USER_ID = str(UUID(int=0))


@router.get("/", response_model=list[MemoryEntryResponse])
async def list_memory() -> list[MemoryEntryResponse]:
    memory = AgentMemory()
    rows = await memory.list_recent(_LOCAL_USER_ID, limit=50)
    out: list[MemoryEntryResponse] = []
    for pl in rows:
        ts_raw = pl.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now()
        else:
            ts = datetime.now()
        out.append(
            MemoryEntryResponse(
                prompt=str(pl.get("prompt", "")),
                result=str(pl.get("result", "")),
                timestamp=ts,
            )
        )
    return out


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def clear_memory() -> None:
    memory = AgentMemory()
    await memory.delete_all_for_user(_LOCAL_USER_ID)

