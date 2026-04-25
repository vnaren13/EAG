// Minimal service worker — the popup handles everything, but MV3 requires
// a background script to be declared for certain permissions to activate.

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Second Brain Agent] installed');
});
