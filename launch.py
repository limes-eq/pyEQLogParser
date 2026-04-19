"""Entry point for packaged distribution. Starts the Flask server, tray icon, and opens the browser."""
from __future__ import annotations
import os
import sys
import socket
import threading
import time
import webbrowser


def _resource_path(*parts: str) -> str:
    base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def _find_free_port(start: int = 5000) -> int:
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 5000-5099")


def main() -> None:
    if getattr(sys, "frozen", False):
        sys.path.insert(0, sys._MEIPASS)

    from web.app import app
    import pystray
    from PIL import Image

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    # Start Flask in a daemon thread
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()

    # Give Flask a moment to bind before opening the browser
    time.sleep(0.8)
    webbrowser.open(url)

    # Build tray icon
    icon_path = _resource_path("icon", "pyeqlogparser_icon.ico")
    image = Image.open(icon_path)

    def on_open(_icon, _item):
        webbrowser.open(url)

    def on_quit(icon, _item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open pyEQLogParser", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    tray = pystray.Icon("pyEQLogParser", image, "pyEQLogParser", menu)
    tray.run()  # blocks until on_quit calls icon.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("pyEQLogParser", f"Failed to start:\n\n{exc}")
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
