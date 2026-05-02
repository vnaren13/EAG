"""News-coverage fetcher: per-outlet RSS + trafilatura extraction."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
import trafilatura

# Curated outlet → RSS feed. Direct article URLs (no Google News redirects),
# good geographic and ideological spread, all keyless and free.
OUTLETS: dict[str, str] = {
    "BBC": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Times of India": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "The Hindu": "https://www.thehindu.com/feeder/default.rss",
    "Indian Express": "https://indianexpress.com/feed/",
    "Hacker News": "https://hnrss.org/frontpage",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

STOPWORDS = {
    "a", "an", "the", "is", "in", "of", "on", "at", "and", "or", "for", "to",
    "with", "by", "as", "from", "this", "that", "these", "those", "it", "its",
    "be", "been", "are", "was", "were", "have", "has", "had", "do", "does",
    "did", "will", "would", "should", "could", "may", "might", "must",
    "their", "them", "they", "we", "us", "our", "you", "your", "i", "me", "my",
    "he", "she", "his", "her", "him", "today",
}


def _keywords(topic: str) -> list[str]:
    """Lowercased non-stopword tokens of length >= 3."""
    raw = re.findall(r"[A-Za-z0-9]+", topic.lower())
    return [w for w in raw if w not in STOPWORDS and len(w) >= 3]


def _matches(entry: Any, keywords: list[str]) -> int:
    """Score: number of distinct keywords appearing in title+summary."""
    haystack = (
        getattr(entry, "title", "") + " " + getattr(entry, "summary", "")
    ).lower()
    return sum(1 for k in set(keywords) if k in haystack)


def _favicon(url: str) -> str:
    domain = urlparse(url).netloc
    return f"https://www.google.com/s2/favicons?sz=64&domain={domain}"


def _extract_one(outlet: str, feed_url: str, keywords: list[str]) -> dict[str, Any] | None:
    """Fetch one outlet's RSS, find best-matching entry, extract full text.
    Returns None if no match or error.
    """
    try:
        r = httpx.get(feed_url, follow_redirects=True, timeout=12, headers=HEADERS)
        r.raise_for_status()
    except Exception:
        return None

    feed = feedparser.parse(r.text)
    scored = sorted(
        ((_matches(e, keywords), e) for e in feed.entries),
        key=lambda x: x[0],
        reverse=True,
    )
    if not scored or scored[0][0] == 0:
        return None
    best = scored[0][1]

    # Try to extract full text from the article URL.
    full_text = ""
    try:
        art_r = httpx.get(best.link, follow_redirects=True, timeout=15, headers=HEADERS)
        if art_r.status_code == 200:
            full_text = trafilatura.extract(
                art_r.text,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            ) or ""
    except Exception:
        pass

    summary_html = getattr(best, "summary", "") or ""
    summary_text = re.sub(r"<[^>]+>", "", summary_html).strip()
    lead_snippet = (full_text[:500] if full_text else summary_text[:500]).strip()

    return {
        "outlet": outlet,
        "url": best.link,
        "headline": getattr(best, "title", "").strip(),
        "lead_snippet": lead_snippet,
        "full_text": full_text,
        "published_at": getattr(best, "published", ""),
        "favicon_url": _favicon(best.link),
        "match_score": scored[0][0],
    }


def fetch_coverage(
    topic: str,
    max_outlets: int = 5,
    outlets: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch coverage of `topic` from multiple curated news outlets.

    Returns a dict with:
      - topic, fetched_at
      - articles: list of {outlet, url, headline, lead_snippet, full_text,
                           published_at, favicon_url, match_score}
      - count: number of outlets that returned a match
      - skipped: outlets that had no matching article (so the agent knows)

    Notes:
      - full_text is included so the agent can read & reason; only lead_snippet
        gets persisted by manage_diffraction.
      - Matching is keyword-based on RSS title+summary, scored by number of
        distinct keywords hit; best match per outlet is kept.
      - `outlets` lets the agent restrict to a subset (e.g. ["BBC", "Al Jazeera"]).
    """
    keywords = _keywords(topic)
    if not keywords:
        return {"error": f"topic {topic!r} has no usable keywords"}

    targets = outlets or list(OUTLETS.keys())
    targets = [o for o in targets if o in OUTLETS][:max_outlets * 2]  # generous superset

    articles: list[dict[str, Any]] = []
    skipped: list[str] = []

    with ThreadPoolExecutor(max_workers=min(8, len(targets) or 1)) as pool:
        futures = {
            pool.submit(_extract_one, outlet, OUTLETS[outlet], keywords): outlet
            for outlet in targets
        }
        for fut in as_completed(futures):
            outlet = futures[fut]
            result = fut.result()
            if result is None:
                skipped.append(outlet)
            else:
                articles.append(result)

    articles.sort(key=lambda a: a["match_score"], reverse=True)
    articles = articles[:max_outlets]

    return {
        "topic": topic,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "articles": articles,
        "count": len(articles),
        "skipped": skipped,
        "available_outlets": list(OUTLETS.keys()),
    }
