from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from desktop.config import DexterConfig

log = logging.getLogger(__name__)

# Voice Activity Detection parameters
_SILENCE_THRESHOLD = 0.015  # RMS energy below this = silence
_SILENCE_LIMIT = 1.5  # seconds of silence after speech to auto-stop
_MIN_RECORD_TIME = 0.8  # minimum recording time before checking silence
_CHUNK_DURATION = 0.1  # 100ms chunks for responsive VAD


class STTEngine:
    def __init__(self, config: DexterConfig) -> None:
        self._config = config
        self._is_listening = False
        self.__model: WhisperModel | None = None
        self._model_lock = threading.Lock()

    def _get_model(self) -> WhisperModel:
        """Lazy-load the Whisper model on first use (thread-safe)."""
        if self.__model is None:
            with self._model_lock:
                if self.__model is None:
                    log.info("Loading Whisper model '%s' (first use)...", self._config.WHISPER_MODEL)
                    self.__model = WhisperModel(
                        self._config.WHISPER_MODEL, device="cpu", compute_type="int8"
                    )
                    log.info("Whisper model loaded")
        return self.__model

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    async def listen_and_transcribe(
        self,
        duration_seconds: int = 10,
        on_audio_level: Callable[[float], None] | None = None,
    ) -> str:
        self._is_listening = True
        try:
            text = await asyncio.to_thread(
                self._record_and_transcribe,
                duration_seconds,
                on_audio_level,
            )
            return text
        except Exception as exc:  # noqa: BLE001
            log.exception("Microphone/transcription failed")
            return f"error: microphone/transcription failed: {exc}"
        finally:
            self._is_listening = False

    def _record_and_transcribe(
        self,
        max_duration: int | float,
        on_audio_level: Callable[[float], None] | None,
    ) -> str:
        samplerate = 16000
        chunk_samples = int(samplerate * _CHUNK_DURATION)

        if not sd.query_devices():
            return "error: no microphone detected"

        speech_started = False
        silence_elapsed = 0.0
        recorded: list[np.ndarray] = []
        total_time = 0.0

        try:
            with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32") as stream:
                while total_time < max_duration:
                    chunk, _overflow = stream.read(chunk_samples)
                    recorded.append(chunk.copy())

                    # Use float64 intermediate to avoid overflow in square
                    energy = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
                    if on_audio_level:
                        on_audio_level(energy)

                    total_time += _CHUNK_DURATION

                    # Don't check VAD until minimum recording time
                    if total_time < _MIN_RECORD_TIME:
                        continue

                    # Voice Activity Detection
                    if energy > _SILENCE_THRESHOLD:
                        speech_started = True
                        silence_elapsed = 0.0
                    elif speech_started:
                        silence_elapsed += _CHUNK_DURATION
                        if silence_elapsed >= _SILENCE_LIMIT:
                            log.debug("VAD: silence detected after %.1fs, stopping", total_time)
                            break
        except Exception:
            log.exception("Microphone recording error")
            if not recorded:
                return "error: microphone recording failed"

        if not recorded:
            return ""

        audio = np.concatenate(recorded, axis=0)
        mono = np.squeeze(audio)
        model = self._get_model()
        segments, _info = model.transcribe(mono, language="en")
        text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
        return text
