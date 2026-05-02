"""Unit tests for tools.store — pure CRUD on diffractions.json."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_data(monkeypatch, tmp_path):
    """Point store + dashboard touch at a temp dir for each test."""
    from tools import store

    fake_data = tmp_path / "diffractions.json"
    fake_dash = tmp_path / "dashboard.py"
    fake_dash.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(store, "DATA_FILE", fake_data)
    monkeypatch.setattr(store, "DASHBOARD_FILE", fake_dash)
    yield fake_data


def test_list_when_empty(isolated_data):
    from tools.store import manage_diffraction

    res = manage_diffraction("list")
    assert res == {"ok": True, "diffractions": [], "count": 0}


def test_create_requires_topic_and_articles(isolated_data):
    from tools.store import manage_diffraction

    assert "error" in manage_diffraction("create")
    assert "error" in manage_diffraction("create", topic="x")
    assert "error" in manage_diffraction("create", articles=[{}])


def test_create_strips_full_text(isolated_data):
    """Full article body must NOT be persisted to disk — copyright + storage."""
    from tools.store import manage_diffraction

    long_body = "X" * 10000
    res = manage_diffraction(
        "create",
        topic="t",
        articles=[{
            "outlet": "BBC",
            "url": "https://bbc.com/x",
            "headline": "h",
            "lead_snippet": "lead snippet",
            "full_text": long_body,
            "framing_notes": ["a"],
        }],
    )
    assert res["ok"] is True
    persisted = isolated_data.read_text(encoding="utf-8")
    assert "lead snippet" in persisted
    assert long_body not in persisted, "full_text leaked into JSON"


def test_full_round_trip(isolated_data):
    from tools.store import manage_diffraction

    created = manage_diffraction(
        "create",
        topic="round-trip",
        articles=[{"outlet": "BBC", "url": "u", "headline": "h"}],
        synthesis="s",
        tags=["t"],
    )
    did = created["diffraction"]["id"]

    read = manage_diffraction("read", diffraction_id=did)
    assert read["diffraction"]["topic"] == "round-trip"

    upd = manage_diffraction(
        "update", diffraction_id=did, synthesis="updated", tags=["new"]
    )
    assert upd["diffraction"]["synthesis"] == "updated"
    assert upd["diffraction"]["tags"] == ["new"]

    listed = manage_diffraction("list")
    assert listed["count"] == 1

    deleted = manage_diffraction("delete", diffraction_id=did)
    assert deleted["deleted"] == did

    assert manage_diffraction("list")["count"] == 0


def test_read_missing_id(isolated_data):
    from tools.store import manage_diffraction

    res = manage_diffraction("read", diffraction_id="does-not-exist")
    assert "error" in res


def test_delete_missing_id(isolated_data):
    from tools.store import manage_diffraction

    res = manage_diffraction("delete", diffraction_id="does-not-exist")
    assert "error" in res


def test_unknown_op(isolated_data):
    from tools.store import manage_diffraction

    res = manage_diffraction("garbage")  # type: ignore[arg-type]
    assert "error" in res


def test_create_touches_dashboard(isolated_data, tmp_path, monkeypatch):
    """Create operation should bump dashboard.py mtime so prefab reload picks it up."""
    from tools import store
    from tools.store import manage_diffraction

    fake_dash = store.DASHBOARD_FILE
    initial_mtime = fake_dash.stat().st_mtime

    import time
    time.sleep(0.05)

    manage_diffraction(
        "create",
        topic="t",
        articles=[{"outlet": "BBC", "url": "u", "headline": "h"}],
    )

    new_mtime = fake_dash.stat().st_mtime
    assert new_mtime > initial_mtime, "dashboard.py mtime did not advance"
