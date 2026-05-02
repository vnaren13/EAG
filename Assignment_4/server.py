"""News Diffractor — FastMCP entry point.

Wires three MCP tools and silently spawns the Prefab webapp as a child
process so the user only ever has to launch this single server.

Run directly:
    uv run python server.py             # local smoke test
Or register with an MCP client (see docs/mcp-client-config.md).
"""
from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP

from tools.coverage import OUTLETS, fetch_coverage as _fetch_coverage
from tools.store import manage_diffraction as _manage_diffraction
from tools.ui import show_diffractor as _show_diffractor

ROOT = Path(__file__).resolve().parent
DASHBOARD_FILE = ROOT / "dashboard.py"

mcp = FastMCP(
    "News Diffractor",
    instructions=(
        "Tools for diffracting a single news story across multiple outlets and "
        "surfacing a side-by-side dashboard.\n\n"
        "Pipeline expected by the user:\n"
        "  1. fetch_coverage(topic) — pull the same story from multiple outlets.\n"
        "  2. Read the articles, decide on framing notes per outlet (3-5 short "
        "phrases each), and write a Markdown synthesis comparing how outlets "
        "frame the story.\n"
        "  3. manage_diffraction(op='create', topic, articles=<with framing_notes>, "
        "synthesis=<your markdown>, tags) — persist the study.\n"
        "  4. show_diffractor(diffraction_id=<just-created-id>) — open the user's "
        "browser onto the live dashboard.\n\n"
        f"Available outlets: {', '.join(OUTLETS.keys())}."
    ),
)


# ---------------------------------------------------------------------------
# Tool registrations (thin wrappers so FastMCP gets clean signatures + docs)
# ---------------------------------------------------------------------------

@mcp.tool
def fetch_coverage(
    topic: str,
    max_outlets: int = 5,
    outlets: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch coverage of a single news topic across multiple curated outlets.

    The returned `articles` include `full_text` so you can read and reason
    about each outlet's framing. Persist via `manage_diffraction(op='create')`
    after extracting per-outlet `framing_notes` (3-5 short phrases).

    Args:
        topic: The news story you want to diffract (e.g. "OpenAI EU regulatory probe").
        max_outlets: Cap on number of outlets to include.
        outlets: Optional subset filter, e.g. ["BBC", "Al Jazeera"].
    """
    return _fetch_coverage(topic=topic, max_outlets=max_outlets, outlets=outlets)


@mcp.tool
def manage_diffraction(
    op: Literal["create", "read", "update", "delete", "list"],
    diffraction_id: str | None = None,
    topic: str | None = None,
    articles: list[dict[str, Any]] | None = None,
    synthesis: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """CRUD over the local diffractions store (`data/diffractions.json`).

    Operations:
      - create: requires topic + articles; synthesis/tags optional.
      - read:   requires diffraction_id.
      - update: requires diffraction_id; pass any subset of fields to update.
      - delete: requires diffraction_id.
      - list:   no args; returns lightweight summaries.
    """
    return _manage_diffraction(
        op=op,
        diffraction_id=diffraction_id,
        topic=topic,
        articles=articles,
        synthesis=synthesis,
        tags=tags,
    )


@mcp.tool
def show_diffractor(diffraction_id: str | None = None) -> dict[str, Any]:
    """Open the News Diffractor dashboard in the user's browser.

    The dashboard is a real Prefab webapp running locally at
    http://localhost:5175/ (port can be overridden via PREFAB_PORT env var).
    It re-renders automatically after every CRUD write.

    Args:
        diffraction_id: Optional — pass to deep-link a specific record.
    """
    return _show_diffractor(diffraction_id=diffraction_id)


# ---------------------------------------------------------------------------
# Prefab webapp child process
# ---------------------------------------------------------------------------

_prefab_proc: subprocess.Popen | None = None


def _start_prefab_webapp() -> None:
    """Spawn `prefab serve dashboard.py --port <port> --reload` as a daemon."""
    global _prefab_proc
    port = os.environ.get("PREFAB_PORT", "5175")
    prefab_bin = ROOT / ".venv" / "Scripts" / "prefab.exe"
    if not prefab_bin.exists():
        # POSIX layout fallback
        prefab_bin = ROOT / ".venv" / "bin" / "prefab"
    if not prefab_bin.exists():
        # Last resort: rely on PATH
        prefab_bin = "prefab"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # Use relative path "dashboard.py" with cwd=ROOT — Prefab's CLI parses
    # TARGET as "path:attribute" so an absolute Windows path like "D:\..."
    # gets mangled (drive-letter colon collides with the attribute separator).
    cmd = [
        str(prefab_bin),
        "serve",
        "dashboard.py",
        "--port", port,
        "--reload",
    ]
    try:
        _prefab_proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        # Tiny grace period; not strictly needed since the user only hits the
        # webapp when they call show_diffractor.
        time.sleep(0.5)
        sys.stderr.write(
            f"[news-diffractor] Prefab webapp pid={_prefab_proc.pid} on port {port}\n"
        )
    except FileNotFoundError:
        sys.stderr.write(
            f"[news-diffractor] WARNING: could not start `prefab serve` "
            f"(binary not found: {prefab_bin}). Dashboard will be unavailable; "
            f"start manually with: prefab serve dashboard.py --port {port} --reload\n"
        )


def _stop_prefab_webapp() -> None:
    global _prefab_proc
    if _prefab_proc and _prefab_proc.poll() is None:
        try:
            _prefab_proc.terminate()
            _prefab_proc.wait(timeout=3)
        except Exception:
            try:
                _prefab_proc.kill()
            except Exception:
                pass


atexit.register(_stop_prefab_webapp)


def _install_signal_handlers() -> None:
    def _on_signal(_signum, _frame):  # noqa: ARG001
        _stop_prefab_webapp()
        sys.exit(0)

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _on_signal)
            except (ValueError, OSError):
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _install_signal_handlers()
    _start_prefab_webapp()
    mcp.run()


if __name__ == "__main__":
    main()
