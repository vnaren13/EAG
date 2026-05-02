"""End-to-end test of the diffraction pipeline.

Hits live RSS feeds via fetch_coverage, persists via manage_diffraction,
and verifies dashboard.py rebuilds the Prefab tree with the new data.

We deliberately do NOT spawn `prefab serve` here — that's tested manually,
and spawning it during pytest creates port-conflict flakes against any
already-running webapp.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "diffractions.json"


@pytest.fixture
def isolated_data():
    """Move any real diffractions.json aside so the test runs against a clean store."""
    backup = None
    if DATA_FILE.exists():
        backup = DATA_FILE.read_text(encoding="utf-8")
        DATA_FILE.unlink()
    yield
    if backup is not None:
        DATA_FILE.write_text(backup, encoding="utf-8")


def test_pipeline_fetch_save_render(isolated_data):
    """Full pipeline: fetch real coverage → save → dashboard renders new data."""
    from tools.coverage import fetch_coverage
    from tools.store import manage_diffraction

    # 1. Fetch real coverage of a topic that should hit multiple outlets.
    res = fetch_coverage("Trump Germany Iran troops", max_outlets=4)
    assert res["count"] >= 2, f"expected ≥2 outlets, got {res['count']} (skipped: {res.get('skipped')})"

    # 2. Save with framing notes (agent-style).
    articles = []
    for art in res["articles"]:
        art["framing_notes"] = ["test-framing-1", "test-framing-2"]
        articles.append(art)

    create = manage_diffraction(
        op="create",
        topic="E2E pipeline test",
        articles=articles,
        synthesis="**Test synthesis** — the agent compares outlets here.",
        tags=["e2e-test", "live-network"],
    )
    assert create["ok"] is True
    diff_id = create["diffraction"]["id"]

    # 3. dashboard.py rebuilds and includes the new record.
    import dashboard
    importlib.reload(dashboard)

    # The view tree must contain the new topic somewhere — recursive search.
    found = _tree_contains(dashboard.app.view, "E2E pipeline test")
    assert found, "saved topic not found in dashboard tree"
    found_synth = _tree_contains(dashboard.app.view, "Test synthesis")
    assert found_synth, "synthesis not found in dashboard tree"

    # 4. Cleanup.
    deleted = manage_diffraction("delete", diffraction_id=diff_id)
    assert deleted["ok"] is True


def _tree_contains(node, needle: str) -> bool:
    """Recursive search for a string in any text-bearing field of the view tree."""
    if hasattr(node, "model_dump"):
        d = node.model_dump()
    elif isinstance(node, dict):
        d = node
    elif isinstance(node, list):
        return any(_tree_contains(item, needle) for item in node)
    elif isinstance(node, str):
        return needle in node
    else:
        return False

    for v in d.values():
        if isinstance(v, str) and needle in v:
            return True
        if isinstance(v, (list, dict)) and _tree_contains(v, needle):
            return True
    # Also walk live children (not always in model_dump output).
    children = getattr(node, "children", None)
    if children:
        return any(_tree_contains(c, needle) for c in children)
    return False
