import type { RecallMessage, RecallResponse, Settings, Stats } from '@/shared/types';
import { DEFAULT_SETTINGS } from '@/shared/types';

/**
 * Options page.
 *
 * Reads settings directly from chrome.storage.local (no service worker round
 * trip needed) and persists them on save. Library actions (export, delete-all,
 * stats) go through the service worker so they share the indexer's state.
 */

const KEY = 'recall:settings';

const pausedEl = document.getElementById('paused') as HTMLInputElement;
const excludedEl = document.getElementById('excluded') as HTMLTextAreaElement;
const minCharsEl = document.getElementById('min-chars') as HTMLInputElement;
const saveBtn = document.getElementById('save') as HTMLButtonElement;
const saveStatusEl = document.getElementById('save-status') as HTMLElement;

const exportBtn = document.getElementById('export') as HTMLButtonElement;
const deleteBtn = document.getElementById('delete-all') as HTMLButtonElement;
const statsEl = document.getElementById('stats') as HTMLElement;

async function loadSettings(): Promise<Settings> {
  const raw = await chrome.storage.local.get(KEY);
  return { ...DEFAULT_SETTINGS, ...(raw[KEY] ?? {}) };
}

async function saveSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({ [KEY]: s });
}

function settingsFromForm(): Settings {
  return {
    paused: pausedEl.checked,
    excludedHosts: excludedEl.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
    minArticleChars: Math.max(100, Number(minCharsEl.value) || DEFAULT_SETTINGS.minArticleChars),
  };
}

function applySettingsToForm(s: Settings): void {
  pausedEl.checked = s.paused;
  excludedEl.value = s.excludedHosts.join('\n');
  minCharsEl.value = String(s.minArticleChars);
}

async function refreshStats(): Promise<void> {
  const res = await sendMessage({ type: 'stats' });
  if (res.type !== 'stats:ok') {
    statsEl.textContent = '—';
    return;
  }
  statsEl.textContent = formatStats(res.stats);
}

function formatStats(stats: Stats): string {
  if (stats.totalDocs === 0) return 'Empty — no articles saved yet.';
  const tokens = stats.totalTokens.toLocaleString();
  const newest = stats.newestSavedAt
    ? new Date(stats.newestSavedAt).toLocaleDateString()
    : '?';
  const oldest = stats.oldestSavedAt
    ? new Date(stats.oldestSavedAt).toLocaleDateString()
    : '?';
  return `${stats.totalDocs.toLocaleString()} articles · ${tokens} tokens · from ${oldest} to ${newest}`;
}

saveBtn.addEventListener('click', async () => {
  const s = settingsFromForm();
  await saveSettings(s);
  saveStatusEl.textContent = 'Saved.';
  setTimeout(() => (saveStatusEl.textContent = ''), 1800);
});

exportBtn.addEventListener('click', async () => {
  const res = await sendMessage({ type: 'export' });
  if (res.type !== 'export:ok') return;
  const blob = new Blob([res.json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const date = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `recall-export-${date}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

deleteBtn.addEventListener('click', async () => {
  const ok = confirm(
    'Delete all saved articles permanently? This cannot be undone.\n\n' +
      'Tip: export your library first if you want a backup.',
  );
  if (!ok) return;
  await sendMessage({ type: 'deleteAll' });
  await refreshStats();
});

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

(async function init() {
  const s = await loadSettings();
  applySettingsToForm(s);
  await refreshStats();
})();
