import { Bm25Index } from './bm25';
import { allDocuments } from '../store/db';
import type { Document, SearchHit } from '@/shared/types';

/**
 * Singleton wrapper around Bm25Index that handles lazy cold-start rebuilds.
 *
 * Service workers in MV3 die after ~30s of inactivity, so we cannot trust
 * any in-memory state to survive between user actions. The first call into
 * the index manager after a wake triggers a rebuild from Dexie; subsequent
 * calls are fast.
 *
 * The rebuild promise is cached so concurrent calls (search + capture
 * arriving at the same time) don't both rebuild.
 */
class IndexManager {
  private index = new Bm25Index();
  private rebuildPromise: Promise<void> | null = null;
  private hydrated = false;

  /** Block until the index has been built from Dexie at least once. */
  async ready(): Promise<void> {
    if (this.hydrated) return;
    if (!this.rebuildPromise) {
      this.rebuildPromise = (async () => {
        const docs = await allDocuments();
        this.index.rebuild(docs);
        this.hydrated = true;
      })();
    }
    await this.rebuildPromise;
  }

  async search(query: string, limit: number): Promise<SearchHit[]> {
    await this.ready();
    return this.index.search(query, limit);
  }

  async add(doc: Document): Promise<void> {
    await this.ready();
    this.index.add(doc);
  }

  async remove(docId: string): Promise<void> {
    await this.ready();
    this.index.remove(docId);
  }

  /** Wipe and rebuild from scratch. Used after deleteAll(). */
  async resetEmpty(): Promise<void> {
    this.index = new Bm25Index();
    this.index.rebuild([]);
    this.hydrated = true;
    this.rebuildPromise = null;
  }

  size(): number {
    return this.index.size;
  }
}

export const indexManager = new IndexManager();
