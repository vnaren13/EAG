# News Diffractor

> An MCP server that diffracts a single news story across multiple outlets and surfaces a side-by-side comparison dashboard built with [Prefab UI](https://prefab.prefect.io).

You read one outlet's coverage of a story and absorb its framing without realising. **News Diffractor** asks an agent to fetch the same story from BBC, Al Jazeera, The Guardian, Times of India, etc., compare how each outlet frames it, persist the analysis locally, and render a live comparison dashboard in your browser — all from a single natural-language prompt.

---

## Tools

| Capability | Implementation |
|---|---|
| **Internet fetch** | `fetch_coverage(topic)` — pulls the same story from a curated set of major-outlet RSS feeds and extracts full body text via `trafilatura`. No API keys. |
| **Local persistence (CRUD)** | `manage_diffraction(op, ...)` — single tool, all of `create / read / update / delete / list` over `data/diffractions.json`. |
| **UI back to the user** | `show_diffractor(diffraction_id?)` — opens the user's browser onto a live Prefab dashboard. |
| **Web-app surface** | `prefab serve dashboard.py` runs a real React webapp at `http://localhost:5175/`. The MCP server spawns it automatically as a child process. |
| **Single-prompt orchestration** | One natural-language prompt drives all three tools plus the dashboard — see the [demo prompt](#-the-demo-prompt) below. |

---

## ✨ The demo prompt

Paste this into any MCP-capable agent (Claude Code, Claude Desktop, Cursor, etc.) once the server is registered:

> **"Diffract today's coverage of the OpenAI EU regulatory probe across major outlets, compare their framing and headlines, save the analysis with a Markdown synthesis, then show me my news diffractor dashboard."**

The agent is forced to:
1. Call `fetch_coverage(topic="OpenAI EU regulatory probe")` to gather articles from multiple outlets.
2. **Reason across the bodies** to derive 3-5 short *framing notes* per outlet (e.g. `["regulatory crackdown", "data privacy", "EU angle"]`) and write a Markdown synthesis comparing how the story is told.
3. Call `manage_diffraction(op="create", topic, articles=<with framing_notes>, synthesis, tags)` to persist.
4. Call `show_diffractor(diffraction_id=<just-created>)` — your browser opens onto the live dashboard.

The dashboard re-renders automatically after every save.

---

## 🚀 Setup

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (the install path below; pip works too)

### Install

```bash
git clone <this-repo>
cd news-diffractor
uv venv --python 3.11
source .venv/Scripts/activate          # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### Smoke-test

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

All 19 tests should pass in ~12 s (one of them — `test_e2e.py::test_e2e_pipeline` — actually hits live RSS feeds, so an internet connection is required).

### Run the server

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python server.py
```

This starts the FastMCP stdio server **and** auto-spawns `prefab serve dashboard.py --port 5175 --reload` as a child process. When the server exits, the Prefab webapp is cleaned up.

---

## 🔌 Hooking it up to an MCP client

See [`docs/mcp-client-config.md`](docs/mcp-client-config.md) for snippets for:

- Claude Code (`~/.claude/mcp_servers.json` or `.mcp.json` in project root)
- Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`)
- Cursor / any other MCP-stdio client

The server is just `uv run python server.py` from the project root.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Any MCP client (Claude Code, Claude Desktop, Cursor, …)         │
└────────────────────────┬────────────────────────────────────────┘
                         │ stdio
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  server.py (FastMCP)                                             │
│   on startup → subprocess.Popen(prefab serve dashboard.py …)     │
│                                                                   │
│  Tools:                                                           │
│   ├─ fetch_coverage(topic, max_outlets, outlets)                 │
│   ├─ manage_diffraction(op, diffraction_id, topic, …)            │
│   └─ show_diffractor(diffraction_id?)                            │
│       └─ os.utime(dashboard.py)  ← bumps prefab-reload           │
│       └─ webbrowser.open(localhost:5175)                          │
└────────────────────────┬────────────────────────────────────────┘
                         │ child process
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  prefab serve dashboard.py @ http://localhost:5175 --reload      │
│  dashboard.py reads data/diffractions.json on every reload       │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP
                         ▼
                   ┌──────────────┐
                   │   Browser    │  ← user sees the dashboard
                   └──────────────┘
```

Why **web-app** rather than rendering inline in Claude Desktop's MCP-Apps panel? Prefab is a UI framework with its own React renderer — `prefab serve` is purpose-built for this. Coupling the project to one specific MCP client (Claude Desktop's MCP-Apps spec) was unnecessary. With `prefab serve`, the dashboard works with **any** MCP client.

---

## 📁 Project layout

```
news-diffractor/
├── pyproject.toml           # fastmcp, prefab-ui, httpx, feedparser, trafilatura
├── README.md                ← this file
├── server.py                # FastMCP entry; spawns prefab serve as child
├── dashboard.py             # Prefab UI definition (rendered by `prefab serve`)
├── tools/
│   ├── coverage.py          # fetch_coverage     (internet fetch)
│   ├── store.py             # manage_diffraction (local CRUD)
│   └── ui.py                # show_diffractor    (browser UI)
├── data/                    # diffractions.json (gitignored)
├── tests/
│   ├── test_coverage.py     # keyword-parsing, scoring, favicon URLs
│   ├── test_store.py        # full CRUD, edge cases, dashboard touch
│   ├── test_mcp_client.py   # tools exposed via MCP, called via FastMCP Client
│   └── test_e2e.py          # live: fetch → save → dashboard updates
└── docs/
    ├── mcp-client-config.md
    └── superpowers/specs/2026-05-01-news-diffractor-design.md
```

---

## 📰 Outlets covered

A keyless, geographically/ideologically diverse curated set:

- **International:** BBC, The Guardian, Al Jazeera
- **Indian:** Times of India, The Hindu, Indian Express
- **Tech:** TechCrunch, The Verge, Ars Technica, Hacker News

All consumed via direct RSS feeds — no Google News redirects, no API keys, no rate-limit drama.

---

## 🛠 Stack

- [**FastMCP**](https://gofastmcp.com) — MCP server framework
- [**Prefab UI**](https://prefab.prefect.io) — declarative Python → React UI framework, served via `prefab serve`
- [`httpx`](https://www.python-httpx.org/) + [`feedparser`](https://feedparser.readthedocs.io/) for RSS fetching
- [`trafilatura`](https://trafilatura.readthedocs.io/) for clean article-body extraction
- All data is local (`data/diffractions.json`); no telemetry, no cloud, no signup, no API keys

---

## 🎯 Design decisions worth knowing

- **Why one CRUD tool with an `op` parameter** instead of 5 separate tools? One tool, five operations keeps the agent's tool list compact and the operation set explicit — agents reason about `op="create"` more reliably than picking between `create_diffraction` / `read_diffraction` / etc.
- **Why per-outlet RSS feeds** instead of Google News search? Google News links are encoded redirects that return HTTP 400 to direct fetches as of May 2026 — even via decoder libraries. Per-outlet RSS gives direct, stable URLs that `trafilatura` can extract from cleanly.
- **Why `framing_notes` + Markdown `synthesis` together?** Structured `framing_notes` (3-5 short phrases per outlet) drive the visual badges in the dashboard; free-form `synthesis` lets the agent write a real paragraph comparing outlets. They serve different jobs.
- **Why touch `dashboard.py` instead of a more elegant reload?** I empirically tested: `prefab serve --reload` watches the target `.py` file but not data files. Touching `dashboard.py` after every CRUD write triggers reload, which re-runs the script, which re-reads the JSON. Confirmed working in ~3 s per cycle.
- **Why drop `full_text` before persisting?** Articles are copyrighted. The dashboard only needs the lead snippet + URL; the agent gets the full body in-memory during reasoning and never asks for it again.
