

https://github.com/user-attachments/assets/406922f8-33b0-4f89-9457-7087a064d82c

# Recall — Your Reading Second Brain

> *"What was that thing about quantum computing I read last month?"* Recall silently saves every article you read in your browser, then gives you instant BM25 search across your entire reading history. **100% local. No cloud. No signup. No API keys.**

## What it does

1. On every article you open, Recall extracts the main text via Mozilla Readability.
2. The article gets a stable content-derived id (so re-visits don't create duplicates), is persisted to IndexedDB, and is added to an in-memory BM25 inverted index.
3. A small "Saved to Recall" toast flashes in the corner of the page on first capture, then auto-dismisses. Nothing else interrupts you.
4. Click the toolbar icon to open the search popup. Type a few words → ranked results appear instantly with snippets, matched terms highlighted, source host, and relative time. Click any result to open the original.

## Why local-only

The privacy story is the design constraint, not a marketing line. It is enforced by the manifest itself:

- **No `host_permissions`.** Recall *cannot* fetch any URL on its own — even if its code wanted to.
- **No `<all_urls>` fetch capability.** The content script only reads the page the user is already on.
- **No telemetry.** There is no remote endpoint anywhere in the codebase.
- **No `chrome.storage.sync`.** All settings stay on this device. Nothing routes through Google's servers.
- **Uninstall = delete.** All data lives in IndexedDB scoped to this extension. Removing the extension removes the data.

## Architecture

```
src/
  manifest.json                MV3 — no host_permissions, no <all_urls> fetch
  background/
    service_worker.ts          Typed message router; owns the index + store
    store/
      db.ts                    Dexie schema (documents table)
      settings.ts              chrome.storage.local-backed settings
    search/
      bm25.ts                  Pure-TS Okapi BM25 inverted index
      index_manager.ts         Lazy rebuild from Dexie on cold start
  content/
    readability.ts             @mozilla/readability wrapper
    capture.ts                 Auto-capture on document_idle
    toast.ts                   Shadow-DOM "Saved to Recall" toast
  popup/                       Search UI (debounced, ranked, keyboard-friendly)
  options/                     Pause / excluded hosts / export / delete-all
  shared/
    types.ts                   Document, SearchHit, Settings, message protocol
    config.ts                  Tunable knobs (BM25 params, snippet sizes)
    util.ts                    Tokenizer, hash, host-suffix matcher, etc.
```

### The BM25 index

`src/background/search/bm25.ts` is a pure TypeScript implementation of Okapi BM25 — no dependencies. The scoring formula:

```
score(q, d) = Σ_{t∈q}  IDF(t) · (tf_{t,d} (k1+1)) / (tf_{t,d} + k1 (1 - b + b · |d|/avgdl))

IDF(t)      = ln( (N - df_t + 0.5) / (df_t + 0.5) + 1 )
```

Default `k1=1.2`, `b=0.75` (the standard Lucene defaults). BM25 was chosen over plain TF-IDF for two reasons that both matter for "find that thing I read":

1. **Term-frequency saturation.** A word appearing 10× isn't 10× as relevant as appearing once.
2. **Document-length normalization.** A 200-word doc isn't penalized against a 5,000-word one.

The index lives entirely in the service worker. Because MV3 service workers idle-die after ~30s, the first request after a wake triggers a one-time rebuild from Dexie via `IndexManager`, which caches the rebuild promise so concurrent calls don't both re-index. After hydration, all subsequent calls hit the in-memory inverted index directly.

**Capacity envelope at v0:** ~10k documents averaging ~500 tokens each, ~50k unique terms. ~5–8 MB of memory. Sub-millisecond search latency. Cold-start rebuild ≈ 1–2 seconds for 10k docs. Beyond that, postings can persist to Dexie and load lazily — the public `Bm25Index` API doesn't have to change.

### Snippet generation

`makeSnippet()` finds the **densest window of matched-term occurrences** in the doc body, slices a context window around it, escapes the HTML, then re-introduces only the `<mark>` tags Recall introduced itself. The result is XSS-safe by construction: the only HTML that survives the escape is markup Recall added.

### Capture flow

1. Content script runs at `document_idle` + 600 ms (so SPAs that hydrate after idle get a chance to populate the article DOM).
2. Readability extracts the main text on a *clone* of the document — the live DOM is never mutated.
3. The text is sent to the service worker via a typed `RecallMessage`.
4. Service worker checks: not paused → not excluded host → long enough → title doesn't look like a 404/login. If all pass, it hashes the content for a stable id, upserts into Dexie, adds to the BM25 index.
5. If this is a *first* save (id wasn't already present), the content script shows a one-time corner toast.
6. Re-visiting the same article updates `savedAt` but doesn't duplicate.

### Confidence in correctness

- **Strict TypeScript** with `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, and `noImplicitOverride` — the build runs `tsc --noEmit` before bundling.
- **Typed message protocol** between content/popup/options ↔ service worker (`RecallMessage` / `RecallResponse` discriminated unions).
- **Content-hash IDs** make captures idempotent: re-visits don't duplicate, and a re-render of the same article (e.g. ad reload causing a different scroll position) hashes to the same id.

## Build & install

Requires Node 20+ and a Chromium-based browser.

```bash
cd Assignment_1/recall
npm install
npm run build
```

Then in Chrome:

1. Open `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `dist/` folder

The placeholder toolbar icon (a blue **R**) is generated by `scripts/make_icons.mjs` during the first build if `public/icons/` is empty.

## Using it

- Open a few news or blog articles. Each will flash a tiny "Saved to Recall" toast in the bottom-right.
- Click the toolbar icon and start typing. The BM25 index returns ranked results in single-digit milliseconds.
- Open the options page (right-click toolbar icon → Options) to pause capture, exclude domains, export your library as JSON, or delete everything.

