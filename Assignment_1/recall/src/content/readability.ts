import { Readability } from '@mozilla/readability';

/**
 * Run Mozilla Readability on a clone of the document. Returns the article's
 * plain text + title + byline, or null if the page isn't an article.
 */
export interface ExtractedArticle {
  title: string;
  byline?: string;
  text: string;
}

export function extractArticle(): ExtractedArticle | null {
  const docClone = document.cloneNode(true) as Document;
  const reader = new Readability(docClone, { keepClasses: false });
  const result = reader.parse();
  if (!result || !result.textContent) return null;

  const text = result.textContent.replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  return {
    title: result.title ?? document.title,
    byline: result.byline ?? undefined,
    text,
  };
}
