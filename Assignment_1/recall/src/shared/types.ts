/**
 * Domain types for Recall.
 *
 * Document  — the canonical persisted record (one row in IndexedDB).
 * SearchHit — what the popup renders for each result.
 * Settings  — what the options page persists to chrome.storage.local.
 * Messages  — typed protocol between content/popup/options ↔ service worker.
 */

export interface Document {
  /** Stable, content-derived id. Same article saved twice produces the same id. */
  id: string;
  /** Canonical URL the user was on when this was captured. */
  url: string;
  /** Hostname only, for grouping/filtering ("nytimes.com"). */
  host: string;
  /** Article title from Readability or document.title. */
  title: string;
  /** Optional byline. */
  byline?: string;
  /** Plain-text article body, post-Readability. */
  text: string;
  /** Token count of `text`, used by BM25 length normalization. */
  length: number;
  /** ms since epoch when first captured. */
  savedAt: number;
}

export interface SearchHit {
  doc: Document;
  /** BM25 score. */
  score: number;
  /** Snippet of text around the highest-scoring matched terms, with markers. */
  snippet: string;
  /** Distinct query terms that matched in this doc, lowercased. */
  matchedTerms: string[];
}

export interface Settings {
  /** When true, content script does not capture. */
  paused: boolean;
  /**
   * Excluded hostnames (or wildcard suffixes). One per line in the UI,
   * stored as an array. Matched against `host` of the current page.
   */
  excludedHosts: string[];
  /** Minimum article length (chars) to bother saving. */
  minArticleChars: number;
}

export const DEFAULT_SETTINGS: Settings = {
  paused: false,
  excludedHosts: [
    'mail.google.com',
    'docs.google.com',
    'calendar.google.com',
    'github.com', // huge files / non-articles dominate
    'localhost',
  ],
  minArticleChars: 600,
};

// ---------- Message protocol ----------

export type RecallMessage =
  | { type: 'capture'; payload: CapturePayload }
  | { type: 'search'; payload: { query: string; limit?: number } }
  | { type: 'stats' }
  | { type: 'list'; payload: { offset: number; limit: number } }
  | { type: 'delete'; payload: { id: string } }
  | { type: 'deleteAll' }
  | { type: 'export' }
  | { type: 'ping' };

export interface CapturePayload {
  url: string;
  title: string;
  byline?: string;
  text: string;
}

export type RecallResponse =
  | { type: 'capture:ok'; doc: Document; firstSave: boolean }
  | { type: 'capture:skipped'; reason: string }
  | { type: 'search:ok'; hits: SearchHit[]; tookMs: number }
  | { type: 'stats:ok'; stats: Stats }
  | { type: 'list:ok'; docs: Document[]; total: number }
  | { type: 'delete:ok' }
  | { type: 'export:ok'; json: string }
  | { type: 'pong' }
  | { type: 'error'; message: string };

export interface Stats {
  totalDocs: number;
  totalTokens: number;
  oldestSavedAt: number | null;
  newestSavedAt: number | null;
}
