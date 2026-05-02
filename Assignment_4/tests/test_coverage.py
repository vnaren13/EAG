"""Unit tests for tools.coverage — keyword parsing, scoring, favicon URLs.

Network-touching paths are covered by tests/test_e2e.py.
"""
from __future__ import annotations

import types

from tools import coverage


def test_keywords_strips_stopwords_and_short_tokens():
    out = coverage._keywords("The OpenAI EU regulatory probe is on")
    assert "openai" in out
    assert "regulatory" in out
    assert "probe" in out
    assert "the" not in out
    assert "is" not in out
    assert "on" not in out


def test_keywords_lowercases_and_handles_punctuation():
    out = coverage._keywords("Trump's spat with Merz over Iran-war")
    assert "trump" in out
    assert "merz" in out
    assert "iran" in out
    assert "war" in out  # 3 chars, kept
    assert "with" not in out  # stopword
    # digit handling: "5,000" splits into "5" and "000"; both < 3 chars, dropped
    out2 = coverage._keywords("5,000 troops withdrawn from Germany")
    assert "troops" in out2
    assert "withdrawn" in out2
    assert "germany" in out2


def test_matches_counts_distinct_keywords():
    keywords = ["openai", "eu", "regulator", "probe"]
    fake = types.SimpleNamespace(
        title="OpenAI faces EU probe over training data",
        summary="Brussels regulators announced today",
    )
    score = coverage._matches(fake, keywords)
    assert score >= 3, f"expected 3+ matches, got {score}"


def test_matches_returns_zero_for_unrelated():
    keywords = ["openai", "regulatory", "probe"]
    fake = types.SimpleNamespace(
        title="Gardening tips for spring",
        summary="how to plant tulips",
    )
    assert coverage._matches(fake, keywords) == 0


def test_favicon_url_uses_google_s2():
    url = coverage._favicon("https://www.bbc.com/news/some-article")
    assert "google.com/s2/favicons" in url
    assert "domain=www.bbc.com" in url


def test_outlets_directory_is_keyless_and_curated():
    """Sanity: every outlet has a feed URL and they're not Google-News redirects."""
    for outlet, url in coverage.OUTLETS.items():
        assert url.startswith(("http://", "https://"))
        assert "news.google.com" not in url, f"{outlet} uses Google News redirect"


def test_fetch_coverage_rejects_empty_topic():
    res = coverage.fetch_coverage("the and is")  # all stopwords
    assert "error" in res
