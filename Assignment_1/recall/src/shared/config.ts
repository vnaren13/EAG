/**
 * Tunable knobs. Anything that might want to become a user setting later
 * starts its life here.
 */
export const CONFIG = {
  bm25: {
    k1: 1.2,
    b: 0.75,
  },
  search: {
    /** Max hits returned to the popup. */
    defaultLimit: 30,
    /** Snippet character budget. */
    snippetChars: 240,
    /** Window of context around the best matched term. */
    snippetContextChars: 110,
  },
  capture: {
    /** Skip pages whose article body is shorter than this. */
    minArticleChars: 600,
    /** Skip pages whose Readability extraction title looks like a non-article. */
    skipTitlePatterns: [
      /^(?:sign in|log in|login|404|page not found|access denied|search results)/i,
    ],
  },
  index: {
    /** Tokens shorter than this are ignored. */
    minTokenLength: 3,
  },
} as const;
