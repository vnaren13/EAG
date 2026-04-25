# 🧠 Second Brain Agent

> Agentic AI Chrome extension that captures any webpage into your Obsidian vault as a well-structured, searchable note — and shows you its full reasoning chain as it works.

Built for **Assignment 3: Chrome Agentic AI Plugin**.

---

## What it is

A Manifest V3 Chrome extension with a popup UI that runs an **agent loop** against Gemini:

```
┌──────────────────────────────────────────────────────────────────┐
│ Query1 → LLM → tool_call + tool_result                           │
│   → Query2 (history now includes everything above) → LLM → ...   │
│   → ... → Final answer                                           │
└──────────────────────────────────────────────────────────────────┘
```

Every LLM reasoning step, every tool call, and every tool result streams into the trace UI in real time. The full message history is re-sent on every iteration (as required by the assignment).

## The 4 custom tools

| # | Tool | What it does | Why the LLM can't do it alone |
|---|------|--------------|-------------------------------|
| 1 | `get_page_content()` | Extracts title, visible text, and outbound links from the user's active Chrome tab via `chrome.scripting.executeScript` | LLM has no browser access |
| 2 | `extract_key_concepts(text)` | Deterministic tag/phrase extraction: capitalized-phrase detection + term-frequency ranking + stopword filtering | Deterministic + fast, removes hallucination risk on tagging |
| 3 | `fetch_url_preview(url)` | Fetches a URL and returns its `<title>`, meta description, and first `<p>` | LLM has no network access |
| 4 | `save_to_obsidian(title, content, tags, vault)` | Downloads a `.md` file AND fires the `obsidian://new` URL scheme to insert directly into the user's vault | Side-effect on real filesystem / OS |

## Project structure

```
second-brain-agent/
├── manifest.json        # MV3 manifest
├── popup.html           # UI structure
├── popup.css            # Terminal/CRT aesthetic
├── popup.js             # 🔑 main agent loop — read this one
├── gemini.js            # Gemini generateContent wrapper
├── tools.js             # 4 tool declarations + implementations
├── background.js        # minimal service worker
└── README.md
```

---

## Setup (2 minutes)

### 1. Get a Gemini API key (free tier)
- Go to https://aistudio.google.com/apikey
- Click **Create API key** → copy it.

### 2. Load the extension
1. Unzip this folder anywhere (e.g. `~/Projects/second-brain-agent`).
2. Open `chrome://extensions` in Chrome.
3. Toggle **Developer mode** (top right).
4. Click **Load unpacked** → pick the `second-brain-agent` folder.
5. The 🧠 extension icon appears in your toolbar — pin it for the demo.

### 3. Configure
1. Click the extension icon → the popup opens.
2. Paste your Gemini API key → **save**.
3. (Optional) Enter your Obsidian vault name → **save**.
   - If you don't use Obsidian, leave it at `SecondBrain` — you'll still get a `.md` download as fallback.

---

## How to demo (for the YouTube submission)

### Recommended demo page
Navigate to an article-style page. Good options:
- A technical blog post (e.g. `https://simonwillison.net`)
- A Wikipedia article
- A long-form Medium / Substack post
- An arXiv abstract page

### Script

1. **Navigate** to the target page.
2. **Click** the Second Brain Agent icon.
3. **Leave** the default query (or edit it — e.g. ask it to focus on a specific angle).
4. **Click "▶ run agent"**.
5. **Watch the trace** — you'll see:
   - `user query` (blue)
   - `iter 1 — llm reasoning` (purple) — Gemini explains it will call `get_page_content`
   - `tool_call → get_page_content` (amber)
   - `tool_result ← get_page_content` (green) — page text comes back
   - `iter 2 — llm reasoning` — Gemini plans to extract concepts
   - `tool_call → extract_key_concepts`
   - `tool_result ← extract_key_concepts` — tags appear
   - *(optional)* `tool_call → fetch_url_preview` if a link is worth fetching
   - `tool_call → save_to_obsidian`
   - `tool_result ← save_to_obsidian`
   - `final answer` (teal) — one-sentence confirmation
6. **Check your Downloads folder** — a fresh `.md` file is there. If you have Obsidian open with the configured vault, the note has also been inserted.
7. **Click "copy"** on the trace panel to copy the entire LLM log for submission.

Total runtime: typically 20–40 seconds, 4–5 LLM iterations, 4 tool calls.

### What to highlight on camera
- The trace is **color-coded by turn type** — easy to show what's an LLM thought vs a tool call vs a tool result.
- The **`iter / msgs` counter** in the trace header shows the growing history size — visually reinforces that "each Query stores ALL past interaction".
- The final `.md` file is a real artifact you can open in any editor.

---

## Sample LLM log (what to paste alongside your YouTube link)

This is an illustrative run — yours will differ based on the page you capture.

```
=== SECOND BRAIN AGENT — LLM LOG ===

[user query]
Capture this page into my Obsidian vault. Include a 3-sentence TL;DR,
5-7 lowercase tags, a Key Ideas section with bullets, and any notable
external links worth exploring.

[iter 1]
sending 1 messages to gemini…

[iter 1 — llm reasoning]
I'll start by reading the current tab's content so I know what to summarize.

[tool_call → get_page_content]
{}

[tool_result ← get_page_content]
{
  "url": "https://simonwillison.net/2024/Dec/19/one-shot-python-tools/",
  "title": "Building Python tools with a one-shot prompt using uv...",
  "text": "Back in March last year I wrote about how I was using...",
  "full_text_length": 7421,
  "links": [
    { "text": "uv tool", "href": "https://docs.astral.sh/uv/..." },
    ...
  ]
}

[iter 2]
sending 3 messages to gemini…

[iter 2 — llm reasoning]
Good — now I'll extract key concepts to drive the tags and identify the
main themes.

[tool_call → extract_key_concepts]
{ "text": "Back in March last year I wrote about how I..." }

[tool_result ← extract_key_concepts]
{
  "key_phrases": ["Simon Willison", "Claude", "Python", "uv tool", "LLM"],
  "top_words": [
    { "word": "script", "count": 14 },
    { "word": "prompt", "count": 11 }
  ],
  "suggested_tags": ["python", "llm", "claude", "one-shot-prompt", "uv-tool"]
}

[iter 3]
sending 5 messages to gemini…

[iter 3 — llm reasoning]
The `uv tool` link looks central — I'll preview it for context on why it
matters to the one-shot workflow.

[tool_call → fetch_url_preview]
{ "url": "https://docs.astral.sh/uv/guides/tools/" }

[tool_result ← fetch_url_preview]
{
  "url": "https://docs.astral.sh/uv/guides/tools/",
  "title": "Using tools | uv",
  "description": "Many Python packages provide applications that can be...",
  "first_paragraph": "..."
}

[iter 4]
sending 7 messages to gemini…

[iter 4 — llm reasoning]
I have enough context. Composing the final note and saving it.

[tool_call → save_to_obsidian]
{
  "title": "One-shot Python Tools with uv and Claude",
  "content": "# One-shot Python Tools with uv and Claude\n\n## TL;DR\n...",
  "tags": ["python", "llm", "claude", "uv-tool", "one-shot-prompt",
           "dev-tools", "workflow"]
}

[tool_result ← save_to_obsidian]
{
  "saved": true,
  "vault": "SecondBrain",
  "filename": "One-shot Python Tools with uv and Claude.md",
  "char_count": 1842,
  "obsidian_fired": true,
  "download_id": 47
}

[iter 5]
sending 9 messages to gemini…

[final answer]
Saved "One-shot Python Tools with uv and Claude" to your SecondBrain
vault with 7 tags. The .md file is also in your Downloads folder.
```

---

## Architecture: why this meets the assignment spec

- ✅ **LLM called multiple times** — the agent loop calls Gemini up to 10 times per run; typical run is 4–5 calls.
- ✅ **Each query stores ALL past interaction** — `popup.js` maintains a single `contents` array that is appended to (never reset) and re-sent in full on every iteration. You can see the `msgs: N` counter grow in the trace header.
- ✅ **Reasoning chain displayed** — every LLM reasoning block, tool call, and tool result renders as a separate color-coded entry in the trace UI.
- ✅ **At least 3 custom tool functions** — 4 tools, all distinct in capability and relevant to the "second brain" use case.
- ✅ **Tools require capabilities the LLM doesn't have alone** — browser tab access, deterministic text analysis, network fetch, filesystem side effects.

---

## Troubleshooting

**"Gemini API 400: API key not valid"** — Your key didn't paste correctly. Re-copy from https://aistudio.google.com/apikey.

**"Cannot extract content from protected URL"** — The extension can't inject into `chrome://`, `chrome-extension://`, or the Chrome Web Store. Navigate to a normal webpage first.

**Obsidian didn't open** — You either don't have Obsidian installed or the vault name doesn't match. The `.md` file in your Downloads folder is the fallback — you can drop it into any Obsidian vault manually.

**"Gemini API 429"** — Free-tier rate limit hit. Wait 60 seconds and retry, or upgrade your AI Studio quota.

**Font looks generic** — Google Fonts couldn't load. The system monospace fallback still works; the layout is unaffected.

---

## License

MIT — do whatever you want.
