from __future__ import annotations

import os
import re
import subprocess

# -------------------------------------------------------------------
# ABSOLUTELY BLOCKED — these are never allowed, even with confirmation.
# -------------------------------------------------------------------
BLOCKED_COMMANDS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "rmdir /s /q c:\\",
    "format c:",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "curl | bash",
    "wget | bash",
    "curl | sh",
    "wget | sh",
    "> /dev/sda",
    "chmod -R 777 /",
    ":(){ :|:& };:",
]

# -------------------------------------------------------------------
# CONFIRMATION REQUIRED — the agent MUST stop and ask the user first.
# These patterns cover delete, remove, shutdown, reboot, uninstall,
# editing sensitive files, and other destructive operations.
# -------------------------------------------------------------------
CONFIRMATION_PATTERNS = [
    # File/directory deletion
    r"\brm\b",
    r"\brmdir\b",
    r"\bdel\b",
    r"\brd\b",
    r"\berase\b",
    r"\bremove-item\b",
    r"\bunlink\b",
    r"\bshred\b",
    r"\btrash\b",
    # System control
    r"\bshutdown\b",
    r"\breboot\b",
    r"\brestart-computer\b",
    r"\bstop-computer\b",
    r"\blogoff\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    # Package management (uninstall / remove)
    r"\bpip\s+uninstall\b",
    r"\bnpm\s+uninstall\b",
    r"\bapt\s+remove\b",
    r"\bapt-get\s+remove\b",
    r"\bapt\s+purge\b",
    r"\bchoco\s+uninstall\b",
    r"\bwinget\s+uninstall\b",
    r"\buninstall\b",
    # Disk / partition
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\bmkfs\b",
    # File overwrite / truncation
    r">\s*/",          # redirect overwriting root files
    r">\s*~",          # redirect overwriting home files
    r"\bmv\b.*\s+/",   # moving files into root-level paths
    r"\bcopy\b.*\s+c:\\windows",
    # Permission changes
    r"\bchmod\b",
    r"\bchown\b",
    r"\bicacls\b",
    r"\btakeown\b",
    # Registry editing
    r"\breg\s+delete\b",
    r"\breg\s+add\b",
    r"\bregedit\b",
    # Service control
    r"\bsc\s+delete\b",
    r"\bnet\s+stop\b",
    r"\bstop-service\b",
    # Kill processes
    r"\btaskkill\b",
    r"\bkill\b",
    r"\bpkill\b",
    # Git destructive
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-fd\b",
]


def _is_blocked(command: str) -> str | None:
    """Return the matched blocked pattern or None."""
    lowered = command.strip().lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in lowered:
            return blocked
    return None


def _needs_confirmation(command: str) -> str | None:
    """Return the matched confirmation pattern or None."""
    lowered = command.strip().lower()
    for pattern in CONFIRMATION_PATTERNS:
        if re.search(pattern, lowered):
            return pattern
    return None


async def shell_tool(command: str) -> str:
    if os.getenv("ENABLE_SHELL_TOOL", "false").lower() != "true":
        raise RuntimeError("shell_tool is disabled. Set ENABLE_SHELL_TOOL=true to enable it.")

    command_stripped = command.strip()
    if not command_stripped:
        return "error: command cannot be empty"

    # Hard block — never allowed
    blocked = _is_blocked(command_stripped)
    if blocked:
        return f"error: BLOCKED — this command matches a forbidden pattern ({blocked}). This cannot be executed."

    # Soft block — needs human approval before running
    needs_confirm = _needs_confirmation(command_stripped)
    if needs_confirm:
        return (
            f"⚠️ CONFIRMATION REQUIRED: This command is potentially destructive.\n"
            f"Command: {command_stripped}\n"
            f"Matched safety pattern: {needs_confirm}\n\n"
            f"You MUST stop here and tell the user exactly what you want to run and WHY, "
            f"then wait for their explicit approval in a follow-up message. "
            f"Do NOT retry this command or any variation of it without the user's permission."
        )

    try:
        completed = subprocess.run(
            command_stripped,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30 seconds"
    except Exception as exc:  # noqa: BLE001
        return f"error: failed to execute command: {exc}"

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        return stdout
    if stderr:
        return stderr
    return f"command finished with exit code {completed.returncode}"
