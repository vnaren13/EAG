import Dexie, { type Table } from 'dexie';
import type { Document } from '@/shared/types';

/**
 * Persistent storage for Recall.
 *
 * One table for documents (the canonical record). Indexes on `savedAt`,
 * `host`, and `length` so we can sort/group/filter without scanning every
 * row. The text body itself isn't indexed by Dexie — that's the BM25
 * inverted index's job (built in memory at runtime).
 *
 * Why Dexie over raw IndexedDB: it's small (~30 KB), well-tested, and
 * gives us promise-based queries with automatic schema migration. Cost is
 * one dependency.
 */
class RecallDB extends Dexie {
  documents!: Table<Document, string>;

  constructor() {
    super('recall');
    this.version(1).stores({
      // Primary key + secondary indexes (no `text` — full-text is BM25's job).
      documents: 'id, savedAt, host, length',
    });
  }
}

export const db = new RecallDB();

/** Add a document; if id already exists, refresh `savedAt` only. */
export async function upsertDocument(doc: Document): Promise<{ inserted: boolean }> {
  const existing = await db.documents.get(doc.id);
  if (existing) {
    // Same content, possibly different URL or visit time. Bump savedAt so
    // it surfaces in "recently read" but keep the original record.
    await db.documents.update(doc.id, { savedAt: doc.savedAt, url: doc.url });
    return { inserted: false };
  }
  await db.documents.add(doc);
  return { inserted: true };
}

export async function getDocument(id: string): Promise<Document | undefined> {
  return db.documents.get(id);
}

export async function deleteDocument(id: string): Promise<void> {
  await db.documents.delete(id);
}

export async function deleteAll(): Promise<void> {
  await db.documents.clear();
}

export async function listDocuments(offset: number, limit: number): Promise<{
  docs: Document[];
  total: number;
}> {
  const total = await db.documents.count();
  const docs = await db.documents
    .orderBy('savedAt')
    .reverse()
    .offset(offset)
    .limit(limit)
    .toArray();
  return { docs, total };
}

export async function allDocuments(): Promise<Document[]> {
  return db.documents.orderBy('savedAt').reverse().toArray();
}

export async function totalDocs(): Promise<number> {
  return db.documents.count();
}

export async function aggregateStats(): Promise<{
  totalDocs: number;
  totalTokens: number;
  oldestSavedAt: number | null;
  newestSavedAt: number | null;
}> {
  const docs = await db.documents.toArray();
  if (docs.length === 0) {
    return { totalDocs: 0, totalTokens: 0, oldestSavedAt: null, newestSavedAt: null };
  }
  let totalTokens = 0;
  let oldest = Infinity;
  let newest = -Infinity;
  for (const d of docs) {
    totalTokens += d.length;
    if (d.savedAt < oldest) oldest = d.savedAt;
    if (d.savedAt > newest) newest = d.savedAt;
  }
  return {
    totalDocs: docs.length,
    totalTokens,
    oldestSavedAt: oldest,
    newestSavedAt: newest,
  };
}
