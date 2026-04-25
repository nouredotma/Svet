from __future__ import annotations

import asyncio
import signal
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow
from qasync import QEventLoop

from desktop.api_client import DexterAPIClient
from desktop.config import DexterConfig
from desktop.dashboard import DexterDashboard
from desktop.overlay import DexterOverlay, OverlayState
from desktop.system_tray import DexterTrayIcon
from desktop.voice_controller import VoiceController


async def _init_app(app: QApplication) -> tuple[DexterAPIClient, DexterTrayIcon]:
    config = DexterConfig()
    api = DexterAPIClient(config.DEXTER_API_URL)
    overlay = DexterOverlay(config)
    overlay.show()
    overlay.set_state(OverlayState.IDLE)

    dashboard = DexterDashboard(api, config)
    dashboard.closeEvent = lambda event: (event.ignore(), dashboard.hide())

    controller = VoiceController(config, overlay, api)
    controller.enable_wake_word()
    tray = DexterTrayIcon(api)
    tray.bind(dashboard, controller)
    tray.show()

    ok = await api.health_check()
    if not ok:
        tray.showMessage("Dexter", "Backend is not responding. Check if uvicorn is running.", tray.MessageIcon.Warning)
    await tray.update_backend_status()
    await dashboard.refresh_all()

    # Auto-open the dashboard on launch
    dashboard.show()
    dashboard.raise_()
    dashboard.activateWindow()

    return api, tray


def _apply_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QMainWindow, QMenu, QDialog { background-color: #1a1a1a; color: white; }
        QMainWindow QWidget { background-color: #1a1a1a; color: white; }
        QPushButton { background-color: #2a2a2a; border: 1px solid #444; padding: 6px; }
        QPushButton:hover { border: 1px solid #FF4500; }
        QLineEdit, QTextEdit, QListWidget, QTableWidget { background-color: #232323; color: white; border: 1px solid #333; }
        QMenu { background-color: #232323; color: white; }
        QMenu::item:selected { background-color: #FF4500; }
        """
    )


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _apply_theme(app)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, app.quit)
        except NotImplementedError:
            pass

    with loop:
        api, _tray = loop.run_until_complete(_init_app(app))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(api.close())


if __name__ == "__main__":
    main()
