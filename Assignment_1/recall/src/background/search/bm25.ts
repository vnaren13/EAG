import type { Document, SearchHit } from '@/shared/types';
import { CONFIG } from '@/shared/config';
import { tokenize, escapeHtml } from '@/shared/util';

/**
 * In-memory BM25 search index.
 *
 * Lives entirely in the service worker. Rebuilt from Dexie on cold start
 * (the SW dies after ~30s idle), updated incrementally when new documents
 * are captured.
 *
 * BM25 (Okapi) scoring:
 *
 *     score(q, d) = Σ_{t∈q}  IDF(t) · (tf_{t,d} (k1+1)) / (tf_{t,d} + k1 (1 - b + b · |d|/avgdl))
 *
 *     IDF(t)      = ln( (N - df_t + 0.5) / (df_t + 0.5) + 1 )
 *
 * Why BM25 over plain TF-IDF: BM25 saturates term frequency (a word appearing
 * 10× isn't 10× as relevant as appearing once) and normalizes by document
 * length so a 200-word doc isn't penalized vs a 5,000-word doc. Both matter
 * a lot for "find that thing I read."
 *
 * Capacity envelope at v0:
 *   - ~10k documents, average ~500 tokens each, ~50k unique terms.
 *   - Memory: ~5–8 MB for the inverted index. Fine for a service worker.
 *   - Cold-start rebuild: linear in total tokens, ~1–2s for 10k docs.
 *   - Search: O(query_terms · avg_postings_per_term). Sub-millisecond for
 *     typical queries on a 10k corpus.
 *
 * When this stops being good enough we persist the postings to Dexie and
 * load the inverted index lazily; the API of this class doesn't have to
 * change.
 */

interface Posting {
  docId: string;
  tf: number;
}

export class Bm25Index {
  /** term → posting list. */
  private postings = new Map<string, Posting[]>();
  /** term → document frequency (number of docs containing the term). */
  private df = new Map<string, number>();
  /** docId → metadata (length in tokens). The body lives in Dexie. */
  private docLengths = new Map<string, number>();
  /** docId → quick lookup of the Document for hit rendering. */
  private docs = new Map<string, Document>();

  private totalTokens = 0;
  /** Set to true once `rebuild()` has finished at least once. */
  private ready = false;

  /** Number of documents currently indexed. */
  get size(): number {
    return this.docs.size;
  }

  /** Average document length in tokens — needed by BM25. */
  private get avgDocLength(): number {
    return this.docs.size === 0 ? 0 : this.totalTokens / this.docs.size;
  }

  isReady(): boolean {
    return this.ready;
  }

  /**
   * Bulk rebuild from a list of documents. Called on service-worker cold
   * start. Discards any prior in-memory state.
   */
  rebuild(documents: Document[]): void {
    this.postings.clear();
    this.df.clear();
    this.docLengths.clear();
    this.docs.clear();
    this.totalTokens = 0;

    for (const d of documents) {
      this.addInternal(d, /*reportFresh*/ false);
    }
    this.ready = true;
  }

  /** Add a single document incrementally. Safe to call before/after rebuild. */
  add(doc: Document): void {
    if (this.docs.has(doc.id)) {
      // Already indexed — nothing to do at the index level. The store handles
      // savedAt updates separately.
      return;
    }
    this.addInternal(doc, /*reportFresh*/ true);
  }

  /** Remove a document from the index. */
  remove(docId: string): void {
    const doc = this.docs.get(docId);
    if (!doc) return;
    const len = this.docLengths.get(docId) ?? 0;
    this.totalTokens -= len;
    this.docLengths.delete(docId);
    this.docs.delete(docId);
    // Sweep postings. Linear in total postings — acceptable for v0; if this
    // becomes hot we can swap to a doc-major posting layout.
    for (const [term, list] of this.postings) {
      const filtered = list.filter((p) => p.docId !== docId);
      if (filtered.length === 0) {
        this.postings.delete(term);
        this.df.delete(term);
      } else if (filtered.length !== list.length) {
        this.postings.set(term, filtered);
        this.df.set(term, filtered.length);
      }
    }
  }

  /**
   * Search the index for the top-K hits matching `query`. Returns hits
   * sorted by descending BM25 score, with snippets.
   */
  search(query: string, limit: number): SearchHit[] {
    if (!this.ready || this.docs.size === 0) return [];

    // Combine title + body for query expansion (we don't index them
    // separately yet — see roadmap). For now, query terms come straight from
    // the user input.
    const queryTerms = uniq(tokenize(query, CONFIG.index.minTokenLength));
    if (queryTerms.length === 0) return [];

    const N = this.docs.size;
    const avgdl = this.avgDocLength;
    const { k1, b } = CONFIG.bm25;

    // Accumulate per-doc scores via term-at-a-time traversal.
    const scores = new Map<string, number>();
    const matched = new Map<string, Set<string>>();

    for (const term of queryTerms) {
      const df = this.df.get(term);
      if (!df) continue;
      const idf = Math.log((N - df + 0.5) / (df + 0.5) + 1);
      const list = this.postings.get(term)!;

      for (const { docId, tf } of list) {
        const dl = this.docLengths.get(docId) ?? 0;
        const denom = tf + k1 * (1 - b + (b * dl) / (avgdl || 1));
        const contribution = idf * ((tf * (k1 + 1)) / (denom || 1));
        scores.set(docId, (scores.get(docId) ?? 0) + contribution);

        let set = matched.get(docId);
        if (!set) {
          set = new Set();
          matched.set(docId, set);
        }
        set.add(term);
      }
    }

    if (scores.size === 0) return [];

    // Top-K via partial sort. For very large result sets a heap would beat
    // sort(); for v0, sort is fine.
    const ranked = Array.from(scores.entries())
      .sort((a, b2) => b2[1] - a[1])
      .slice(0, limit);

    return ranked.map(([docId, score]) => {
      const doc = this.docs.get(docId)!;
      const matchedTerms = Array.from(matched.get(docId) ?? []);
      return {
        doc,
        score,
        snippet: makeSnippet(doc.text, matchedTerms),
        matchedTerms,
      };
    });
  }

  // ---------- internals ----------

  private addInternal(doc: Document, _reportFresh: boolean): void {
    // Index over title + text so title hits are weighted naturally by their
    // term frequency within the doc.
    const fullText = (doc.title ? doc.title + '\n' : '') + doc.text;
    const tokens = tokenize(fullText, CONFIG.index.minTokenLength);
    const length = tokens.length;

    // Build term frequency for this doc.
    const tf = new Map<string, number>();
    for (const t of tokens) tf.set(t, (tf.get(t) ?? 0) + 1);

    // Update inverted index.
    for (const [term, count] of tf) {
      let list = this.postings.get(term);
      if (!list) {
        list = [];
        this.postings.set(term, list);
      }
      list.push({ docId: doc.id, tf: count });
      this.df.set(term, (this.df.get(term) ?? 0) + 1);
    }

    this.docLengths.set(doc.id, length);
    this.docs.set(doc.id, doc);
    this.totalTokens += length;
  }
}

// ---------- helpers ----------

function uniq<T>(xs: T[]): T[] {
  return Array.from(new Set(xs));
}

/**
 * Build a snippet string for a search hit. Strategy: find the densest
 * window in the doc text containing matched terms, render with the
 * matched terms wrapped in <mark>.
 *
 * Output is HTML-safe (escaped + only the <mark> tags introduced by us).
 */
export function makeSnippet(text: string, matchedTerms: string[]): string {
  if (!matchedTerms.length) {
    return escapeHtml(text.slice(0, CONFIG.search.snippetChars)).trim() + '…';
  }

  const lower = text.toLowerCase();
  // Find positions of any matched term occurrences.
  const positions: { idx: number; term: string }[] = [];
  for (const term of matchedTerms) {
    const re = new RegExp(`\\b${escapeRegex(term)}\\b`, 'g');
    let m: RegExpExecArray | null;
    while ((m = re.exec(lower)) !== null) {
      positions.push({ idx: m.index, term });
      if (positions.length > 200) break; // safety
    }
    if (positions.length > 200) break;
  }

  if (positions.length === 0) {
    return escapeHtml(text.slice(0, CONFIG.search.snippetChars)).trim() + '…';
  }

  // Find the position whose surrounding window contains the most distinct terms.
  const window = CONFIG.search.snippetContextChars * 2;
  let bestIdx = positions[0].idx;
  let bestCount = 0;
  for (const { idx } of positions) {
    const lo = idx - CONFIG.search.snippetContextChars;
    const hi = idx + CONFIG.search.snippetContextChars;
    const distinct = new Set<string>();
    for (const p of positions) {
      if (p.idx >= lo && p.idx <= hi) distinct.add(p.term);
    }
    if (distinct.size > bestCount) {
      bestCount = distinct.size;
      bestIdx = idx;
    }
  }

  const start = Math.max(0, bestIdx - CONFIG.search.snippetContextChars);
  const end = Math.min(text.length, start + window);
  let raw = text.slice(start, end).trim();
  if (start > 0) raw = '…' + raw;
  if (end < text.length) raw = raw + '…';

  // Escape, then re-introduce <mark> wrappers around matched terms only.
  let escaped = escapeHtml(raw);
  // Wrap longest terms first so "york" doesn't shadow "new york".
  const sortedTerms = [...matchedTerms].sort((a, b) => b.length - a.length);
  for (const term of sortedTerms) {
    const re = new RegExp(`\\b(${escapeRegex(escapeHtml(term))})\\b`, 'gi');
    escaped = escaped.replace(re, '<mark>$1</mark>');
  }
  return escaped;
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
