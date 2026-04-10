import type {
  CapturePayload,
  Document,
  RecallMessage,
  RecallResponse,
} from '@/shared/types';
import { CONFIG } from '@/shared/config';
import {
  aggregateStats,
  allDocuments,
  deleteAll as dbDeleteAll,
  deleteDocument,
  listDocuments,
  upsertDocument,
} from './store/db';
import { getSettings } from './store/settings';
import { indexManager } from './search/index_manager';
import { contentHash, hostExcluded, hostOf, tokenize } from '@/shared/util';

/**
 * MV3 service worker.
 *
 * Owns the BM25 index, the Dexie store, and the message router.
 * Content/popup/options scripts talk to it via chrome.runtime.sendMessage
 * with a typed RecallMessage. Async handlers — sendResponse is called from
 * inside the promise chain, with `return true` keeping the channel open.
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Recall] installed');
});

chrome.runtime.onMessage.addListener(
  (msg: RecallMessage, _sender, sendResponse: (r: RecallResponse) => void) => {
    handle(msg)
      .then(sendResponse)
      .catch((err: unknown) => {
        console.error('[Recall] handler error', err);
        sendResponse({ type: 'error', message: errMessage(err) });
      });
    return true;
  },
);

async function handle(msg: RecallMessage): Promise<RecallResponse> {
  switch (msg.type) {
    case 'ping':
      return { type: 'pong' };

    case 'capture':
      return capture(msg.payload);

    case 'search': {
      const start = performance.now();
      const hits = await indexManager.search(
        msg.payload.query,
        msg.payload.limit ?? CONFIG.search.defaultLimit,
      );
      return { type: 'search:ok', hits, tookMs: performance.now() - start };
    }

    case 'stats': {
      const stats = await aggregateStats();
      return { type: 'stats:ok', stats };
    }

    case 'list': {
      const { docs, total } = await listDocuments(msg.payload.offset, msg.payload.limit);
      return { type: 'list:ok', docs, total };
    }

    case 'delete': {
      await deleteDocument(msg.payload.id);
      await indexManager.remove(msg.payload.id);
      return { type: 'delete:ok' };
    }

    case 'deleteAll': {
      await dbDeleteAll();
      await indexManager.resetEmpty();
      return { type: 'delete:ok' };
    }

    case 'export': {
      const docs = await allDocuments();
      return { type: 'export:ok', json: JSON.stringify(docs, null, 2) };
    }
  }
}

// ---------- Capture flow ----------

async function capture(payload: CapturePayload): Promise<RecallResponse> {
  const settings = await getSettings();
  if (settings.paused) {
    return { type: 'capture:skipped', reason: 'paused' };
  }

  const host = hostOf(payload.url);
  if (hostExcluded(host, settings.excludedHosts)) {
    return { type: 'capture:skipped', reason: 'excluded host' };
  }

  if (payload.text.length < settings.minArticleChars) {
    return { type: 'capture:skipped', reason: 'too short' };
  }

  for (const re of CONFIG.capture.skipTitlePatterns) {
    if (re.test(payload.title)) {
      return { type: 'capture:skipped', reason: 'non-article title' };
    }
  }

  // Content-hash → stable id. Same article = same id even on re-visit.
  const id = contentHash(payload.text);
  const doc: Document = {
    id,
    url: payload.url,
    host,
    title: payload.title || '(untitled)',
    byline: payload.byline,
    text: payload.text,
    length: tokenize(payload.text).length,
    savedAt: Date.now(),
  };

  const { inserted } = await upsertDocument(doc);
  if (inserted) {
    await indexManager.add(doc);
  }

  return { type: 'capture:ok', doc, firstSave: inserted };
}

function errMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
