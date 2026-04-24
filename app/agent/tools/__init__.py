from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.agent.tools.browser import browser_tool
from app.agent.tools.calendar import calendar_tool
from app.agent.tools.desktop_control import desktop_control_tool
from app.agent.tools.email import read_email_tool, send_email_tool
from app.agent.tools.files import read_file_tool, write_file_tool
from app.agent.tools.http_request import http_request_tool
from app.agent.tools.screen_vision import screen_vision_tool
from app.agent.tools.search import web_search_tool
from app.agent.tools.shell import shell_tool
from app.agent.tools.screenshot import screenshot_tool
from app.agent.tools.system_info import system_info_tool

TOOLS_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "browser_tool": browser_tool,
    "calendar_tool": calendar_tool,
    "web_search_tool": web_search_tool,
    "read_file_tool": read_file_tool,
    "write_file_tool": write_file_tool,
    "send_email_tool": send_email_tool,
    "read_email_tool": read_email_tool,
    "http_request_tool": http_request_tool,
    "shell_tool": shell_tool,
    "screenshot_tool": screenshot_tool,
    "system_info_tool": system_info_tool,
    "desktop_control_tool": desktop_control_tool,
    "screen_vision_tool": screen_vision_tool,
}


def get_tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "browser_tool",
            "description": "Use a headless Chromium browser to navigate/extract/modify pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["navigate", "click", "fill", "extract", "wait_for", "screenshot"],
                        "description": "navigate loads URL; click/fill/extract/wait_for/screenshot operate on a persisted page session",
                    },
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["url", "action"],
            },
        },
        {
            "name": "calendar_tool",
            "description": (
                "Date/time helpers: now, parse, to_timezone, add, diff_minutes, weekday, list_timezones. "
                "Use IANA timezone names (e.g. Europe/Berlin). datetime_str uses ISO-8601 or common date formats."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "now",
                            "parse",
                            "to_timezone",
                            "add",
                            "diff_minutes",
                            "weekday",
                            "list_timezones",
                            "calendar_read",
                            "calendar_create",
                            "calendar_update",
                            "calendar_delete",
                        ],
                    },
                    "datetime_str": {"type": "string"},
                    "datetime_str_b": {"type": "string"},
                    "text": {"type": "string"},
                    "timezone": {"type": "string", "default": "UTC"},
                    "days": {"type": "integer", "default": 0},
                    "hours": {"type": "integer", "default": 0},
                    "minutes": {"type": "integer", "default": 0},
                    "pattern": {"type": "string", "default": "%Y-%m-%d %H:%M:%S %Z"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "web_search_tool",
            "description": "Search the public web (DuckDuckGo instant answers by default).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "read_file_tool",
            "description": "Read a UTF-8 text file under the configured agent workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "write_file_tool",
            "description": "Write or append UTF-8 text under the configured agent workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["w", "a"], "default": "w"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "send_email_tool",
            "description": "Send email via SMTP using server-configured credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "read_email_tool",
            "description": "Read recent inbox emails via IMAP using server-configured credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 5},
                },
            },
        },
        {
            "name": "http_request_tool",
            "description": "Perform an HTTP request with retries and safety checks against private/internal hosts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "shell_tool",
            "description": "Execute a shell command with safety filters and environment-gated access.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "screenshot_tool",
            "description": "Capture a full-screen screenshot and save it as PNG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_path": {"type": "string"},
                },
            },
        },
        {
            "name": "system_info_tool",
            "description": "Read system metrics such as CPU, RAM, disk, processes, battery, and network usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["cpu", "ram", "disk", "processes", "battery", "network", "all"],
                        "default": "all",
                    }
                },
            },
        },
        {
            "name": "desktop_control_tool",
            "description": "Perform desktop actions such as mouse movement/clicks, typing, and key presses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "move",
                            "click",
                            "right_click",
                            "double_click",
                            "type",
                            "press",
                            "scroll",
                            "open_app",
                        ],
                    },
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "text": {"type": "string"},
                    "key": {"type": "string"},
                    "app_name": {"type": "string"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "screen_vision_tool",
            "description": "Analyze the screen with smart capture modes (active window/cursor region/full screen).",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "capture_mode": {
                        "type": "string",
                        "enum": ["active_window", "cursor_region", "full_screen"],
                        "default": "active_window",
                    },
                    "region_size": {
                        "type": "integer",
                        "default": 700,
                        "description": "Used for cursor_region capture square size in pixels.",
                    },
                    "include_history": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include lightweight recent vision context for better follow-up answers.",
                    },
                },
                "required": ["question"],
            },
        },
    ]
