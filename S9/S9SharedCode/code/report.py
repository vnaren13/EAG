"""report.py — turn a session's saved nodes into a self-contained HTML replay.

Usage:
    uv run python report.py <session_id>
    uv run python report.py                 # uses the newest session

Reads state/sessions/<sid>/ (the same files replay.py walks) and writes a
single HTML file with the 8 deliverables the assignment asks for:
  1 user goal   2 planner DAG   3 browser path   4 browser actions
  5 screenshots 6 extracted data 7 final table   8 turn + cost summary

No new runtime behaviour, no orchestrator changes — this only *reads*
state that flow.py already wrote.
"""
from __future__ import annotations

import base64
import glob
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SESSIONS = ROOT / "state" / "sessions"

STATUS_COLOR = {
    "complete": "#1a7f37", "failed": "#cf222e",
    "skipped": "#9a6700", "running": "#0969da", "pending": "#57606a",
}
SKILL_ICON = {
    "planner": "🧠", "browser": "🌐", "distiller": "📝", "critic": "✅",
    "formatter": "🖊️", "researcher": "🔎", "summariser": "📄",
    "retriever": "📚", "coder": "💻", "sandbox_executor": "⚙️",
}


def _esc(x) -> str:
    return html.escape(str(x))


def _load_nodes(sid_dir: Path) -> list[dict]:
    files = sorted(glob.glob(str(sid_dir / "nodes" / "n_*.json")),
                   key=lambda f: int(Path(f).stem.split("_")[1]))
    out = []
    for f in files:
        try:
            out.append(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
    return out


def _img_data_uri(png: Path) -> str:
    b = png.read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()


def _gateway_cost_by_agent(sid: str) -> dict | None:
    """Per-skill token/cost ledger for this session from the V9 gateway.
    Returns None if the gateway isn't running (token counts are then omitted).
    Uses stdlib urllib so report.py keeps no extra dependency."""
    import urllib.request
    try:
        url = f"http://localhost:8109/v1/cost/by_agent?session={sid}"
        with urllib.request.urlopen(url, timeout=4) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def build(sid: str) -> Path:
    sid_dir = SESSIONS / sid
    if not sid_dir.exists():
        raise SystemExit(f"no session {sid} at {sid_dir}")

    query = ""
    qf = sid_dir / "query.txt"
    if qf.exists():
        query = qf.read_text(encoding="utf-8").strip()

    nodes = _load_nodes(sid_dir)

    # ── 8 · totals ──────────────────────────────────────────────────────
    total_elapsed = 0.0
    total_cost = 0.0
    rows = []
    for n in nodes:
        r = n.get("result") or {}
        el = float(r.get("elapsed_s") or 0)
        co = float(r.get("cost") or 0)
        total_elapsed += el
        total_cost += co
        rows.append((n.get("node_id"), n.get("skill"), n.get("status"),
                     r.get("provider") or "—", el, co))

    parts: list[str] = []
    P = parts.append

    P(f"""<!doctype html><html lang=en><meta charset=utf-8>
<title>Replay — {_esc(sid)}</title>
<style>
 body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f8fa;color:#1f2328}}
 .wrap{{max-width:980px;margin:0 auto;padding:24px}}
 h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:28px 0 10px;border-bottom:1px solid #d0d7de;padding-bottom:6px}}
 .sid{{color:#57606a;font-size:13px;margin-bottom:18px}}
 .goal{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:14px 16px;font-size:16px}}
 .dag{{display:flex;flex-direction:column;gap:8px}}
 .node{{background:#fff;border:1px solid #d0d7de;border-left:5px solid #888;border-radius:8px;padding:10px 14px;display:flex;align-items:center;gap:10px}}
 .node .id{{font:600 13px monospace;color:#57606a;min-width:42px}}
 .node .skill{{font-weight:600}}
 .badge{{font-size:12px;color:#fff;border-radius:20px;padding:2px 10px;margin-left:auto}}
 .arrow{{margin:0 0 0 56px;color:#57606a}}
 .from{{font:12px monospace;color:#57606a}}
 table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d0d7de;border-radius:8px;overflow:hidden}}
 th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #eaeef2;font-size:14px}}
 th{{background:#f6f8fa;font-weight:600}}
 .num{{text-align:right;font-variant-numeric:tabular-nums}}
 pre{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:12px;overflow:auto;font-size:13px;white-space:pre-wrap}}
 .shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
 .shot{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:8px}}
 .shot img{{width:100%;border-radius:4px;border:1px solid #eaeef2}} .shot .cap{{font:12px monospace;color:#57606a;margin-top:6px}}
 .final{{background:#dafbe1;border:1px solid #1a7f37;border-radius:8px;padding:14px 16px}}
 .pill{{display:inline-block;background:#0969da;color:#fff;border-radius:20px;padding:3px 12px;font-size:13px;margin-right:8px}}
 .muted{{color:#57606a}}
 .mermaid{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:18px;text-align:center;overflow:auto}}
 .mermaid small{{font-size:11px;opacity:.7}}
 .mermaid.arch{{background:#0d1117;border-color:#30363d}}
 details{{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:8px 12px;margin:6px 0}}
 summary{{cursor:pointer;font:13px monospace;color:#0969da}}
</style>
<div class=wrap>
<h1>🎬 Browser Agent — Replay Report</h1>
<div class=sid>session <code>{_esc(sid)}</code> · {len(nodes)} nodes · {total_elapsed:.1f}s total</div>
""")

    # 1 · goal
    P("<h2>1 · User goal</h2>")
    P(f"<div class=goal>{_esc(query) or '<span class=muted>(no query.txt)</span>'}</div>")

    def _mid(x: str) -> str:                 # mermaid-safe node id (no colon)
        return str(x).replace(":", "_")

    # 2 · Planner DAG — the actual node graph the Planner produced for this run.
    P("<h2>2 · Planner DAG</h2>")
    g = ["flowchart LR"]
    for n in nodes:
        nid = n.get("node_id"); sk = n.get("skill"); st = n.get("status")
        ic = SKILL_ICON.get(sk, "")
        g.append(f'  {_mid(nid)}(["{ic} {sk}<br/><small>{nid}</small>"]):::{st}')
    for n in nodes:
        nid = n.get("node_id")
        for u in (n.get("inputs") or []):
            if str(u).startswith("n:"):
                g.append(f"  {_mid(u)} --> {_mid(nid)}")
    # dark boxes (reference style) with status-coloured borders
    g += [
        "  classDef complete fill:#21262d,stroke:#3fb950,stroke-width:2px,color:#e6edf3;",
        "  classDef failed fill:#21262d,stroke:#f85149,stroke-width:2px,color:#e6edf3;",
        "  classDef skipped fill:#21262d,stroke:#d29922,stroke-width:2px,color:#e6edf3;",
        "  classDef running fill:#21262d,stroke:#58a6ff,stroke-width:2px,color:#e6edf3;",
        "  classDef pending fill:#161b22,stroke:#484f58,stroke-width:2px,color:#8b949e;",
    ]
    P('<pre class="mermaid arch">' + "\n".join(g) + "</pre>")
    P("<p class=muted>The Planner's DAG for this run. Border colour = status: "
      "green complete · red failed · amber skipped · blue running. "
      "Arrows = data dependencies between skills.</p>")

    # browser nodes — path + actions + screenshots
    browser_nodes = [n for n in nodes if n.get("skill") == "browser"]
    # 3 · path
    P("<h2>3 · Browser path chosen</h2>")
    if browser_nodes:
        P("<div class=dag>")
        for n in browser_nodes:
            o = (n.get("result") or {}).get("output") or {}
            ec = (n.get("result") or {}).get("error_code")
            path = ec or o.get("path") or "—"
            P(f"""<div class=node><span class=id>{_esc(n.get('node_id'))}</span>
                  <span class=skill>🌐 path = <b>{_esc(path)}</b></span>
                  <span class=from>{_esc((o.get('final_url') or '')[:90])}</span>
                  <span class=badge style="background:#0969da">{_esc(o.get('turns') or 0)} turns</span></div>""")
        P("</div>")
    else:
        P("<div class=goal class=muted>no browser node in this run</div>")

    # 4 · actions
    P("<h2>4 · Browser actions taken</h2>")
    any_actions = False
    for n in browser_nodes:
        o = (n.get("result") or {}).get("output") or {}
        acts = o.get("actions") or []
        if not acts:
            continue
        any_actions = True
        P(f"<p class=muted>{_esc(n.get('node_id'))} — {len(acts)} turn(s):</p><pre>")
        for a in acts:
            t = a.get("turn"); aa = a.get("actions"); oc = a.get("outcome")
            P(_esc(f"turn {t}: {json.dumps(aa)}  → {oc}") + "\n")
        P("</pre>")
    if not any_actions:
        P("<div class=goal class=muted>no per-turn actions recorded (extract path makes none)</div>")

    # 5 · screenshots
    P("<h2>5 · Screenshots (what the agent saw)</h2>")
    shots = sorted(glob.glob(str(sid_dir / "browser" / "**" / "turn_*_raw.png"), recursive=True))
    if shots:
        P("<div class=shots>")
        for s in shots[:12]:
            sp = Path(s)
            cap = "/".join(sp.parts[-3:])
            P(f"<div class=shot><img src='{_img_data_uri(sp)}'><div class=cap>{_esc(cap)}</div></div>")
        P("</div>")
        if len(shots) > 12:
            P(f"<p class=muted>… and {len(shots) - 12} more in the session folder</p>")
    else:
        P("<div class=goal class=muted>no screenshots (extract path takes none)</div>")

    # 5b · accessibility tree (a11y legend per turn) — what the agent navigated
    P("<h2>5b · Accessibility tree (what the agent navigated)</h2>")
    legends = sorted(glob.glob(str(sid_dir / "browser" / "**" / "turn_*_legend.txt"),
                               recursive=True))
    if legends:
        P("<p class=muted>On the a11y path the driver enumerates every interactive "
          "element on the page into this numbered legend; the model then picks marks "
          "to click or type into (e.g. <code>click(21)</code> = the Language filter). "
          "Expand a turn to see the exact tree it reasoned over.</p>")
        for lp in legends[:12]:
            p = Path(lp)
            label = "/".join(p.parts[-3:])
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                txt = ""
            n_el = txt.count(chr(10)) + 1 if txt.strip() else 0
            if not txt.strip():
                txt = ("(empty legend — the page exposed no enumerable interactive "
                       "elements; this is exactly when the cascade escalates to the "
                       "vision layer)")
            P(f"<details><summary>{_esc(label)} — {n_el} elements</summary>"
              f"<pre>{_esc(txt[:6000])}</pre></details>")
        if len(legends) > 12:
            P(f"<p class=muted>… and {len(legends) - 12} more legend files in the "
              f"session folder</p>")
    else:
        P("<div class=goal class=muted>no a11y legend (extract / deterministic "
          "path produces none)</div>")

    # 6 · extracted data (distiller)
    P("<h2>6 · Extracted data (distiller output)</h2>")
    distillers = [n for n in nodes if n.get("skill") == "distiller"
                  and (n.get("result") or {}).get("output")]
    if distillers:
        o = (distillers[-1].get("result") or {}).get("output") or {}
        P(f"<pre>{_esc(json.dumps(o, indent=2)[:4000])}</pre>")
    else:
        P("<div class=goal class=muted>no distiller output</div>")

    # 7 · final comparison table
    P("<h2>7 · Final comparison table</h2>")
    table_rows = []
    for n in reversed(nodes):
        if n.get("skill") != "distiller":
            continue
        o = (n.get("result") or {}).get("output") or {}
        fields = o.get("fields") or o
        # Find the first value that is a list-of-dicts — works for any
        # comparison key name (top_models, planets, games, items, ...).
        items = None
        if isinstance(fields, dict):
            for v in fields.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    items = v
                    break
        if isinstance(items, list) and items and isinstance(items[0], dict):
            table_rows = items
            break
    if table_rows:
        cols = list(table_rows[0].keys())
        P("<table><tr>" + "".join(f"<th>{_esc(c)}</th>" for c in cols) + "</tr>")
        for it in table_rows:
            P("<tr>" + "".join(f"<td>{_esc(it.get(c, ''))}</td>" for c in cols) + "</tr>")
        P("</table>")
    else:
        P("<div class=goal class=muted>no structured table found in distiller output</div>")

    # final answer (formatter)
    fmt = [n for n in nodes if n.get("skill") == "formatter"
           and (n.get("result") or {}).get("output")]
    if fmt:
        fa = (fmt[-1].get("result") or {}).get("output", {}).get("final_answer")
        if fa:
            P(f"<p class=muted>Formatter's final answer:</p><div class=final>{_esc(fa)}</div>")

    # 8 · turn count + cost summary — measured in tokens/turns (free-tier $≈0)
    P("<h2>8 · Turn count &amp; cost summary</h2>")
    browser_turns = sum(int(((b.get("result") or {}).get("output") or {}).get("turns") or 0)
                        for b in browser_nodes)
    cost = _gateway_cost_by_agent(sid)
    tok_rows = []
    tin = tout = tcalls = 0
    tdollars = 0.0
    if cost:
        for skill, entries in cost.items():
            ci = co = cc = 0; cd = 0.0; provs = set()
            for e in entries:
                ci += e.get("in_tok", 0); co += e.get("out_tok", 0)
                cc += e.get("calls", 0); cd += e.get("dollars", 0.0)
                if e.get("provider"): provs.add(e["provider"])
            tin += ci; tout += co; tcalls += cc; tdollars += cd
            tok_rows.append((skill, ", ".join(sorted(provs)), cc, ci, co, cd))

    P("<p>"
      f"<span class=pill>{len(nodes)} nodes</span>"
      f"<span class=pill>{len(browser_nodes)} browser run(s)</span>"
      f"<span class=pill>{browser_turns} browser turns</span>"
      f"<span class=pill>{total_elapsed:.1f}s wall</span>"
      + (f"<span class=pill>{tcalls} LLM calls</span>"
         f"<span class=pill>{tin:,} tokens in</span>"
         f"<span class=pill>{tout:,} tokens out</span>"
         f"<span class=pill>${tdollars:.6f}</span>" if cost else "")
      + "</p>")
    P("<p class=muted>Dollar cost is near <b>$0</b> because calls run on "
      "<b>free-tier</b> providers (Gemini is $0/token; Groq bills a few cents). "
      "For a free-tier agent the real cost is <b>tokens and turns</b>, below.</p>")

    if tok_rows:
        P("<table><tr><th>skill</th><th>provider</th><th class=num>calls</th>"
          "<th class=num>tokens in</th><th class=num>tokens out</th>"
          "<th class=num>$</th></tr>")
        for skill, prov, c, i, o, d in sorted(tok_rows, key=lambda r: -(r[3] + r[4])):
            P(f"<tr><td>{SKILL_ICON.get(skill,'•')} {_esc(skill)}</td><td>{_esc(prov)}</td>"
              f"<td class=num>{c}</td><td class=num>{i:,}</td><td class=num>{o:,}</td>"
              f"<td class=num>{d:.6f}</td></tr>")
        P(f"<tr><td><b>TOTAL</b></td><td></td><td class=num><b>{tcalls}</b></td>"
          f"<td class=num><b>{tin:,}</b></td><td class=num><b>{tout:,}</b></td>"
          f"<td class=num><b>{tdollars:.6f}</b></td></tr></table>")
    else:
        P("<p class=muted>(Per-skill token ledger unavailable — start the V9 gateway "
          "on :8109 before generating the report to include token counts.)</p>")

    # per-node timing (always available from saved state, no gateway needed)
    P("<h3>Per-node timing</h3>")
    P("<table><tr><th>node</th><th>skill</th><th>status</th><th>provider</th>"
      "<th class=num>elapsed (s)</th></tr>")
    for nid, sk, st, pv, el, co in rows:
        col = STATUS_COLOR.get(st, "#888")
        P(f"<tr><td><code>{_esc(nid)}</code></td><td>{SKILL_ICON.get(sk,'•')} {_esc(sk)}</td>"
          f"<td style='color:{col};font-weight:600'>{_esc(st)}</td><td>{_esc(pv)}</td>"
          f"<td class=num>{el:.1f}</td></tr>")
    P("</table>")

    P("<p class=muted style='margin-top:30px'>Generated by report.py — reads "
      "state that flow.py wrote; no orchestrator changes.</p></div>")
    # Mermaid renders the .mermaid block into an SVG workflow graph. ESM import
    # at end-of-body so the graph element already exists when it runs.
    P("""<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({
    startOnLoad: true, theme: 'base', securityLevel: 'loose',
    themeVariables: { fontFamily: 'Segoe UI, Roboto, sans-serif', fontSize: '15px', lineColor: '#94a3b8' },
    flowchart: { useMaxWidth: true, curve: 'basis', nodeSpacing: 55, rankSpacing: 80, padding: 14 }
  });
</script></html>""")

    out = SESSIONS.parent.parent.parent / f"replay_{sid}.html"
    out.write_text("".join(parts), encoding="utf-8")
    return out


def main() -> None:
    if len(sys.argv) > 1:
        sid = sys.argv[1]
    else:
        cand = sorted(SESSIONS.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not cand:
            raise SystemExit("no sessions found")
        sid = cand[0].name
    out = build(sid)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
