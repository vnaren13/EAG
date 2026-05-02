"""CRUD on data/diffractions.json."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "diffractions.json"
DASHBOARD_FILE = Path(__file__).resolve().parent.parent / "dashboard.py"

Op = Literal["create", "read", "update", "delete", "list"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"diffractions": []}
    raw = DATA_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return {"diffractions": []}
    return json.loads(raw)


def _save(state: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    # Touch dashboard.py to trigger `prefab serve --reload` so the running
    # webapp re-renders with fresh data without us managing its lifecycle.
    if DASHBOARD_FILE.exists():
        os.utime(DASHBOARD_FILE, None)


def _find(state: dict[str, Any], diffraction_id: str) -> dict[str, Any] | None:
    for d in state["diffractions"]:
        if d["id"] == diffraction_id:
            return d
    return None


def manage_diffraction(
    op: Op,
    diffraction_id: str | None = None,
    topic: str | None = None,
    articles: list[dict[str, Any]] | None = None,
    synthesis: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Single-tool CRUD over data/diffractions.json.

    Operations:
      - create: requires topic + articles; synthesis/tags optional. Returns the new record.
      - read:   requires diffraction_id. Returns the record.
      - update: requires diffraction_id. synthesis/tags/articles override existing.
      - delete: requires diffraction_id. Returns {"deleted": id}.
      - list:   returns lightweight summary list (no full article bodies).
    """
    state = _load()

    if op == "create":
        if not topic or not articles:
            return {"error": "create requires both topic and articles"}
        record = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "fetched_at": _now(),
            "articles": _strip_articles_for_storage(articles),
            "synthesis": synthesis or "",
            "tags": tags or [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        state["diffractions"].append(record)
        _save(state)
        return {"ok": True, "diffraction": record}

    if op == "read":
        if not diffraction_id:
            return {"error": "read requires diffraction_id"}
        record = _find(state, diffraction_id)
        if record is None:
            return {"error": f"no diffraction with id {diffraction_id}"}
        return {"ok": True, "diffraction": record}

    if op == "update":
        if not diffraction_id:
            return {"error": "update requires diffraction_id"}
        record = _find(state, diffraction_id)
        if record is None:
            return {"error": f"no diffraction with id {diffraction_id}"}
        if synthesis is not None:
            record["synthesis"] = synthesis
        if tags is not None:
            record["tags"] = tags
        if articles is not None:
            record["articles"] = _strip_articles_for_storage(articles)
        if topic is not None:
            record["topic"] = topic
        record["updated_at"] = _now()
        _save(state)
        return {"ok": True, "diffraction": record}

    if op == "delete":
        if not diffraction_id:
            return {"error": "delete requires diffraction_id"}
        before = len(state["diffractions"])
        state["diffractions"] = [d for d in state["diffractions"] if d["id"] != diffraction_id]
        if len(state["diffractions"]) == before:
            return {"error": f"no diffraction with id {diffraction_id}"}
        _save(state)
        return {"ok": True, "deleted": diffraction_id}

    if op == "list":
        summary = [
            {
                "id": d["id"],
                "topic": d["topic"],
                "outlets": [a.get("outlet") for a in d.get("articles", [])],
                "tags": d.get("tags", []),
                "fetched_at": d.get("fetched_at"),
                "has_synthesis": bool(d.get("synthesis")),
            }
            for d in state["diffractions"]
        ]
        return {"ok": True, "diffractions": summary, "count": len(summary)}

    return {"error": f"unknown op: {op!r}. expected one of: create/read/update/delete/list"}


def _strip_articles_for_storage(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop full_text from articles before persisting — copyright + storage hygiene.
    Lead snippet (capped) + URL is enough for the dashboard.
    """
    cleaned = []
    for a in articles:
        snippet = a.get("lead_snippet") or a.get("full_text") or ""
        cleaned.append({
            "outlet": a.get("outlet", ""),
            "url": a.get("url", ""),
            "headline": a.get("headline", ""),
            "lead_snippet": snippet[:500],
            "favicon_url": a.get("favicon_url", ""),
            "framing_notes": a.get("framing_notes", []),
            "published_at": a.get("published_at", ""),
        })
    return cleaned
