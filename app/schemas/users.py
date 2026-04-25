from datetime import datetime

from pydantic import BaseModel


class MemoryEntryResponse(BaseModel):
    prompt: str
    result: str
    timestamp: datetime
