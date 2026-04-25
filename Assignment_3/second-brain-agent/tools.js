// ============================================================
// tools.js — 4 custom tools for the Second Brain Agent.
//
//   1. get_page_content       — pull visible text + links from active tab
//   2. extract_key_concepts   — deterministic tag/phrase extraction
//   3. fetch_url_preview      — fetch a URL's title/description/first paragraph
//   4. save_to_obsidian       — write a .md file and fire obsidian:// URL scheme
// ============================================================

// ---------- 1. GET_PAGE_CONTENT ----------------------------------

async function getPageContent() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return { error: 'No active tab found.' };
  }
  // Don't try to extract from chrome:// or extension pages
  if (/^(chrome|edge|about|chrome-extension):/i.test(tab.url || '')) {
    return { error: `Cannot extract content from protected URL: ${tab.url}` };
  }

  try {
    const [injectionResult] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        // Prefer semantic main content, fall back to body
        const article = document.querySelector('article');
        const main = document.querySelector('main');
        const root = article || main || document.body;
        const rawText = (root?.innerText || '').replace(/\n{3,}/g, '\n\n').trim();

        // Collect up to 15 outbound links
        const seen = new Set();
        const links = [];
        for (const a of root.querySelectorAll('a[href]')) {
          const href = a.href;
          const text = (a.innerText || '').trim();
          if (!href || !href.startsWith('http')) continue;
          if (seen.has(href)) continue;
          if (!text || text.length < 3) continue;
          seen.add(href);
          links.push({ text: text.slice(0, 120), href });
          if (links.length >= 15) break;
        }

        return {
          url: location.href,
          title: document.title || '',
          text: rawText.slice(0, 6000),
          full_text_length: rawText.length,
          links,
        };
      },
    });
    return injectionResult?.result || { error: 'Script injection returned no result.' };
  } catch (e) {
    return { error: `Failed to extract page content: ${e.message}` };
  }
}

// ---------- 2. EXTRACT_KEY_CONCEPTS ------------------------------

const STOPWORDS = new Set([
  'the','and','for','with','that','this','from','have','has','had','are','was','were',
  'will','would','should','could','can','you','your','yours','our','ours','their','they',
  'them','its','but','not','also','into','onto','upon','about','over','under','more',
  'most','some','such','than','then','when','where','which','while','who','whom','whose',
  'what','why','how','there','here','been','being','does','did','doing','done',
]);

function extractKeyConcepts({ text }) {
  if (!text || typeof text !== 'string') {
    return { error: 'extract_key_concepts requires a text string.' };
  }

  // 1. Capitalized multi-word phrases (likely proper nouns, product names, concepts)
  const capPattern = /\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b/g;
  const capFreq = new Map();
  const matches = text.match(capPattern) || [];
  for (const m of matches) {
    if (m.length < 3) continue;
    capFreq.set(m, (capFreq.get(m) || 0) + 1);
  }
  const key_phrases = [...capFreq.entries()]
    .filter(([, c]) => c >= 1)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([p]) => p);

  // 2. Frequent content words (length >= 4, not stopwords)
  const wordFreq = new Map();
  for (const w of text.toLowerCase().match(/\b[a-z][a-z\-]{3,}\b/g) || []) {
    if (STOPWORDS.has(w)) continue;
    wordFreq.set(w, (wordFreq.get(w) || 0) + 1);
  }
  const top_words = [...wordFreq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([w, c]) => ({ word: w, count: c }));

  // 3. Suggested tags (lowercase, hyphenated, 3-7 of them)
  const raw = [
    ...key_phrases.slice(0, 4),
    ...top_words.slice(0, 4).map(t => t.word),
  ];
  const suggested_tags = [...new Set(raw.map(t =>
    t.toLowerCase().replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-')
  ))]
    .filter(t => t && t.length >= 3)
    .slice(0, 7);

  return {
    key_phrases,
    top_words,
    suggested_tags,
  };
}

// ---------- 3. FETCH_URL_PREVIEW ---------------------------------

async function fetchUrlPreview({ url }) {
  if (!url || !/^https?:\/\//i.test(url)) {
    return { error: 'fetch_url_preview requires a valid http(s) URL.' };
  }
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (Second Brain Agent)' },
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return { url, error: `HTTP ${res.status}` };
    }

    const html = (await res.text()).slice(0, 200_000);

    const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const title = titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim().slice(0, 200) : '';

    const descMatch =
      html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i) ||
      html.match(/<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["']/i);
    const description = descMatch ? descMatch[1].replace(/\s+/g, ' ').trim().slice(0, 300) : '';

    // First text paragraph — strip tags from first <p>
    const pMatch = html.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
    const firstP = pMatch
      ? pMatch[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 400)
      : '';

    return { url, title, description, first_paragraph: firstP };
  } catch (e) {
    return { url, error: e.name === 'AbortError' ? 'timeout' : e.message };
  }
}

// ---------- 4. SAVE_TO_OBSIDIAN ----------------------------------

async function saveToObsidian({ title, content, tags = [], vault }) {
  if (!title || !content) {
    return { error: 'save_to_obsidian requires both title and content.' };
  }

  // Resolve vault name — use arg, else saved setting, else default
  if (!vault) {
    const stored = await chrome.storage.local.get('obsidianVault');
    vault = stored.obsidianVault || 'SecondBrain';
  }

  const safeName = String(title)
    .replace(/[<>:"/\\|?*]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 100) || 'Untitled';

  const tagList = Array.isArray(tags) ? tags : [];
  const frontmatter =
    '---\n' +
    `title: "${String(title).replace(/"/g, '\\"')}"\n` +
    `date: ${new Date().toISOString().slice(0, 10)}\n` +
    `tags: [${tagList.map(t => `"${String(t).replace(/"/g, '')}"`).join(', ')}]\n` +
    '---\n\n';

  const fullContent = frontmatter + content;

  // --- Fallback 1: download .md file via chrome.downloads ---
  let downloadId = null;
  try {
    const dataUrl = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(fullContent);
    downloadId = await chrome.downloads.download({
      url: dataUrl,
      filename: `${safeName}.md`,
      saveAs: false,
    });
  } catch (e) {
    console.warn('download failed:', e);
  }

  // --- Primary path: fire obsidian://new URL via a hidden anchor ---
  // This only works if the user has Obsidian installed and a vault of this name.
  const obsidianUrl =
    `obsidian://new?vault=${encodeURIComponent(vault)}` +
    `&name=${encodeURIComponent(safeName)}` +
    `&content=${encodeURIComponent(fullContent)}`;

  let obsidianFired = false;
  try {
    const a = document.createElement('a');
    a.href = obsidianUrl;
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    obsidianFired = true;
  } catch (e) {
    console.warn('obsidian:// fire failed:', e);
  }

  return {
    saved: true,
    vault,
    filename: `${safeName}.md`,
    char_count: fullContent.length,
    tag_count: tagList.length,
    obsidian_fired: obsidianFired,
    download_id: downloadId,
    note: 'File downloaded to your default Downloads folder. If Obsidian is installed with a vault matching the name above, a new note was also created there.',
  };
}

// ---------- TOOL REGISTRY ----------------------------------------

export const TOOL_DECLARATIONS = [
  {
    name: 'get_page_content',
    description:
      "Extracts the visible text content, title, URL, and up to 15 outbound links from the user's currently active browser tab. Call this first when the user asks to capture or analyze the current page. Returns {url, title, text, full_text_length, links[]}.",
    parameters: { type: 'object', properties: {}, required: [] },
  },
  {
    name: 'extract_key_concepts',
    description:
      'Analyzes a text block and returns (a) key_phrases (capitalized multi-word terms, likely proper nouns/concepts), (b) top_words (frequent content words), (c) suggested_tags (3-7 lowercase hyphenated tags). Use after get_page_content to inform note tagging and section headings.',
    parameters: {
      type: 'object',
      properties: {
        text: { type: 'string', description: 'The text block to analyze.' },
      },
      required: ['text'],
    },
  },
  {
    name: 'fetch_url_preview',
    description:
      'Fetches a single URL and returns its {title, description, first_paragraph}. Use sparingly — only for 1-2 of the MOST important external links found on the main page, to enrich the note with additional context. Do not call for every link.',
    parameters: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'A valid http(s) URL to fetch.' },
      },
      required: ['url'],
    },
  },
  {
    name: 'save_to_obsidian',
    description:
      "Saves the final structured markdown note. This (1) downloads a .md file to the user's Downloads folder and (2) attempts to open an obsidian://new URL for direct vault insertion. Call this EXACTLY ONCE at the very end, after you have assembled the complete note content. Do not call any more tools after save_to_obsidian.",
    parameters: {
      type: 'object',
      properties: {
        title: { type: 'string', description: 'Note title (no slashes or special chars).' },
        content: {
          type: 'string',
          description:
            'Full markdown note body WITHOUT frontmatter — frontmatter is added automatically. Include headings, bullets, and Source URL.',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: '3-7 lowercase hyphenated tags, no # prefix.',
        },
        vault: {
          type: 'string',
          description: "Obsidian vault name. If omitted, the user's configured vault is used.",
        },
      },
      required: ['title', 'content'],
    },
  },
];

export async function executeTool(name, args = {}) {
  switch (name) {
    case 'get_page_content':     return await getPageContent();
    case 'extract_key_concepts': return extractKeyConcepts(args);
    case 'fetch_url_preview':    return await fetchUrlPreview(args);
    case 'save_to_obsidian':     return await saveToObsidian(args);
    default:                     return { error: `Unknown tool: ${name}` };
  }
}
