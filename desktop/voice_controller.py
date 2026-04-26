from __future__ import annotations

import asyncio
import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from desktop import earcon
from desktop.api_client import DexterAPIClient
from desktop.config import DexterConfig
from desktop.overlay import DexterOverlay, OverlayState
from desktop.stt_engine import STTEngine
from desktop.tts_engine import TTSEngine
from desktop.wake_word import WakeWordDetector
from desktop.websocket_client import TaskWebSocketClient

log = logging.getLogger(__name__)

_DISMISS_PHRASES = {"that's all", "thanks", "thank you", "stop", "never mind", "bye", "goodbye"}


class VoiceController(QObject):
    transcription_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    _wake_signal = pyqtSignal()
    _hotkey_signal = pyqtSignal()

    def __init__(self, config: DexterConfig, overlay: DexterOverlay, api_client: DexterAPIClient) -> None:
        super().__init__()
        self.config = config
        self.overlay = overlay
        self.api = api_client
        self.stt = STTEngine(config)
        self.tts = TTSEngine(config)
        self.ws = TaskWebSocketClient(config.DEXTER_API_URL)
        self.wake = WakeWordDetector(config.WAKE_WORD, self._wake_detected, self.stt, config.WAKE_WORD_SENSITIVITY)

        self._conversation_history: list[dict[str, str]] = []
        self._in_conversation = False
        self._busy = False  # Prevent overlapping interactions

        self._wake_signal.connect(self._on_activation)
        self._hotkey_signal.connect(self._on_activation)

    # ---- Activation (wake word or hotkey) ----

    async def start_listening(self) -> str:
        self.overlay.set_state(OverlayState.LISTENING)
        text = await self.stt.listen_and_transcribe()
        self.transcription_ready.emit(text)
        self.overlay.show_transcript(text or "(no speech detected)")
        return text

    def enable_wake_word(self) -> None:
        self.wake.start()

    def disable_wake_word(self) -> None:
        self.wake.stop()

    def _wake_detected(self) -> None:
        """Called from background thread — only emit signal."""
        self._wake_signal.emit()

    def on_hotkey(self) -> None:
        """Called when global hotkey is pressed — emit signal."""
        self._hotkey_signal.emit()

    def _on_activation(self) -> None:
        """Runs on main/GUI thread — safe for Qt + asyncio."""
        if self._busy:
            return
        log.info("Activation triggered — starting voice flow")
        if self.config.ENABLE_EARCONS:
            earcon.chime_activation(self.config.EARCON_VOLUME)
        self.overlay.show_transcript("Listening...")
        asyncio.ensure_future(self._voice_flow())

    # ---- Main voice flow ----

    async def _voice_flow(self) -> None:
        """Full voice interaction cycle, with optional conversation follow-up."""
        if self._busy:
            return
        self._busy = True

        try:
            text = await self.start_listening()
            if not text or text.startswith("error:"):
                self.overlay.set_state(OverlayState.IDLE)
                return

            # Check for dismissal phrases
            if text.strip().lower() in _DISMISS_PHRASES:
                log.info("Dismiss phrase detected: %s", text)
                self._end_conversation()
                return

            await self._process_and_respond(text)

            # ---- Conversation follow-up loop ----
            if self.config.ENABLE_CONVERSATION_MODE:
                while True:
                    follow_up = await self._wait_for_follow_up()
                    if not follow_up:
                        break
                    if follow_up.strip().lower() in _DISMISS_PHRASES:
                        log.info("Dismiss phrase in follow-up: %s", follow_up)
                        break
                    await self._process_and_respond(follow_up)

            self._end_conversation()
        except Exception:
            log.exception("Voice flow error")
            if self.config.ENABLE_EARCONS:
                earcon.chime_error(self.config.EARCON_VOLUME)
            self.overlay.set_state(OverlayState.IDLE)
        finally:
            self._busy = False

    async def _process_and_respond(self, prompt: str) -> None:
        """Submit prompt, wait for response, speak it."""
        if self.config.ENABLE_EARCONS:
            earcon.chime_transcribed(self.config.EARCON_VOLUME)

        self.overlay.set_state(OverlayState.THINKING)

        # Build contextual prompt for multi-turn conversation
        full_prompt = self._build_contextual_prompt(prompt)

        task = await self.api.submit_task(full_prompt)
        if not task or not task.get("id"):
            self.error_occurred.emit("Failed to submit task.")
            if self.config.ENABLE_EARCONS:
                earcon.chime_error(self.config.EARCON_VOLUME)
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
        try:
            await asyncio.wait_for(done_event.wait(), timeout=120)
        except asyncio.TimeoutError:
            log.warning("WebSocket timed out for task %s, falling back to HTTP", task_id)

        if not result_text:
            details = await self.api.get_task(task_id)
            if details:
                result_text = str(details.get("result") or details.get("error") or "")

        # Save to conversation history
        self._conversation_history.append({"role": "user", "content": prompt})
        self._conversation_history.append({"role": "assistant", "content": result_text})
        # Keep history manageable
        if len(self._conversation_history) > 10:
            self._conversation_history = self._conversation_history[-10:]

        self.overlay.show_transcript(result_text or "Task completed.")
        self.response_ready.emit(result_text)

        if self.config.AUTO_SPEAK_RESPONSES and result_text:
            if self.config.ENABLE_EARCONS:
                earcon.chime_response(self.config.EARCON_VOLUME)
            self.overlay.set_state(OverlayState.SPEAKING)
            await self.tts.speak(result_text)

        self.overlay.clear_transcript()
        await self.ws.disconnect()

    async def _wait_for_follow_up(self) -> str:
        """Enter conversation mode and wait for a follow-up utterance.

        Returns the transcribed text, or empty string on timeout.
        """
        self._in_conversation = True
        self.overlay.set_state(OverlayState.CONVERSATION)
        log.info("Conversation mode: waiting %ds for follow-up", self.config.CONVERSATION_TIMEOUT)

        text = await self.stt.listen_and_transcribe(
            duration_seconds=self.config.CONVERSATION_TIMEOUT + 5,
            conversation_timeout=float(self.config.CONVERSATION_TIMEOUT),
        )

        if not text or text.startswith("error:"):
            log.info("No follow-up detected, ending conversation")
            return ""

        log.info("Follow-up detected: %s", text[:50])
        if self.config.ENABLE_EARCONS:
            earcon.chime_activation(self.config.EARCON_VOLUME)
        self.overlay.show_transcript(text)
        self.transcription_ready.emit(text)
        return text

    def _end_conversation(self) -> None:
        """Clean up conversation state and go idle."""
        self._in_conversation = False
        self._conversation_history.clear()
        if self.config.ENABLE_EARCONS:
            earcon.chime_idle(self.config.EARCON_VOLUME)
        self.overlay.clear_transcript()
        self.overlay.set_state(OverlayState.IDLE)
        log.info("Conversation ended")

    def _build_contextual_prompt(self, prompt: str) -> str:
        """Prepend conversation history for multi-turn context."""
        if not self._conversation_history:
            return prompt

        lines = []
        for msg in self._conversation_history[-6:]:
            role = "User" if msg["role"] == "user" else "Dexter"
            lines.append(f"{role}: {msg['content']}")
        lines.append(f"User: {prompt}")

        return (
            "This is a continued conversation. Here is the context:\n\n"
            + "\n".join(lines)
            + "\n\nRespond to the latest User message considering the conversation above."
        )
