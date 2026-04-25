from __future__ import annotations

import asyncio
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from desktop.api_client import DexterAPIClient
from desktop.config import DexterConfig
from desktop.overlay import DexterOverlay, OverlayState
from desktop.stt_engine import STTEngine
from desktop.tts_engine import TTSEngine
from desktop.wake_word import WakeWordDetector
from desktop.websocket_client import TaskWebSocketClient

log = logging.getLogger(__name__)


class VoiceController(QObject):
    transcription_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    _wake_signal = pyqtSignal()  # Thread-safe wake word notification

    def __init__(self, config: DexterConfig, overlay: DexterOverlay, api_client: DexterAPIClient) -> None:
        super().__init__()
        self.config = config
        self.overlay = overlay
        self.api = api_client
        self.stt = STTEngine(config)
        self.tts = TTSEngine(config)
        self.ws = TaskWebSocketClient(config.DEXTER_API_URL)
        self.wake = WakeWordDetector(config.WAKE_WORD, self._wake_detected, self.stt, config.WAKE_WORD_SENSITIVITY)

        # Connect the thread-safe signal to the handler on the main thread
        self._wake_signal.connect(self._on_wake_signal)

    async def start_listening(self) -> str:
        self.overlay.set_state(OverlayState.LISTENING)
        text = await self.stt.listen_and_transcribe()
        self.transcription_ready.emit(text)
        self.overlay.show_transcript(text or "(no speech detected)")
        return text

    async def process_and_respond(self, prompt: str) -> None:
        if not prompt or prompt.startswith("error:"):
            self.overlay.set_state(OverlayState.IDLE)
            return
        self.overlay.set_state(OverlayState.THINKING)
        task = await self.api.submit_task(prompt)
        if not task or not task.get("id"):
            self.error_occurred.emit("Failed to submit task.")
            self.overlay.set_state(OverlayState.IDLE)
            return
        task_id = str(task["id"])
        result_text = ""
        done_event = asyncio.Event()

        async def on_update(data: dict) -> None:
            nonlocal result_text
            status = str(data.get("status", ""))
            if data.get("result"):
                result_text = str(data.get("result"))
            if status in {"failed", "cancelled"} and data.get("error"):
                self.error_occurred.emit(str(data["error"]))
            if status.lower() in {"done", "failed", "cancelled"}:
                done_event.set()

        await self.ws.connect(task_id, on_update)

        # Wait for WebSocket to deliver terminal status, with timeout fallback
        try:
            await asyncio.wait_for(done_event.wait(), timeout=120)
        except asyncio.TimeoutError:
            log.warning("WebSocket timed out for task %s, falling back to HTTP", task_id)

        # If WebSocket didn't deliver result, fall back to HTTP
        if not result_text:
            details = await self.api.get_task(task_id)
            if details:
                result_text = str(details.get("result") or details.get("error") or "")

        self.overlay.show_transcript(result_text or "Task completed.")
        self.response_ready.emit(result_text)
        if self.config.AUTO_SPEAK_RESPONSES and result_text:
            self.overlay.set_state(OverlayState.SPEAKING)
            await self.tts.speak(result_text)
        self.overlay.clear_transcript()
        self.overlay.set_state(OverlayState.IDLE)
        await self.ws.disconnect()

    def enable_wake_word(self) -> None:
        self.wake.start()

    def disable_wake_word(self) -> None:
        self.wake.stop()

    def _wake_detected(self) -> None:
        """Called from the background wake-word thread. Only emit a signal — never
        touch Qt widgets or the asyncio event loop directly from here."""
        self._wake_signal.emit()

    def _on_wake_signal(self) -> None:
        """Runs on the main/GUI thread via Qt signal queue — safe to use Qt and asyncio."""
        log.info("Wake word detected — starting voice flow")
        self.overlay.show_transcript("Wake word detected")
        asyncio.ensure_future(self._wake_flow())

    async def _wake_flow(self) -> None:
        text = await self.start_listening()
        await self.process_and_respond(text)
