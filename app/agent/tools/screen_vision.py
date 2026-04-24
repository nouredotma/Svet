from __future__ import annotations

import base64
import time
from collections import deque
from datetime import datetime, timezone
from io import BytesIO

from PIL import ImageGrab
import pyautogui

from app.agent.llm import LLMClient
from app.config import get_settings

try:
    import pygetwindow as gw
except Exception:  # noqa: BLE001
    gw = None

_LAST_CAPTURE_AT = 0.0
_COOLDOWN_SECONDS = 2.0
_VISION_HISTORY: deque[dict[str, str]] = deque(maxlen=3)


def _active_window_bbox() -> tuple[int, int, int, int] | None:
    if gw is None:
        return None
    try:
        win = gw.getActiveWindow()
        if not win:
            return None
        left = int(getattr(win, "left", 0))
        top = int(getattr(win, "top", 0))
        width = int(getattr(win, "width", 0))
        height = int(getattr(win, "height", 0))
        if width <= 0 or height <= 0:
            return None
        return (left, top, left + width, top + height)
    except Exception:  # noqa: BLE001
        return None


def _cursor_region_bbox(region_size: int) -> tuple[int, int, int, int]:
    x, y = pyautogui.position()
    half = max(120, region_size // 2)
    return (x - half, y - half, x + half, y + half)


def _capture_image(capture_mode: str, region_size: int):
    mode = capture_mode.lower().strip()
    if mode == "active_window":
        bbox = _active_window_bbox()
        if bbox:
            return ImageGrab.grab(bbox=bbox), "active_window"
        return ImageGrab.grab(), "full_screen_fallback"
    if mode == "cursor_region":
        bbox = _cursor_region_bbox(region_size=region_size)
        return ImageGrab.grab(bbox=bbox), "cursor_region"
    return ImageGrab.grab(), "full_screen"


def _history_block() -> str:
    if not _VISION_HISTORY:
        return "(no recent screen analysis history)"
    lines = []
    for item in list(_VISION_HISTORY):
        lines.append(
            f"- {item['timestamp']} mode={item['mode']} size={item['size']} "
            f"q={item['question']} a={item['answer']}"
        )
    return "\n".join(lines)


async def screen_vision_tool(
    question: str,
    capture_mode: str = "active_window",
    region_size: int = 700,
    include_history: bool = True,
) -> str:
    global _LAST_CAPTURE_AT

    if not question.strip():
        return "error: question cannot be empty"

    now = time.monotonic()
    if now - _LAST_CAPTURE_AT < _COOLDOWN_SECONDS:
        wait_for = round(_COOLDOWN_SECONDS - (now - _LAST_CAPTURE_AT), 1)
        return f"error: vision cooldown active, retry in {wait_for}s"

    image, final_mode = _capture_image(capture_mode=capture_mode, region_size=region_size)
    _LAST_CAPTURE_AT = time.monotonic()

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    settings = get_settings()
    llm = LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a screen analysis assistant. Answer from the screenshot only. "
                "Be concise, call out uncertainty, and suggest a follow-up capture if needed."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Question: {question}\n"
                        f"Capture mode used: {final_mode}\n"
                        f"Recent history:\n{_history_block() if include_history else '(history disabled)'}"
                    ),
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        },
    ]

    response = await llm.call(messages=messages, tools=[])
    answer = (response.text or "No analysis returned.").strip()
    width, height = image.size
    _VISION_HISTORY.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": final_mode,
            "size": f"{width}x{height}",
            "question": question[:120],
            "answer": answer[:160],
        }
    )
    return answer
