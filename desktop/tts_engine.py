from __future__ import annotations

import asyncio
import io
import logging
import os
import threading

import edge_tts
import sounddevice as sd
import soundfile as sf

from desktop.config import DexterConfig

log = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, config: DexterConfig) -> None:
        self._config = config
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._play_thread: threading.Thread | None = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        await self.stop()
        self._is_speaking = True
        self._stop_event.clear()
        try:
            # Stream audio into an in-memory buffer instead of writing to disk
            buf = io.BytesIO()
            communicate = edge_tts.Communicate(
                text=text,
                voice=self._config.TTS_VOICE,
                rate=self._config.TTS_RATE,
            )
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
                if self._stop_event.is_set():
                    return

            if buf.tell() == 0:
                log.warning("TTS produced no audio data")
                return

            buf.seek(0)
            await asyncio.to_thread(self._play_audio_buffer, buf)
        except Exception:
            log.exception("TTS failed, trying fallback")
            await asyncio.to_thread(self._fallback_tts, text)
        finally:
            self._is_speaking = False

    async def stop(self) -> None:
        self._stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)
        self._is_speaking = False

    def _play_audio_buffer(self, buf: io.BytesIO) -> None:
        """Play audio from an in-memory buffer (no temp file needed)."""
        try:
            data, samplerate = sf.read(buf, dtype="float32")
            sd.play(data, samplerate)
            sd.wait()
        except Exception:
            log.exception("Audio playback failed")

    def _fallback_tts(self, text: str) -> None:
        command = f'powershell -Command "Add-Type -AssemblyName System.Speech; ' \
            f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text.replace(chr(39), " ")}\')"'
        os.system(command)
