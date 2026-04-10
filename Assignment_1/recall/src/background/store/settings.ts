import { DEFAULT_SETTINGS, type Settings } from '@/shared/types';

/**
 * Settings live in chrome.storage.local (NOT sync — no server round-trip).
 * Load is async, so anything that needs settings should `await getSettings()`
 * rather than caching at module load.
 */

const KEY = 'recall:settings';

export async function getSettings(): Promise<Settings> {
  const raw = await chrome.storage.local.get(KEY);
  const stored = raw[KEY] as Partial<Settings> | undefined;
  return { ...DEFAULT_SETTINGS, ...(stored ?? {}) };
}

export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  const current = await getSettings();
  const merged: Settings = { ...current, ...patch };
  await chrome.storage.local.set({ [KEY]: merged });
  return merged;
}
