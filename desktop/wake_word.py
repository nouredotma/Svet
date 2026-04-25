from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

from desktop.stt_engine import STTEngine

log = logging.getLogger(__name__)

SUPPORTED_WAKE_MODELS = {"alexa", "hey_mycroft", "hey_jarvis", "hey_rhasspy", "timer", "weather"}


class WakeWordDetector:
    def __init__(
        self,
        wake_word: str,
        on_detected: Callable[[], None],
        stt_engine: STTEngine | None = None,
        sensitivity: float = 0.5,
    ) -> None:
        self._wake_word = wake_word.strip().lower()
        self._on_detected = on_detected
        self._sensitivity = sensitivity
        self._running = False
        self._thread: threading.Thread | None = None
        self._stt_engine = stt_engine
        self._cooldown_seconds = 1.5
        self._use_transcribe = False
        self._model: Model | None = None

        if self._wake_word in SUPPORTED_WAKE_MODELS:
            self._model = Model(wakeword_models=[self._wake_word])
        elif self._stt_engine is not None:
            self._use_transcribe = True
        else:
            self._model = Model()

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Wake word detector started (word=%s, transcribe=%s)", self._wake_word, self._use_transcribe)

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        log.info("Wake word detector stopped")

    def _listen_loop(self) -> None:
        if self._use_transcribe:
            self._listen_for_phrase()
        else:
            self._listen_with_model()

    def _listen_with_model(self) -> None:
        samplerate = 16000
        blocksize = 1280
        threshold = self._sensitivity
        try:
            with sd.InputStream(samplerate=samplerate, channels=1, blocksize=blocksize, dtype="int16") as stream:
                while self._running:
                    frames, _overflow = stream.read(blocksize)
                    chunk = np.squeeze(frames).astype(np.int16)
                    scores = self._model.predict(chunk) if self._model else {}
                    best = max((float(v) for v in scores.values()), default=0.0)
                    if best >= threshold:
                        log.info("Wake word model detected (score=%.3f)", best)
                        self._on_detected()
                        time.sleep(self._cooldown_seconds)
        except Exception:
            log.exception("Wake word model listener crashed")
            self._running = False

    def _listen_for_phrase(self) -> None:
        if not self._stt_engine:
            log.error("No STT engine for phrase-based wake word detection")
            self._running = False
            return

        phrase_duration = 1.5
        while self._running:
            try:
                transcript = self._stt_engine._record_and_transcribe(phrase_duration, None)
                if transcript and not transcript.startswith("error:"):
                    if self._wake_word in transcript.lower():
                        log.info("Wake phrase detected in transcript: %s", transcript)
                        self._on_detected()
                        time.sleep(self._cooldown_seconds)
            except Exception:
                log.exception("Wake word phrase listener error")
                time.sleep(1.0)
