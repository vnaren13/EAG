import type { RecallMessage, RecallResponse } from '@/shared/types';
import { extractArticle } from './readability';
import { showSavedToast } from './toast';

/**
 * Content script entry. Runs once per page at document_idle.
 *
 *  1. Skip if already injected (avoid double-capture on SPA navigation).
 *  2. Run Readability on a document clone.
 *  3. Send the article body to the service worker for indexing.
 *  4. If this is the first time we've ever seen this content, show a tiny
 *     "Saved to Recall" toast (once per page) so the user knows it's there
 *     without being intrusive.
 */
(async function main() {
  if ((window as any).__recallLoaded) return;
  (window as any).__recallLoaded = true;

  // Defer slightly so SPAs that hydrate after document_idle have time to
  // populate the article DOM. 600ms is the sweet spot in practice.
  await sleep(600);

  const article = extractArticle();
  if (!article) return;

  let res: RecallResponse;
  try {
    res = await sendMessage({
      type: 'capture',
      payload: {
        url: location.href,
        title: article.title,
        byline: article.byline,
        text: article.text,
      },
    });
  } catch (e) {
    // Service worker may be temporarily unavailable on browser startup; that's fine.
    console.debug('[Recall] capture send failed', e);
    return;
  }

  if (res.type === 'capture:ok' && res.firstSave) {
    showSavedToast();
  }
})();

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

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
