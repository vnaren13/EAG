"""Browser-opening UI tool that surfaces the dashboard back to the user.

Self-healing: if the Prefab webapp isn't reachable when called, this tool
spawns it itself and waits for it to come up before opening the browser.
That way the user gets a working dashboard even if the auto-spawn at
server startup failed for any reason (UTF-8, port conflict, MCP client
quirks, etc).
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = ROOT / "dashboard.py"
LOG_FILE = ROOT / "data" / "prefab.log"

_managed_proc: subprocess.Popen | None = None


def _port() -> int:
    return int(os.environ.get("PREFAB_PORT", "5175"))


def _is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _prefab_bin() -> str:
    candidates = [
        ROOT / ".venv" / "Scripts" / "prefab.exe",
        ROOT / ".venv" / "bin" / "prefab",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "prefab"


def _spawn_prefab(port: int) -> subprocess.Popen | None:
    """Start `prefab serve dashboard.py` if not already running. stderr is logged
    to data/prefab.log so silent failures become visible.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    log_handle = open(LOG_FILE, "a", encoding="utf-8")
    log_handle.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} starting prefab on :{port} ===\n")
    log_handle.flush()

    try:
        # Relative target "dashboard.py" — Prefab's CLI parses TARGET as
        # "path:attribute" so a Windows absolute path "D:\..." would split
        # on the drive-letter colon and break.
        proc = subprocess.Popen(
            [
                _prefab_bin(),
                "serve",
                "dashboard.py",
                "--port", str(port),
                "--reload",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        log_handle.write(f"FAILED to spawn: {exc}\n")
        log_handle.close()
        return None

    return proc


def _ensure_dashboard_running(port: int, max_wait_s: float = 12.0) -> tuple[bool, str]:
    """Make sure http://localhost:<port> answers. Returns (ok, message)."""
    global _managed_proc

    if _is_port_open(port):
        return True, f"Dashboard already up on port {port}."

    # Not reachable — try to start it ourselves.
    _managed_proc = _spawn_prefab(port)
    if _managed_proc is None:
        return False, (
            f"Could not spawn `prefab serve`. "
            f"Check {LOG_FILE} for errors, or run manually:\n"
            f"  prefab serve dashboard.py --port {port} --reload"
        )

    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if _is_port_open(port):
            return True, f"Dashboard ready on port {port}."
        if _managed_proc.poll() is not None:
            return False, (
                f"Prefab process exited with code {_managed_proc.returncode}. "
                f"See {LOG_FILE} for details."
            )
        time.sleep(0.4)

    return False, (
        f"Prefab did not bind port {port} within {max_wait_s}s. "
        f"See {LOG_FILE} for details."
    )


def show_diffractor(diffraction_id: str | None = None) -> dict[str, Any]:
    """Open the Prefab dashboard in the user's browser.

    If the dashboard webapp isn't already running (e.g. the auto-spawn at
    server startup failed), this tool will start it on demand and wait for
    it to come up before opening the browser.

    Args:
        diffraction_id: Optional — pass to deep-link a specific record.
    """
    port = _port()

    # Touch dashboard.py so prefab --reload re-renders with the latest JSON.
    if DASHBOARD_FILE.exists():
        try:
            os.utime(DASHBOARD_FILE, None)
        except OSError:
            pass

    ok, message = _ensure_dashboard_running(port)
    if not ok:
        return {
            "ok": False,
            "url": f"http://localhost:{port}/",
            "opened_browser": False,
            "message": message,
        }

    base = f"http://localhost:{port}/"
    url = base + "?" + urlencode({"id": diffraction_id}) if diffraction_id else base

    opened = False
    try:
        opened = webbrowser.open(url, new=2)
    except Exception:
        opened = False

    return {
        "ok": True,
        "url": url,
        "opened_browser": opened,
        "message": (
            f"News Diffractor dashboard opened in your browser. {message}"
            if opened
            else f"Dashboard ready at {url} — open manually if no tab popped. {message}"
        ),
    }
