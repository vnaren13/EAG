# Session 9 — Browser Comparison Agent + Replay Viewer
### Architecture Note

## 1. The task

**Goal:** compare the top trending **Python repositories on GitHub this week** —
for each, extract the repository name, primary language, total stars, and
stars gained this week, then rank the fastest-growing one and explain why.

This is a task that Session 8's `web_search` + `fetch_url` cannot do reliably:
the data only appears **after** the page's filters (language = Python, date
range = this week) are applied, and GitHub Trending is a JavaScript-driven page
where a static fetch returns the page shell, not the ranked list. The agent must
**interact** — open the page, apply the language filter, apply the date filter,
and read the resulting cards. That is ≥3 visible browser actions.

## 2. System architecture

The agent is built on the **Session 8 growing-graph orchestrator**
([`flow.py`](S9SharedCode/code/flow.py)), which was **not modified**. The loop is
a NetworkX DiGraph that grows at runtime: the Planner seeds a plan, skills emit
successors, and the orchestrator splices in static successors, auto-inserts a
Critic after any `critic:true` skill, and re-invokes the Planner on failure.

New behaviour was added **only** through the skill catalogue and the Browser
skill — exactly as the assignment requires.

```
User goal
   │
   ▼
Planner ──► Browser ──► Distiller ──► [auto-Critic] ──► Formatter
 (DAG)     (interact)   (extract)      (verify)         (answer + table)
```

| Skill | Role | Provider (via gateway) |
|---|---|---|
| **Planner** | Decomposes the goal into the DAG; names skills, never tools | gemini |
| **Browser** | Drives GitHub Trending through a layered cascade | gemini (a11y/vision) |
| **Distiller** | Turns raw page text into structured per-repo records | gemini |
| **Critic** | Auto-inserted; pass/fail on completeness + plausibility | groq |
| **Formatter** | Renders the final comparison table + ranking | gemini |

All LLM calls go through the local **`llm_gatewayV9`** proxy (`:8109`), which
provides provider failover (Gemini → Groq), rate-limit handling, per-agent cost
attribution, and the `/v1/vision` endpoint the Browser's vision layer uses.

## 3. The Browser cascade (the heart of S9)

The Browser skill ([`browser/skill.py`](S9SharedCode/code/browser/skill.py)) owns
a four-layer cascade and stops at the first layer that succeeds:

| Layer | Mechanism | When it fires |
|---|---|---|
| 1 · **extract** | `trafilatura` over a plain HTTP GET (no LLM) | static pages |
| 2a · **deterministic** | caller-supplied CSS selectors via Playwright | when selectors given |
| 2b · **a11y** | accessibility tree + coordinate actions, LLM-driven | interactive pages |
| 3 · **vision** | set-of-marks screenshot + `/v1/vision` | no DOM grip, pixels only |

A **gateway-blocked** result (CAPTCHA / login wall / Cloudflare) is a first-class
failure that short-circuits to the Planner's recovery path.

**For this task the cascade chose Layer 2b (a11y).** GitHub Trending has an
accessible DOM (the filter controls and repo cards are real elements), so the
a11y driver clicks the language and date filters and reads the cards in ~5–6
turns. The extract layer is correctly skipped because the goal contains
interaction verbs (filter/sort) and the filtered data isn't in the bare HTML.

## 4. Design decisions and fixes

Integrating a real interactive site surfaced several issues. All fixes live in
the **Browser skill or the skill-catalogue prompts** — never in the orchestrator.

1. **Planner wiring (`planner.md`).** The Planner initially pointed the Formatter
   at the Critic node (a pass/fail verdict, no data). Rule added: the Formatter
   must read the **data** node (Distiller), never a Critic.

2. **Browser navigation resilience (`driver.py`).** GitHub's filter controls
   trigger a full-page reload; the per-turn DOM read then raced the navigation
   and crashed ("Execution context destroyed"). Added `_safe_enumerate()` —
   wait for load state, retry once — so the driver survives navigations.

3. **Critic over-rejection (`critic.md`).** The auto-inserted Critic only sees
   `USER_QUERY` + the upstream output, never the Browser's raw page text, so it
   kept calling **correct** extracted data "fabricated/unsupported" and forced
   endless re-planning. Rewrote the Critic to (a) not treat an unseen source as
   fabrication, (b) judge only what the node is responsible for — a data node
   owns per-item fields; ranking/synthesis is the Formatter's job — and
   (c) honour optional/range requirements ("at least 3").

4. **Memory hygiene.** The S7 FAISS memory accumulated data from earlier,
   unrelated runs and bled it into every prompt, confusing the small Distiller
   model. The demo runner now clears the FAISS index before each run.

## 5. Results

A clean run is a tidy 5-node DAG with **no loops**:

```
planner ✅ → browser ✅ (a11y, 5–6 turns) → distiller ✅ (4 repos)
        → critic ✅ PASS → formatter ✅
```

**Final comparison table** (live data, e.g. session `s8-ee528ca3`):

| Repository | Language | Total stars | Stars this week |
|---|---|---:|---:|
| microsoft/markitdown | Python | 152,130 | 10,513 |
| mvanhorn/last30days-skill | Python | 40,418 | 3,254 |
| Panniantong/Agent-Reach | Python | 26,817 | 2,188 |
| chopratejas/headroom | Python | 24,815 | 1,623 |

**Fastest-growing:** `microsoft/markitdown` — highest total stars *and* most
stars gained this week.

## 6. Replay viewer

A custom [`report.py`](S9SharedCode/code/report.py) reads the session's saved
node files and emits a self-contained HTML replay covering all 8 required
sections: user goal, planner DAG, browser path, browser actions, screenshots,
extracted data, final comparison table, and the turn-count + cost summary. It
only *reads* state the orchestrator wrote — no runtime or orchestrator changes.

```
uv run python report.py <session_id>   →   replay_<session_id>.html
```

The one-shot runner [`run_github_demo.ps1`](run_github_demo.ps1) ties it together:
clear memory → run the agent (live trace) → build the replay → open it.

## 7. What this demonstrates

The agent does what static fetch cannot: it **interacts** with a JavaScript page,
applies site-native filters and sorting, and extracts data that exists only after
those actions — then verifies and structures it. The cascade picks the cheapest
working layer (a11y here), recovers from gateway blocks, and attributes cost per
agent through the gateway ledger.
