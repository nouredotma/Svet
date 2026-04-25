from __future__ import annotations

import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


@dataclass
class DexterConfig:
    DEXTER_API_URL: str = os.getenv("DEXTER_API_URL", "http://localhost:8000")
    WAKE_WORD: str = os.getenv("WAKE_WORD", "hi dexter")
    WAKE_WORD_SENSITIVITY: float = _to_float(os.getenv("WAKE_WORD_SENSITIVITY"), 0.5)
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")
    GLOW_COLOR: str = os.getenv("GLOW_COLOR", "#FF4500")
    GLOW_OPACITY: int = _to_int(os.getenv("GLOW_OPACITY"), 180)
    GLOW_WIDTH: int = _to_int(os.getenv("GLOW_WIDTH"), 40)
    TRANSCRIPT_DURATION: int = _to_int(os.getenv("TRANSCRIPT_DURATION"), 6)
    TRANSCRIPT_FONT_SIZE: int = _to_int(os.getenv("TRANSCRIPT_FONT_SIZE"), 14)
    POLL_INTERVAL_MS: int = _to_int(os.getenv("POLL_INTERVAL_MS"), 1000)
    AUTO_SPEAK_RESPONSES: bool = _to_bool(os.getenv("AUTO_SPEAK_RESPONSES"), True)

