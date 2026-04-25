from __future__ import annotations

import asyncio
import os
import re
import subprocess

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# Patterns that should never be launched via open_app
_BLOCKED_APP_PATTERNS = [
    r"\brm\b",
    r"\brmdir\b",
    r"\bdel\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bcurl\s.*\|\s*bash",
    r"\bwget\s.*\|\s*bash",
]

# Patterns where we warn the LLM to ask the user first
_CONFIRM_APP_PATTERNS = [
    r"\bcmd\b.*(/c|/k)",       # cmd with inline commands
    r"\bpowershell\b.*-c",     # powershell with inline commands
    r"\btaskkill\b",
    r"\bnet\s+stop\b",
    r"\bsc\s+delete\b",
    r"\breg\s+(add|delete)\b",
    r"\bregedit\b",
]


async def desktop_control_tool(
    action: str,
    x: int | None = None,
    y: int | None = None,
    text: str | None = None,
    key: str | None = None,
    app_name: str | None = None,
) -> str:
    if os.getenv("ENABLE_DESKTOP_CONTROL", "false").lower() != "true":
        raise RuntimeError("desktop_control_tool is disabled. Set ENABLE_DESKTOP_CONTROL=true to enable it.")

    action_norm = action.lower().strip()
    await asyncio.sleep(0.1)

    if action_norm == "move":
        if x is None or y is None:
            return "error: x and y are required for move"
        pyautogui.moveTo(x, y)
        return f"moved mouse to ({x}, {y})"

    if action_norm == "click":
        pyautogui.click(x=x, y=y)
        return f"clicked at ({x}, {y})" if x is not None and y is not None else "clicked current position"

    if action_norm == "right_click":
        pyautogui.rightClick(x=x, y=y)
        return f"right-clicked at ({x}, {y})" if x is not None and y is not None else "right-clicked current position"

    if action_norm == "double_click":
        pyautogui.doubleClick(x=x, y=y)
        return f"double-clicked at ({x}, {y})" if x is not None and y is not None else "double-clicked current position"

    if action_norm == "type":
        if text is None:
            return "error: text is required for type"
        pyautogui.write(text)
        return f"typed text ({len(text)} chars)"

    if action_norm == "press":
        if key is None:
            return "error: key is required for press"
        pyautogui.press(key)
        return f"pressed key '{key}'"

    if action_norm == "scroll":
        amount = int(text) if text is not None else 0
        pyautogui.scroll(amount)
        return f"scrolled {amount}"

    if action_norm == "open_app":
        if not app_name:
            return "error: app_name is required for open_app"

        app_lower = app_name.strip().lower()

        # Hard block — never allow
        for pattern in _BLOCKED_APP_PATTERNS:
            if re.search(pattern, app_lower):
                return (
                    f"error: BLOCKED — this app/command matches a forbidden destructive pattern. "
                    f"Cannot be launched."
                )

        # Soft block — needs user confirmation
        for pattern in _CONFIRM_APP_PATTERNS:
            if re.search(pattern, app_lower):
                return (
                    f"⚠️ CONFIRMATION REQUIRED: Opening this app/command may be destructive.\n"
                    f"App: {app_name}\n\n"
                    f"You MUST stop here and tell the user exactly what you want to open and WHY, "
                    f"then wait for their explicit approval. "
                    f"Do NOT retry without the user's permission."
                )

        subprocess.Popen(app_name, shell=True)
        return f"opened app '{app_name}'"

    return "error: unknown action. use move|click|right_click|double_click|type|press|scroll|open_app"
