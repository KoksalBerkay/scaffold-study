"""Scaffold as a desktop app: the same backend, shown in a native window (pywebview).

    ./run.sh --app
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
import webview

sys.path.insert(0, str(Path(__file__).parent))
from app.config import WORKSPACE  # noqa: E402

PORT = 8765
ICON = Path(__file__).resolve().parents[1] / "assets" / "icon-1024.png"


def brand_macos_app():
    """Show 'Scaffold' with its icon in the Dock, menu bar and app switcher instead of 'python3.12'."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle, NSProcessInfo
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = "Scaffold"
        info["CFBundleDisplayName"] = "Scaffold"
        NSProcessInfo.processInfo().setProcessName_("Scaffold")
        app = NSApplication.sharedApplication()
        if ICON.exists():
            app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(ICON)))
    except Exception as e:  # cosmetic only, never block startup
        print("branding skipped:", e)


def scaffold_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/settings", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def start_server() -> tuple[int, uvicorn.Server | None]:
    if scaffold_running(PORT):  # the web version is already running: share it
        return PORT, None
    port = PORT
    while not port_free(port):
        port += 1
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                           timeout_graceful_shutdown=2))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    return port, server


def main():
    brand_macos_app()
    port, server = start_server()
    webview.create_window("Scaffold", f"http://127.0.0.1:{port}/", width=1440, height=920, min_size=(900, 600),
                          background_color="#0E1015", text_select=True)
    storage = WORKSPACE / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    # private_mode=False keeps localStorage (theme choice) between launches
    webview.start(private_mode=False, storage_path=str(storage))
    if server:
        server.should_exit = True


if __name__ == "__main__":
    main()
