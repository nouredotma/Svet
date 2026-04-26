"""Earcon (audio feedback) sounds for Dexter state transitions.

All sounds are generated programmatically with numpy — no external audio files needed.
Each function is non-blocking: audio plays in a background thread via sounddevice.
"""
from __future__ import annotations

import numpy as np
import sounddevice as sd

_SR = 44100  # sample rate


def _tone(freq: float, dur: float, vol: float = 0.3) -> np.ndarray:
    t = np.linspace(0, dur, int(_SR * dur), endpoint=False)
    fade = min(int(_SR * 0.015), len(t) // 4)
    env = np.ones_like(t)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return (vol * np.sin(2 * np.pi * freq * t) * env).astype(np.float32)


def _gap(ms: float = 30) -> np.ndarray:
    return np.zeros(int(_SR * ms / 1000), dtype=np.float32)


def _play(audio: np.ndarray) -> None:
    try:
        sd.play(audio, _SR, blocking=False)
    except Exception:
        pass


# ---- Public API ----

def chime_activation(vol: float = 0.3) -> None:
    """Rising two-note chime — wake word or hotkey detected."""
    _play(np.concatenate([_tone(880, 0.08, vol), _gap(), _tone(1320, 0.10, vol)]))


def chime_transcribed(vol: float = 0.2) -> None:
    """Subtle click — transcription done, thinking starts."""
    _play(_tone(1000, 0.05, vol))


def chime_response(vol: float = 0.25) -> None:
    """Soft tone — response is starting."""
    _play(_tone(660, 0.10, vol))


def chime_idle(vol: float = 0.15) -> None:
    """Gentle descending tone — conversation mode ending, going idle."""
    _play(np.concatenate([_tone(660, 0.08, vol), _gap(20), _tone(440, 0.12, vol * 0.7)]))


def chime_error(vol: float = 0.2) -> None:
    """Low buzz — something went wrong."""
    t = np.linspace(0, 0.15, int(_SR * 0.15), endpoint=False)
    audio = (vol * np.sin(2 * np.pi * 220 * t) * np.sin(2 * np.pi * 15 * t)).astype(np.float32)
    _play(audio)
