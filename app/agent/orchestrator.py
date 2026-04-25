from __future__ import annotations

import inspect
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.llm import LLMClient
from app.agent.memory import AgentMemory
from app.agent.prompt_guard import validate_tool_input
from app.agent.tools import TOOLS_REGISTRY, get_tools_schema
from app.config import get_settings
from app.db.models import Task


@dataclass
class OrchestratorResult:
    result: str
    tokens_used: int
    steps: list[dict[str, Any]]

def _build_user_message(prompt: str, attachments: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not attachments:
        return {"role": "user", "content": prompt}
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for block in attachments:
        if isinstance(block, dict):
            parts.append(block)
    return {"role": "user", "content": parts}


async def run(
    prompt: str,
    user_id: str,
    task_id: str,
    *,
    llm_provider: str,
    db_session_factory: async_sessionmaker[AsyncSession],
    attachments: list[dict[str, Any]] | None = None,
) -> OrchestratorResult:
    settings = get_settings()

    llm = LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )

    memory = AgentMemory()
    memories = await memory.load(user_id, prompt)

    tools_schema = get_tools_schema()

    memory_block = "\n".join(memories) if memories else "(no relevant memory)"

    system_prompt = (
        "You are Dexter, the user's personal autonomous agent. Use tools when they materially improve correctness. "
        "If you can answer directly with high confidence, respond with plain text only.\n\n"
        "CRITICAL SAFETY RULE: If any tool returns a message containing 'CONFIRMATION REQUIRED', "
        "you MUST immediately stop what you are doing and respond to the user with:\n"
        "1. A clear explanation of what you were trying to do\n"
        "2. The exact command or action that was blocked\n"
        "3. A request for their explicit permission to proceed\n"
        "You must NEVER retry the blocked command, use a workaround, or attempt any variation "
        "without the user explicitly approving it in a new message. This is non-negotiable.\n\n"
        f"Memory context:\n{memory_block}"
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        _build_user_message(prompt, attachments),
    ]

    steps: list[dict[str, Any]] = []
    tokens_used = 0

    try:
        for step_idx in range(20):
            llm_tools = []
            for t in tools_schema:
                llm_tools.append(
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {"type": "object"}),
                    }
                )

            response = await llm.call(messages, llm_tools)
            tokens_used += int(response.input_tokens + response.output_tokens)

            if response.type == "text":
                text = response.text or ""
                await memory.save(user_id, prompt, text)

                steps.append(
                    {
                        "step": step_idx + 1,
                        "tool": "final",
                        "input": {},
                        "output": text,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                )
                await _persist_steps(db_session_factory, task_id, steps)

                return OrchestratorResult(result=text, tokens_used=tokens_used, steps=steps)

            if response.type != "tool_call":
                raise RuntimeError("Unexpected LLM response type")

            tool_name = response.tool_name or ""
            tool_input = response.tool_input or {}

            if tool_name not in TOOLS_REGISTRY:
                tool_output = f"error: unknown tool '{tool_name}'"
            else:
                ok, reason = validate_tool_input(tool_name, tool_input)
                if not ok:
                    logger.warning("Prompt guard blocked tool '{}' for task {}", tool_name, task_id)
                    tool_output = f"error: blocked by prompt guard: {reason}"
                else:
                    tool_fn = TOOLS_REGISTRY[tool_name]
                    try:
                        tool_output = await _call_tool(tool_fn, tool_input)
                    except Exception as exc:
                        logger.exception("Tool execution failed")
                        tool_output = f"error: tool raised {exc}"

            call_id = secrets.token_hex(12)
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_input, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": tool_output,
                }
            )

            steps.append(
                {
                    "step": step_idx + 1,
                    "tool": tool_name,
                    "input": tool_input,
                    "output": tool_output[:50_000],
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )
            await _persist_steps(db_session_factory, task_id, steps)

        final_text = "Agent stopped after reaching the maximum number of steps."
        await memory.save(user_id, prompt, final_text)
        return OrchestratorResult(result=final_text, tokens_used=tokens_used, steps=steps)

    except Exception as exc:
        logger.exception("Orchestrator failed")
        err_text = f"Agent failed: {exc}"
        steps.append(
            {
                "step": len(steps) + 1,
                "tool": "error",
                "input": {},
                "output": err_text,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
        )
        await _persist_steps(db_session_factory, task_id, steps)
        return OrchestratorResult(result=err_text, tokens_used=tokens_used, steps=steps)


async def _persist_steps(
    db_session_factory: async_sessionmaker[AsyncSession],
    task_id: str,
    steps: list[dict[str, Any]],
) -> None:
    async with db_session_factory() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return
        task.steps = list(steps)
        await session.commit()


async def _call_tool(fn: Any, kwargs: dict[str, Any]) -> str:
    sig = inspect.signature(fn)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return await fn(**filtered)
