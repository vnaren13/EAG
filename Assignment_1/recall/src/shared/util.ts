/** Stable 32-bit FNV-1a hash → base36 string. */
export function hashId(input: string): string {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36);
}

/**
 * Normalize text for content-hashing: lowercase, collapse whitespace, drop
 * punctuation. Two captures of the same article (different scroll position,
 * different ad load) should hash to the same id.
 */
export function contentHash(text: string): string {
  const norm = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 8000); // first 8k chars is enough for stable identification
  return hashId(norm);
}

/**
 * Tokenize text for BM25. Lowercase, alphanumeric runs, drop short tokens
 * and stopwords. Returns an array preserving order (caller can build a
 * frequency map if it needs term-frequency).
 */
export function tokenize(text: string, minLen = 3): string[] {
  const tokens: string[] = [];
  const re = /[a-z0-9]+/g;
  const lower = text.toLowerCase();
  let m: RegExpExecArray | null;
  while ((m = re.exec(lower)) !== null) {
    const t = m[0];
    if (t.length < minLen) continue;
    if (STOPWORDS.has(t)) continue;
    tokens.push(t);
  }
  return tokens;
}

/** Hostname extraction with safe fallback. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/**
 * Check whether a hostname is excluded by a list of suffix patterns.
 * "google.com" matches "mail.google.com" and "google.com".
 */
export function hostExcluded(host: string, excluded: readonly string[]): boolean {
  if (!host) return false;
  const h = host.toLowerCase();
  for (const pat of excluded) {
    const p = pat.trim().toLowerCase();
    if (!p) continue;
    if (h === p) return true;
    if (h.endsWith('.' + p)) return true;
  }
  return false;
}

/** Sleep helper for tests / debounce. */
export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** Format a timestamp as a short relative string ("3d ago"). */
export function relativeTime(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 0) return 'in the future';
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  const yr = Math.floor(day / 365);
  return `${yr}y ago`;
}

/** Escape HTML. Used in popup snippet rendering. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Compact English stopword list. Kept small on purpose — BM25 already
 * down-weights common words via IDF, so the stopword list is mostly here
 * to shrink the inverted index, not to do linguistic work.
 */
const STOPWORDS = new Set([
  'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'any', 'can',
  'had', 'her', 'his', 'one', 'our', 'out', 'their', 'they', 'this', 'that',
  'these', 'those', 'with', 'from', 'have', 'has', 'was', 'were', 'will',
  'what', 'when', 'where', 'which', 'who', 'why', 'how', 'into', 'than',
  'then', 'them', 'about', 'after', 'also', 'because', 'been', 'being',
  'before', 'between', 'both', 'each', 'just', 'more', 'most', 'other',
  'over', 'same', 'some', 'such', 'through', 'under', 'very', 'would',
  'should', 'could', 'while', 'your', 'there', 'here', 'said',
]);
