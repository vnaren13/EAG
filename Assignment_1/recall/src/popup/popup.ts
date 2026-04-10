import type { RecallMessage, RecallResponse, SearchHit, Stats } from '@/shared/types';
import { escapeHtml, relativeTime } from '@/shared/util';

/**
 * Popup app.
 *
 * Single-page UI: a search input on top, a results list below, a footer with
 * stats. Search is debounced, ranked by BM25 (in the service worker), and
 * results land back here as SearchHit[]. Clicking a hit opens its URL in a
 * new tab.
 *
 * Empty state shows the recently-saved articles so the popup is never
 * blank — even on first install (which shows an onboarding card instead).
 */

const searchEl = document.getElementById('search') as HTMLInputElement;
const resultsEl = document.getElementById('results') as HTMLElement;
const statsLineEl = document.getElementById('stats-line') as HTMLElement;
const openOptionsBtn = document.getElementById('open-options') as HTMLButtonElement;

let debounceTimer: number | null = null;
let lastQueryToken = 0;

searchEl.addEventListener('input', () => {
  if (debounceTimer !== null) clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(runSearch, 80);
});

searchEl.addEventListener('keydown', (e) => {
  // Down/Up arrows move focus into the result list, Enter opens the focused hit.
  if (e.key === 'ArrowDown') {
    const first = resultsEl.querySelector<HTMLAnchorElement>('a.hit');
    if (first) {
      e.preventDefault();
      first.focus();
    }
  }
});

resultsEl.addEventListener('keydown', (e) => {
  const target = e.target as HTMLElement | null;
  if (!target?.classList.contains('hit')) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    (target.nextElementSibling as HTMLElement | null)?.focus();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    const prev = target.previousElementSibling as HTMLElement | null;
    if (prev?.classList.contains('hit')) prev.focus();
    else searchEl.focus();
  }
});

openOptionsBtn.addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

async function runSearch(): Promise<void> {
  const q = searchEl.value.trim();
  const token = ++lastQueryToken;

  if (q.length === 0) {
    await renderRecent();
    return;
  }

  resultsEl.innerHTML = `<div class="loading">Searching…</div>`;

  const res = await sendMessage({ type: 'search', payload: { query: q } });
  // Drop stale responses if user kept typing.
  if (token !== lastQueryToken) return;

  if (res.type !== 'search:ok') {
    resultsEl.innerHTML = `<div class="no-results">Error: ${escapeHtml(
      res.type === 'error' ? res.message : 'unknown',
    )}</div>`;
    return;
  }

  if (res.hits.length === 0) {
    resultsEl.innerHTML = `
      <div class="no-results">
        No matches.
        <span class="hint">Try fewer or more general words.</span>
      </div>
    `;
    statsLineEl.textContent = `0 hits · ${res.tookMs.toFixed(0)} ms`;
    return;
  }

  resultsEl.innerHTML = res.hits.map(renderHit).join('');
  statsLineEl.textContent = `${res.hits.length} hits · ${res.tookMs.toFixed(0)} ms`;
}

async function renderRecent(): Promise<void> {
  // No query → show recent articles + stats.
  const [statsRes, listRes] = await Promise.all([
    sendMessage({ type: 'stats' }),
    sendMessage({ type: 'list', payload: { offset: 0, limit: 12 } }),
  ]);

  if (statsRes.type === 'stats:ok') updateStatsFooter(statsRes.stats);

  if (listRes.type !== 'list:ok' || listRes.docs.length === 0) {
    resultsEl.innerHTML = `
      <div class="empty">
        Recall is ready.
        <span class="hint">Read a few articles in your browser — they'll show up here.</span>
      </div>
    `;
    return;
  }

  resultsEl.innerHTML = listRes.docs
    .map((d) => ({
      doc: d,
      score: 0,
      snippet: escapeHtml(d.text.slice(0, 220).trim()) + '…',
      matchedTerms: [],
    }))
    .map((h) => renderHit(h as SearchHit))
    .join('');
}

function renderHit(h: SearchHit): string {
  return `
    <a class="hit" href="${escapeAttr(h.doc.url)}" target="_blank" rel="noopener" tabindex="0">
      <div class="title">${escapeHtml(h.doc.title)}</div>
      <div class="meta">
        <span class="host">${escapeHtml(h.doc.host)}</span>
        <span>·</span>
        <span>${escapeHtml(relativeTime(h.doc.savedAt))}</span>
      </div>
      <div class="snippet">${h.snippet}</div>
    </a>
  `;
}

function updateStatsFooter(stats: Stats): void {
  if (stats.totalDocs === 0) {
    statsLineEl.textContent = 'Empty — start reading';
    return;
  }
  const tokens = stats.totalTokens >= 1000
    ? `${(stats.totalTokens / 1000).toFixed(0)}k tokens`
    : `${stats.totalTokens} tokens`;
  statsLineEl.textContent = `${stats.totalDocs} articles · ${tokens}`;
}

function sendMessage(msg: RecallMessage): Promise<RecallResponse> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response: RecallResponse | undefined) => {
      const lastErr = chrome.runtime.lastError;
      if (lastErr) {
        reject(new Error(lastErr.message));
        return;
      }
      if (!response) {
        reject(new Error('No response from service worker'));
        return;
      }
      resolve(response);
    });
  });
}

function escapeAttr(s: string): string {
  return escapeHtml(s);
}

// Initial render: recent articles + stats.
renderRecent();
