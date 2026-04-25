from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    llm_provider: str | None = None
    attachments: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional multimodal parts (OpenAI-style), e.g. image_url blocks for vision tasks.",
    )


class TaskResponse(BaseModel):
    id: str
    user_id: str
    prompt: str
    attachments: list[dict[str, Any]] | None = None
    status: str
    result: str | None
    error: str | None
    llm_provider: str
    tokens_used: int
    steps: list[dict[str, Any]] | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskLog(BaseModel):
    step: int
    tool: str
    input: dict[str, Any]
    output: str
    timestamp: datetime
