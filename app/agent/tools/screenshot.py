from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import gettempdir

from PIL import ImageGrab

from app.config import get_settings


def _safe_screenshot_path(save_path: str | None) -> Path:
    """Resolve save path, confined under AGENT_FILES_ROOT if a relative path is given."""
    settings = get_settings()
    root = Path(settings.agent_files_root).resolve()

    if save_path:
        candidate = Path(save_path).expanduser().resolve()
        # If the path is outside the agent files root, force it under root.
        try:
            candidate.relative_to(root)
        except ValueError:
            candidate = (root / Path(save_path).name).resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = (root / f"dexter_screenshot_{ts}.png").resolve()

    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


async def screenshot_tool(save_path: str | None = None) -> str:
    image = ImageGrab.grab()
    output = _safe_screenshot_path(save_path)
    image.save(output, format="PNG")
    width, height = image.size
    return f"saved: {output} (width={width}, height={height})"
