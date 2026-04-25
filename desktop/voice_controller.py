from __future__ import annotations

import asyncio

from PyQt6.QtCore import QObject, pyqtSignal

from desktop.api_client import DexterAPIClient
from desktop.config import DexterConfig
from desktop.overlay import DexterOverlay, OverlayState
from desktop.stt_engine import STTEngine
from desktop.tts_engine import TTSEngine
from desktop.wake_word import WakeWordDetector
from desktop.websocket_client import TaskWebSocketClient


class VoiceController(QObject):
    transcription_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: DexterConfig, overlay: DexterOverlay, api_client: DexterAPIClient) -> None:
        super().__init__()
        self.config = config
        self.overlay = overlay
        self.api = api_client
        self.stt = STTEngine(config)
        self.tts = TTSEngine(config)
        self.ws = TaskWebSocketClient(config.DEXTER_API_URL)
        self.wake = WakeWordDetector(config.WAKE_WORD, self._wake_detected, self.stt, config.WAKE_WORD_SENSITIVITY)

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

        async def on_update(data: dict) -> None:
            nonlocal result_text
            status = str(data.get("status", ""))
            if data.get("result"):
                result_text = str(data.get("result"))
            if status in {"failed", "cancelled"} and data.get("error"):
                self.error_occurred.emit(str(data["error"]))

        await self.ws.connect(task_id, on_update)
        while True:
            details = await self.api.get_task(task_id)
            if not details:
                break
            status = str(details.get("status", "")).lower()
            if status in {"done", "failed", "cancelled"}:
                result_text = str(details.get("result") or result_text or details.get("error") or "")
                break
            await asyncio.sleep(0.8)

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
        self.overlay.show_transcript("Wake word detected")
        asyncio.get_event_loop().create_task(self._wake_flow())

    async def _wake_flow(self) -> None:
        text = await self.start_listening()
        await self.process_and_respond(text)
