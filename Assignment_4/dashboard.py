"""News Diffractor — Prefab dashboard.

Run via: prefab serve dashboard.py --port 5175 --reload

The MCP server touches this file after every CRUD write so `prefab serve --reload`
re-renders with fresh data from data/diffractions.json.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from prefab_ui import PrefabApp
from prefab_ui.components import (
    Accordion,
    AccordionItem,
    Alert,
    AlertDescription,
    AlertTitle,
    Badge,
    BlockQuote,
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
    Code,
    Column,
    Container,
    DataTable,
    DataTableColumn,
    Dot,
    Grid,
    GridItem,
    H1,
    H2,
    H3,
    H4,
    Heading,
    HoverCard,
    Image,
    Lead,
    Link,
    Markdown,
    Mermaid,
    Metric,
    Muted,
    P,
    Progress,
    Ring,
    Row,
    Separator,
    Small,
    Tab,
    Tabs,
    Text,
    Tooltip,
)
from prefab_ui.components.charts import (
    AreaChart,
    BarChart,
    ChartSeries,
    PieChart,
    Sparkline,
)

DATA_FILE = Path(__file__).parent / "data" / "diffractions.json"

KEYWORD_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "have", "will",
    "would", "could", "should", "into", "their", "they", "them", "what",
    "when", "which", "where", "while", "after", "before", "about", "more",
    "than", "over", "such", "some", "very", "just", "also", "been", "were",
    "said", "says", "back", "amid", "year", "years",
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _load_diffractions() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    raw = DATA_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return json.loads(raw).get("diffractions", [])


def _keyword_diff(articles: list[dict]) -> tuple[list[str], dict[str, list[str]]]:
    per_outlet: dict[str, set[str]] = {}
    for a in articles:
        words = re.findall(r"[A-Za-z]{4,}", a.get("headline", "").lower())
        per_outlet[a["outlet"]] = {w for w in words if w not in KEYWORD_STOPWORDS}
    if not per_outlet:
        return [], {}
    counts: Counter[str] = Counter()
    for words in per_outlet.values():
        counts.update(words)
    threshold = max(2, int(len(articles) * 0.6 + 0.999))
    shared = [w for w, c in counts.most_common() if c >= threshold]
    divergent = {
        outlet: [w for w in words if counts[w] == 1][:3]
        for outlet, words in per_outlet.items()
    }
    return shared[:8], divergent


def _outlet_color(outlet: str) -> str:
    """Stable variant per outlet for visual rhythm."""
    palette = ["info", "success", "warning", "destructive", "default", "secondary", "outline", "ghost"]
    return palette[hash(outlet) % len(palette)]


def _short(s: str, n: int = 140) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _format_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return iso[:10] if len(iso) >= 10 else iso


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def _build_hero() -> None:
    with Column(gap=2, css_class="text-center py-6"):
        H1(
            "📰 News Diffractor",
            css_class="text-5xl font-bold bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 bg-clip-text text-transparent",
        )
        Lead(
            "See how multiple outlets frame the same story. "
            "Local-first. No API keys. Powered by FastMCP × Prefab UI.",
            css_class="text-lg",
        )


def _build_metrics(diffractions: list[dict]) -> None:
    total = len(diffractions)
    all_outlets = [a.get("outlet") for d in diffractions for a in d.get("articles", [])]
    unique_outlets = sorted({o for o in all_outlets if o})
    total_articles = sum(len(d.get("articles", [])) for d in diffractions)
    all_tags = [t for d in diffractions for t in d.get("tags", [])]
    most_tag = Counter(all_tags).most_common(1)
    most_tag_label = most_tag[0][0] if most_tag else "—"
    framing_count = sum(
        len(a.get("framing_notes", [])) for d in diffractions for a in d.get("articles", [])
    )

    with Grid(min_column_width="220px", gap=4):
        Metric(label="Diffractions saved", value=str(total), description="story comparisons")
        Metric(
            label="Outlets covered",
            value=str(len(unique_outlets)),
            description=", ".join(unique_outlets[:3]) + ("…" if len(unique_outlets) > 3 else ""),
        )
        Metric(
            label="Articles analysed",
            value=str(total_articles),
            description=f"{framing_count} framing notes",
        )
        Metric(
            label="Top tag",
            value="#" + most_tag_label if most_tag_label != "—" else "—",
            description=f"{Counter(all_tags).get(most_tag_label, 0)} uses" if most_tag_label != "—" else "no tags yet",
        )


def _build_outlet_pill(outlet: str, favicon_url: str | None = None) -> None:
    """Outlet name pill with an HoverCard showing its details (popovers are gold)."""
    with HoverCard(open_delay=200, close_delay=80):
        with Row(gap=2, align="center", css_class="cursor-default"):
            if favicon_url:
                Image(src=favicon_url, alt=outlet, width="20px", height="20px")
            Text(outlet, bold=True, css_class="text-sm")
        # HoverCard content shown below (children rendered in popover)
        with Card(css_class="p-3 max-w-xs"):
            with Row(gap=2, align="center"):
                if favicon_url:
                    Image(src=favicon_url, alt=outlet, width="32px", height="32px")
                Column(gap=0)
                H4(outlet)
            Muted("Curated outlet in News Diffractor", css_class="text-xs mt-2")


def _build_article_card(article: dict, idx: int) -> None:
    with Card(
        css_class=(
            "min-w-80 max-w-96 flex-shrink-0 transition-all hover:shadow-xl "
            "hover:scale-[1.01] border-l-4"
        )
    ):
        with CardHeader(css_class="pb-3"):
            with Row(gap=2, align="center", css_class="mb-1"):
                if article.get("favicon_url"):
                    Image(
                        src=article["favicon_url"],
                        alt=article.get("outlet", ""),
                        width="28px",
                        height="28px",
                    )
                Text(article.get("outlet", "Unknown"), bold=True, css_class="text-base")
                Badge(label=f"#{idx + 1}", variant="outline", css_class="ml-auto")
            CardTitle(_short(article.get("headline", ""), 120), css_class="text-base leading-snug")
            if article.get("published_at"):
                CardDescription(_format_date(article["published_at"]), css_class="text-xs")
        with CardContent(css_class="text-sm space-y-3"):
            snippet = article.get("lead_snippet", "")
            if snippet:
                BlockQuote(_short(snippet, 280), italic=True, css_class="text-xs leading-relaxed")
            framing = article.get("framing_notes", [])
            if framing:
                with Row(gap=1, css_class="flex-wrap"):
                    for note in framing[:5]:
                        with Tooltip(content=f"Agent's framing note for {article.get('outlet')}", side="top"):
                            Badge(label=note, variant="secondary", css_class="text-xs")
        with CardFooter(css_class="pt-2"):
            url = article.get("url")
            if url:
                Link("Read full article →", href=url, target="_blank", css_class="text-xs underline")


def _build_diffraction_detail(d: dict, featured: bool = False) -> None:
    shared, divergent = _keyword_diff(d.get("articles", []))
    n_outlets = len(d.get("articles", []))

    border = "border-t-4 border-indigo-500" if featured else ""
    with Card(css_class=f"mb-6 {border} shadow-lg"):
        with CardHeader():
            with Row(gap=3, align="center", justify="between"):
                with Column(gap=1):
                    if featured:
                        with Row(gap=2, align="center"):
                            Dot(css_class="bg-indigo-500 animate-pulse")
                            Small("LATEST", css_class="text-indigo-500 font-bold tracking-wider")
                    CardTitle(d.get("topic", ""), css_class="text-2xl")
                    CardDescription(
                        f"{n_outlets} outlets · fetched {_format_date(d.get('fetched_at', ''))}"
                    )
                with Row(gap=1, css_class="flex-wrap"):
                    for tag in d.get("tags", []):
                        Badge(label=f"#{tag}", variant="info", css_class="text-xs")

        with CardContent(css_class="space-y-6"):
            # Article cards in a horizontal scroller — feels like a real comparison.
            with Row(gap=4, css_class="overflow-x-auto pb-4 -mx-2 px-2"):
                for idx, article in enumerate(d.get("articles", [])):
                    _build_article_card(article, idx)

            # Synthesis as a polished Markdown card.
            if d.get("synthesis"):
                with Alert(variant="info"):
                    AlertTitle("Synthesis")
                    Markdown(d["synthesis"])

            # Shared keywords (info badges) and divergent keywords (per-outlet).
            if shared:
                with Column(gap=2):
                    H4("Shared across outlets")
                    with Row(gap=2, css_class="flex-wrap"):
                        for word in shared:
                            Badge(label=word, variant="info", css_class="text-xs")

            divergent_nonempty = {k: v for k, v in divergent.items() if v}
            if divergent_nonempty:
                with Column(gap=2):
                    H4("Divergent emphasis (unique-per-outlet)")
                    with Column(gap=2):
                        for outlet, words in divergent_nonempty.items():
                            with Row(gap=2, align="center"):
                                Text(outlet + ":", bold=True, css_class="w-32 text-sm")
                                with Row(gap=1, css_class="flex-wrap"):
                                    for word in words:
                                        Badge(label=word, variant="outline", css_class="text-xs")


# ---------------------------------------------------------------------------
# Tab panels
# ---------------------------------------------------------------------------

def _panel_latest(diffractions: list[dict]) -> None:
    with Column(gap=4, css_class="pt-4"):
        if not diffractions:
            _build_empty_state()
            return
        latest = diffractions[0]
        _build_diffraction_detail(latest, featured=True)


def _panel_analytics(diffractions: list[dict]) -> None:
    """Charts that tell the story of your diffraction history."""
    with Column(gap=6, css_class="pt-4"):
        if not diffractions:
            with Alert(variant="info"):
                AlertTitle("No analytics yet")
                AlertDescription("Run your first diffraction and these charts come alive.")
            return

        # ---- Outlet frequency (PieChart)
        outlet_counts = Counter(
            a.get("outlet", "?") for d in diffractions for a in d.get("articles", [])
        )
        outlet_data = [{"outlet": k, "count": v} for k, v in outlet_counts.most_common()]

        # ---- Framing notes per outlet (BarChart)
        framing_per_outlet: dict[str, int] = {}
        for d in diffractions:
            for a in d.get("articles", []):
                framing_per_outlet[a.get("outlet", "?")] = framing_per_outlet.get(
                    a.get("outlet", "?"), 0
                ) + len(a.get("framing_notes", []))
        framing_data = [
            {"outlet": k, "framings": v}
            for k, v in sorted(framing_per_outlet.items(), key=lambda x: -x[1])
        ]

        # ---- Tag distribution (BarChart)
        tag_counts = Counter(t for d in diffractions for t in d.get("tags", []))
        tag_data = [{"tag": k, "uses": v} for k, v in tag_counts.most_common(8)]

        # ---- Diffractions over time (Sparkline)
        date_counts: Counter[str] = Counter()
        for d in diffractions:
            ts = d.get("created_at", "")[:10]
            if ts:
                date_counts[ts] += 1
        sparkline_data = [v for _, v in sorted(date_counts.items())]
        if not sparkline_data:
            sparkline_data = [len(diffractions)]

        # ---- Layout
        with Grid(min_column_width="320px", gap=6):
            with Card():
                with CardHeader():
                    CardTitle("Outlet coverage")
                    CardDescription("How often each outlet shows up in your saves")
                with CardContent():
                    PieChart(
                        data=outlet_data,
                        data_key="count",
                        name_key="outlet",
                        height=260,
                        show_label=True,
                        show_legend=True,
                        animate=True,
                    )
            with Card():
                with CardHeader():
                    CardTitle("Framing notes per outlet")
                    CardDescription("Total framings the agent has tagged for each outlet")
                with CardContent():
                    BarChart(
                        data=framing_data,
                        series=[ChartSeries(data_key="framings", label="Framings", color="#a855f7")],
                        x_axis="outlet",
                        height=260,
                        bar_radius=8,
                        show_legend=False,
                        show_grid=True,
                        animate=True,
                    )
            with Card():
                with CardHeader():
                    CardTitle("Topic tags")
                    CardDescription("Most-used tags across your diffractions")
                with CardContent():
                    if tag_data:
                        BarChart(
                            data=tag_data,
                            series=[ChartSeries(data_key="uses", label="Uses", color="#0ea5e9")],
                            x_axis="tag",
                            height=260,
                            bar_radius=8,
                            horizontal=True,
                            show_legend=False,
                            animate=True,
                        )
                    else:
                        Muted("No tags yet — add them via manage_diffraction.")
            with Card():
                with CardHeader():
                    CardTitle("Cadence")
                    CardDescription("Diffractions saved over time")
                with CardContent():
                    with Column(gap=4):
                        Sparkline(
                            data=sparkline_data,
                            height=80,
                            variant="success",
                            curve="smooth",
                            fill=True,
                            mode="line",
                        )
                        with Row(gap=4, justify="around"):
                            Metric(label="Days active", value=str(len(date_counts)))
                            Metric(label="Total saves", value=str(len(diffractions)))


def _panel_archive(diffractions: list[dict]) -> None:
    with Column(gap=4, css_class="pt-4"):
        if len(diffractions) <= 1:
            with Alert(variant="info"):
                AlertTitle("Just getting started")
                AlertDescription(
                    "Save more diffractions and they'll all live here, expandable, "
                    "searchable, sortable."
                )
            return

        # Searchable / sortable DataTable summary
        rows = [
            {
                "topic": d.get("topic", ""),
                "outlets": ", ".join(a.get("outlet", "") for a in d.get("articles", [])),
                "tags": ", ".join("#" + t for t in d.get("tags", [])),
                "synthesis": "✅" if d.get("synthesis") else "—",
                "fetched_at": _format_date(d.get("fetched_at", "")),
            }
            for d in diffractions
        ]
        with Card(css_class="mb-6"):
            with CardHeader():
                CardTitle("All diffractions")
                CardDescription("Searchable & sortable")
            with CardContent():
                DataTable(
                    columns=[
                        DataTableColumn(key="topic", header="Topic", sortable=True, min_width="240px"),
                        DataTableColumn(key="outlets", header="Outlets"),
                        DataTableColumn(key="tags", header="Tags"),
                        DataTableColumn(key="synthesis", header="✎", width="60px", align="center"),
                        DataTableColumn(key="fetched_at", header="Fetched", sortable=True, width="120px"),
                    ],
                    rows=rows,
                    search=True,
                    paginated=True,
                    page_size=8,
                )

        # Expandable Accordion of full details for each
        H3("Browse details", css_class="mt-6")
        with Accordion(multiple=True, collapsible=True):
            for d in diffractions[1:]:
                title = (
                    f"{d.get('topic', '')}  ·  "
                    f"{len(d.get('articles', []))} outlets  ·  "
                    f"{_format_date(d.get('fetched_at', ''))}"
                )
                with AccordionItem(title=title, value=d.get("id", "") or title):
                    _build_diffraction_detail(d)


def _panel_how_it_works() -> None:
    with Column(gap=6, css_class="pt-4"):
        with Card():
            with CardHeader():
                CardTitle("The pipeline")
                CardDescription(
                    "One natural-language prompt forces the agent to use all three tools."
                )
            with CardContent():
                Mermaid(chart=(
                    "flowchart LR\n"
                    "    U[👤 You] -->|prompt| A[🤖 Agent]\n"
                    "    A -->|1| F[fetch_coverage]\n"
                    "    F -->|RSS + trafilatura| O[📰 5 outlets]\n"
                    "    O -->|articles| A\n"
                    "    A -->|2 reasons + writes synthesis| M[manage_diffraction]\n"
                    "    M -->|JSON CRUD| D[(💾 diffractions.json)]\n"
                    "    A -->|3| S[show_diffractor]\n"
                    "    S -->|webbrowser.open| B[🌐 This dashboard]\n"
                    "    D -.->|prefab serve --reload| B"
                ))

        with Card():
            with CardHeader():
                CardTitle("Try it")
                CardDescription("Paste this exact prompt into your MCP client.")
            with CardContent(css_class="space-y-3"):
                Code(
                    "Diffract today's coverage of <topic> across major outlets, "
                    "compare their framing and headlines, save the analysis with a "
                    "Markdown synthesis, then show me my news diffractor dashboard.",
                    language="text",
                )
                Muted(
                    "Replace `<topic>` with anything in the news today — "
                    "e.g. \"the OpenAI EU regulatory probe\", \"India's election results\", "
                    "\"the latest Fed rate decision\".",
                )

        with Grid(min_column_width="280px", gap=4):
            with Card():
                with CardHeader():
                    CardTitle("Tool 1 · fetch_coverage")
                    CardDescription("Internet")
                with CardContent():
                    P("Pulls coverage of one topic from a curated set of major outlets via direct RSS.")
                    Muted("BBC, The Guardian, Al Jazeera, TechCrunch, The Verge, Times of India, The Hindu, Indian Express, Hacker News, Ars Technica.")
            with Card():
                with CardHeader():
                    CardTitle("Tool 2 · manage_diffraction")
                    CardDescription("Local-file CRUD")
                with CardContent():
                    P("Single tool, all CRUD ops on data/diffractions.json. Touches dashboard.py to live-reload this view.")
            with Card():
                with CardHeader():
                    CardTitle("Tool 3 · show_diffractor")
                    CardDescription("UI")
                with CardContent():
                    P("Opens this Prefab webapp in your browser. Self-healing — spawns the server on demand.")


def _build_empty_state() -> None:
    with Card(css_class="border-dashed border-2"):
        with CardContent(css_class="py-12 text-center space-y-6"):
            H2("👋 Ready when you are")
            Lead(
                "No diffractions saved yet. Pop into your MCP client and try this prompt:",
                css_class="max-w-xl mx-auto",
            )
            Code(
                'Diffract today\'s coverage of "the OpenAI EU regulatory probe" '
                'across major outlets, compare their framing, save the analysis, '
                'then show me my news diffractor dashboard.',
                language="text",
                css_class="text-left max-w-2xl mx-auto",
            )
            with Row(gap=3, justify="center", css_class="pt-2"):
                Badge(label="🌐 Tool 1: fetch_coverage", variant="info")
                Badge(label="💾 Tool 2: manage_diffraction", variant="success")
                Badge(label="📊 Tool 3: show_diffractor", variant="warning")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def build_dashboard() -> PrefabApp:
    diffractions = _load_diffractions()
    diffractions.sort(key=lambda d: d.get("created_at", ""), reverse=True)

    with Container(css_class="max-w-6xl mx-auto p-6 space-y-6") as view:
        _build_hero()
        _build_metrics(diffractions)

        if not diffractions:
            _build_empty_state()
            with Separator(spacing=4):
                pass
            _panel_how_it_works()
        else:
            with Tabs(name="main", value="latest", variant="line"):
                with Tab(title="🌐 Latest", value="latest"):
                    _panel_latest(diffractions)
                with Tab(title="📊 Analytics", value="analytics"):
                    _panel_analytics(diffractions)
                with Tab(title="🗂 Archive", value="archive"):
                    _panel_archive(diffractions)
                with Tab(title="❔ How it works", value="howto"):
                    _panel_how_it_works()

    return PrefabApp(view=view, title="News Diffractor")


app = build_dashboard()
