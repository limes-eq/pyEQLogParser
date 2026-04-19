"""Entry point for packaged distribution. Starts the Flask server and opens the browser."""
from __future__ import annotations
import os
import sys
import socket
import threading
import time
import webbrowser


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

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()
    # Give Flask a moment to bind before opening the browser
    time.sleep(0.8)
    webbrowser.open(url)
    server.join()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("EQ Log Parser", f"Failed to start:\n\n{exc}")
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
