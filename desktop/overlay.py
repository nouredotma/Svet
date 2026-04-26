from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from desktop.config import DexterConfig


class OverlayState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CONVERSATION = "conversation"


class GlowBorder(QWidget):
    """Renders a soft, diffuse glow along each screen edge (no hard border)."""

    def __init__(self, config: DexterConfig, parent: QWidget) -> None:
        super().__init__(parent)
        self._config = config
        self._opacity = 0
        self._current_color: str = config.GLOW_COLOR
        self._anim = QPropertyAnimation(self, b"glowOpacity")
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _color_for_state(self, state: OverlayState) -> str:
        return {
            OverlayState.LISTENING: self._config.GLOW_COLOR_LISTENING,
            OverlayState.THINKING: self._config.GLOW_COLOR_THINKING,
            OverlayState.SPEAKING: self._config.GLOW_COLOR_SPEAKING,
            OverlayState.CONVERSATION: self._config.GLOW_COLOR_CONVERSATION,
        }.get(state, self._config.GLOW_COLOR)

    def get_opacity(self) -> int:
        return self._opacity

    def set_opacity(self, value: int) -> None:
        self._opacity = max(0, min(255, value))
        self.update()

    glowOpacity = pyqtProperty(int, get_opacity, set_opacity)

    def set_state(self, state: OverlayState) -> None:
        self._anim.stop()
        self._current_color = self._color_for_state(state)

        if state == OverlayState.IDLE:
            self._opacity = 0
            self.update()
            return
        if state == OverlayState.SPEAKING:
            self._opacity = self._config.GLOW_OPACITY
            self.update()
            return
        if state == OverlayState.CONVERSATION:
            # Very slow, subtle pulse for "still listening" feel
            self._anim.setStartValue(30)
            self._anim.setEndValue(int(self._config.GLOW_OPACITY * 0.5))
            self._anim.setDuration(2000)
            self._anim.setLoopCount(-1)
            self._anim.start()
            return

        # LISTENING / THINKING
        self._anim.setStartValue(40 if state == OverlayState.LISTENING else 70)
        self._anim.setEndValue(self._config.GLOW_OPACITY)
        self._anim.setDuration(1200 if state == OverlayState.LISTENING else 500)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._opacity <= 0:
            return

        w = self.width()
        h = self.height()
        glow_thickness = self._config.GLOW_WIDTH

        base_color = QColor(self._current_color)
        base_color.setAlpha(self._opacity)
        transparent = QColor(self._current_color)
        transparent.setAlpha(0)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        # --- Top edge glow (gradient goes downward) ---
        grad_top = QLinearGradient(0, 0, 0, glow_thickness)
        grad_top.setColorAt(0.0, base_color)
        grad_top.setColorAt(1.0, transparent)
        painter.setBrush(grad_top)
        painter.drawRect(0, 0, w, glow_thickness)

        # --- Bottom edge glow (gradient goes upward) ---
        grad_bottom = QLinearGradient(0, h, 0, h - glow_thickness)
        grad_bottom.setColorAt(0.0, base_color)
        grad_bottom.setColorAt(1.0, transparent)
        painter.setBrush(grad_bottom)
        painter.drawRect(0, h - glow_thickness, w, glow_thickness)

        # --- Left edge glow (gradient goes rightward) ---
        grad_left = QLinearGradient(0, 0, glow_thickness, 0)
        grad_left.setColorAt(0.0, base_color)
        grad_left.setColorAt(1.0, transparent)
        painter.setBrush(grad_left)
        painter.drawRect(0, 0, glow_thickness, h)

        # --- Right edge glow (gradient goes leftward) ---
        grad_right = QLinearGradient(w, 0, w - glow_thickness, 0)
        grad_right.setColorAt(0.0, base_color)
        grad_right.setColorAt(1.0, transparent)
        painter.setBrush(grad_right)
        painter.drawRect(w - glow_thickness, 0, glow_thickness, h)

        painter.end()


class DexterOverlay(QWidget):
    def __init__(self, config: DexterConfig) -> None:
        super().__init__()
        self._config = config
        self._state = OverlayState.IDLE

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

        self._glow = GlowBorder(config, self)
        self._glow.setGeometry(self.rect())

        self._transcript = QLabel("", self)
        self._transcript.setWordWrap(True)
        self._transcript.setStyleSheet("background-color: rgba(0, 0, 0, 190); color: white; border-radius: 10px; padding: 12px;")
        self._transcript.setFont(QFont("Segoe UI", config.TRANSCRIPT_FONT_SIZE))
        self._transcript.hide()

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self.clear_transcript)

    def resizeEvent(self, _event) -> None:  # noqa: N802
        self._glow.setGeometry(self.rect())
        w, h = 460, 120
        self._transcript.setGeometry(QRect(self.width() - w - 32, self.height() - h - 48, w, h))

    def set_state(self, state: OverlayState) -> None:
        self._state = state
        self._glow.set_state(state)

    def show_transcript(self, text: str) -> None:
        self._transcript.setText(text)
        self._transcript.show()
        self._fade_timer.start(max(1000, self._config.TRANSCRIPT_DURATION * 1000))

    def clear_transcript(self) -> None:
        self._transcript.clear()
        self._transcript.hide()
