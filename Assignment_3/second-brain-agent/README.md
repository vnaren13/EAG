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


## Troubleshooting

**"Gemini API 400: API key not valid"** — Your key didn't paste correctly. Re-copy from https://aistudio.google.com/apikey.

**"Cannot extract content from protected URL"** — The extension can't inject into `chrome://`, `chrome-extension://`, or the Chrome Web Store. Navigate to a normal webpage first.

**Obsidian didn't open** — You either don't have Obsidian installed or the vault name doesn't match. The `.md` file in your Downloads folder is the fallback — you can drop it into any Obsidian vault manually.

**"Gemini API 429"** — Free-tier rate limit hit. Wait 60 seconds and retry, or upgrade your AI Studio quota.

**Font looks generic** — Google Fonts couldn't load. The system monospace fallback still works; the layout is unaffected.

---

## License

MIT — do whatever you want.
