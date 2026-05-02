# News Diffractor — Design

**Date:** 2026-05-01
**Author:** vnaren13
**Status:** Approved, in implementation

## Problem

People read one outlet's coverage of a story and absorb its framing without realising. The agent's job: pull coverage of the same story from multiple outlets, compare framing/headlines/lead paragraphs, persist a side-by-side study, and render an interactive comparison dashboard in the browser.

## Tool design

| Capability | Implementation |
|---|---|
| Internet fetch (search/API) | `fetch_coverage(topic)` — Google News RSS + `trafilatura` for article extraction |
| Local persistence (CRUD) | `manage_diffraction(op, ...)` on `data/diffractions.json` |
| UI back to user | `show_diffractor(diffraction_id?)` opens browser to local Prefab webapp |
| Web-app surface | `prefab serve dashboard.py` runs a real React webapp at `localhost:5175` |
| Single-prompt orchestration | "Diffract today's coverage of X across major outlets, compare their framing, save the analysis, then show me my news diffractor dashboard." |

## Architecture

```
[MCP client: Claude Code, Claude Desktop, anything else]
            │  stdio
            ▼
┌─────────────────────────────────────────────────────────┐
│  server.py (FastMCP)                                     │
│  on startup → spawns: prefab serve dashboard.py --reload │
│                                                           │
│  tools:                                                   │
│   ├─ fetch_coverage(topic, max_outlets)                  │
│   ├─ manage_diffraction(op, ...)                         │
│   └─ show_diffractor(diffraction_id?)                    │
│       └─ touches dashboard.py to trigger reload,          │
│          opens browser to localhost:5175                  │
└──────────┬──────────────────────────────────────────────┘
           │ subprocess
           ▼
┌─────────────────────────────────────────────────────────┐
│  prefab serve dashboard.py @ localhost:5175 --reload    │
│  dashboard.py reads data/diffractions.json on import     │
└─────────────────────────────────────────────────────────┘
           │ HTTP
           ▼
       [Browser]   ← user sees the dashboard here
```

The MCP server **owns** the Prefab webapp as a child process. One thing to launch (the MCP server); the webapp comes up automatically.

## Data model — `data/diffractions.json`

```json
{
  "diffractions": [{
    "id": "uuid",
    "topic": "OpenAI EU regulatory probe",
    "fetched_at": "2026-05-01T10:00:00Z",
    "articles": [{
      "outlet": "BBC", "url": "...", "headline": "...",
      "lead_snippet": "...",
      "favicon_url": "https://www.google.com/s2/favicons?sz=32&domain=bbc.com",
      "framing_notes": ["regulatory crackdown", "data privacy", "EU angle"],
      "published_at": "..."
    }],
    "synthesis": "Free-form Markdown — agent's diff analysis",
    "tags": ["openai", "regulation"],
    "created_at": "...", "updated_at": "..."
  }]
}
```

`framing_notes` per article = the agent's structured analysis (3–5 short phrases). This is what makes the side-by-side dashboard meaningful — the agent has to actually *compare* coverage, not shuffle data.

## Tool signatures

```python
# tools/coverage.py
def fetch_coverage(topic: str, max_outlets: int = 5) -> dict:
    """RSS-search Google News, extract main text from top N results.
    Returns: {topic, fetched_at, articles: [{outlet, url, headline,
              lead_snippet, full_text, published_at, favicon_url}]}"""

# tools/store.py
def manage_diffraction(op: Literal["create","read","update","delete","list"],
                       diffraction_id: str | None = None,
                       topic: str | None = None,
                       articles: list[dict] | None = None,
                       synthesis: str | None = None,
                       tags: list[str] | None = None) -> dict:
    """Single tool, all CRUD. Backed by data/diffractions.json."""

# tools/ui.py
def show_diffractor(diffraction_id: str | None = None) -> dict:
    """Touches dashboard.py to bust prefab-serve cache, opens browser.
    Returns: {url, message}."""
```

## Prefab UI shape (`dashboard.py`)

- Top heading + subtext
- DataTable of diffractions (topic, # outlets, date, tags)
- Each row click → Dialog with:
  - Side-by-side article cards (Row of Cards, scrollable)
  - Each card: favicon, outlet, headline, lead snippet, framing badges, "Read full" link
  - Markdown rendering of synthesis
  - Computed shared-vs-divergent keyword badges
- Empty state: friendly "Run your first diffraction…" message

## Demo prompt (canonical)

> "Diffract today's coverage of the OpenAI EU regulatory probe across major outlets, compare their framing, save the analysis, then show me my news diffractor dashboard."

Expected agent trace:
1. `fetch_coverage(topic="OpenAI EU regulatory probe", max_outlets=4)`
2. *(agent reads articles, derives framing notes per outlet, drafts synthesis)*
3. `manage_diffraction(op="create", topic=..., articles=[...with framing_notes...], synthesis=...)`
4. `show_diffractor(diffraction_id="<just-created-uuid>")` → opens browser

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `prefab serve` may render once at startup, miss new data | `--reload` flag + touch `dashboard.py` after writes |
| Google News RSS undocumented | Tight unit-test parser; clear error if structure changes |
| Outlets paywall/block extraction | `trafilatura` handles most; per-outlet errors are non-fatal |
| Subprocess orphan if MCP server crashes | `atexit.register` + signal handler |
| Article copyright | Persist only short lead snippets + URLs; full text only in-memory for agent reasoning |
| Port conflict on 5175 | `PREFAB_PORT` env var override |

## v1 scope

In v1 (per "go with (iii) both"):
- Outlet favicons via `s2/favicons` (keyless)
- Computed shared-vs-divergent keywords in dashboard

Out of v1: outlet preference config, multi-language support, on-disk full-text cache, manual synthesis editing.

## Out-of-scope / future ideas

- "Diff over time" — re-fetch a diffraction later and compare with original
- Outlet bias scoring via curated AllSides-style ratings
- Export to Markdown / PDF for sharing
- Browser extension to "diffract this article" from any news page

## Project layout

```
news-diffractor/
├── pyproject.toml           # fastmcp, prefab-ui, httpx, feedparser, trafilatura
├── README.md                # setup, demo, MCP client config
├── server.py                # FastMCP entry; spawns prefab serve as child
├── dashboard.py             # Prefab UI definition (rendered by `prefab serve`)
├── tools/
│   ├── __init__.py
│   ├── coverage.py
│   ├── store.py
│   └── ui.py
├── data/                    # diffractions.json gitignored
├── tests/
│   ├── test_coverage.py
│   ├── test_store.py
│   └── test_dashboard.py
└── docs/
    ├── superpowers/specs/2026-05-01-news-diffractor-design.md  ← THIS
    └── mcp-client-config.md
```
