from __future__ import annotations

import logging

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

# Map config string names → pynput Key objects
_KEY_MAP = {
    "scroll_lock": keyboard.Key.scroll_lock,
    "pause": keyboard.Key.pause,
    "insert": keyboard.Key.insert,
    "print_screen": keyboard.Key.print_screen,
    "f1": keyboard.Key.f1, "f2": keyboard.Key.f2, "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4, "f5": keyboard.Key.f5, "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7, "f8": keyboard.Key.f8, "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10, "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
}


class HotkeyListener(QObject):
    """System-wide global hotkey listener.

    Supports single keys (e.g. ``scroll_lock``, ``pause``, ``f8``) and
    pynput combo strings (e.g. ``<ctrl>+<shift>+d``).
    """

    activated = pyqtSignal()

    def __init__(self, hotkey_str: str = "scroll_lock") -> None:
        super().__init__()
        self._hotkey_str = hotkey_str.strip().lower()
        self._listener: keyboard.Listener | None = None
        self._global_hotkeys: keyboard.GlobalHotKeys | None = None

        # Determine if this is a single key or a combo
        self._single_key = _KEY_MAP.get(self._hotkey_str)

    def start(self) -> None:
        if self._single_key:
            # Single key — use a Listener for maximum compatibility
            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.daemon = True
            self._listener.start()
        else:
            # Combo string (pynput format, e.g. "<ctrl>+<shift>+d")
            combo = self._hotkey_str if "<" in self._hotkey_str else f"<{self._hotkey_str}>"
            self._global_hotkeys = keyboard.GlobalHotKeys({combo: self._on_activate})
            self._global_hotkeys.daemon = True
            self._global_hotkeys.start()
        log.info("Hotkey listener started: %s", self._hotkey_str)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._global_hotkeys:
            self._global_hotkeys.stop()
            self._global_hotkeys = None

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Single-key listener callback."""
        try:
            if key == self._single_key:
                self._on_activate()
        except Exception:
            pass

    def _on_activate(self) -> None:
        """Called from pynput thread — pyqtSignal.emit() is thread-safe."""
        self.activated.emit()
