// ============================================================
// popup.js — main agent loop
//
// Agent contract:
//   Query1 -> LLM Response -> Tool Call:Tool Result
//   -> Query2 (contents now includes everything) -> LLM Response -> ...
//   -> final answer
//
// All past turns stay in `contents` and are re-sent every iteration.
// Each LLM reasoning step, tool call, and tool result is logged
// to the trace UI.
// ============================================================

import { callGemini, DEFAULT_MODEL } from './gemini.js';
import { TOOL_DECLARATIONS, executeTool } from './tools.js';

const MAX_ITERATIONS = 10;

const SYSTEM_PROMPT = `You are the SECOND BRAIN AGENT — an AI that captures web pages into the user's Obsidian vault as well-structured, searchable notes.

Your standard workflow (follow unless the user instructs otherwise):
  1. Call get_page_content() to read the user's active browser tab.
  2. Call extract_key_concepts(text=<the page text>) to mine tags and key phrases from the text.
  3. OPTIONALLY call fetch_url_preview(url) for 1–2 of the MOST notable external links found on the page — only if they add meaningful context. Skip this step if the page is self-contained.
  4. Compose a clean markdown note with these sections:
       # <Title>
       ## TL;DR  — 3 to 4 sentences.
       ## Key Ideas  — 4 to 8 bullet points.
       ## Notable Links  — short bulleted list (only if you fetched previews).
       ## Source  — the original page URL.
  5. Call save_to_obsidian(title, content, tags, vault?) EXACTLY ONCE with your final note.
  6. After save_to_obsidian returns, reply with ONE short confirmation sentence and STOP. Do not call any more tools.

Hard rules:
- Briefly think out loud BEFORE each tool call (one sentence of reasoning).
- Tags: 3–7 items, lowercase, hyphen-separated, no '#' prefix.
- Stay faithful to the source page — do not invent facts.
- Never call save_to_obsidian more than once.`;

// ---------- DOM ----------

const $ = id => document.getElementById(id);
const traceEl      = $('trace');
const inputEl      = $('user-query');
const runBtn       = $('run-btn');
const stopBtn      = $('stop-btn');
const clearBtn     = $('clear-btn');
const copyBtn      = $('copy-btn');
const configToggle = $('config-toggle');
const configSec    = $('config-section');
const apiKeyInput  = $('api-key-input');
const saveKeyBtn   = $('save-key-btn');
const vaultInput   = $('vault-input');
const saveVaultBtn = $('save-vault-btn');
const statsEl      = $('trace-stats');
const statusEl     = $('status');
const modelLabel   = $('model-label');

let currentRun = { cancelled: false };

// ---------- TRACE UI ----------

function clearEmptyPlaceholder() {
  const empty = traceEl.querySelector('.trace-empty');
  if (empty) empty.remove();
}

function traceAdd(type, label, body) {
  clearEmptyPlaceholder();
  const entry = document.createElement('div');
  entry.className = `trace-entry trace-${type}`;
  const labelEl = document.createElement('div');
  labelEl.className = 'trace-label';
  labelEl.textContent = label;
  const bodyEl = document.createElement('div');
  bodyEl.className = 'trace-body';
  if (typeof body === 'string') {
    bodyEl.textContent = body;
  } else {
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(body, null, 2);
    bodyEl.appendChild(pre);
  }
  entry.appendChild(labelEl);
  entry.appendChild(bodyEl);
  traceEl.appendChild(entry);
  traceEl.scrollTop = traceEl.scrollHeight;
  return entry;
}

function updateStats(iter, msgCount) {
  statsEl.textContent = `iter: ${iter} · msgs: ${msgCount}`;
}

function setStatus(state, text) {
  statusEl.className = state;
  statusEl.textContent = text;
}

// ---------- STORAGE ----------

async function loadStored() {
  const { geminiApiKey, obsidianVault } = await chrome.storage.local.get([
    'geminiApiKey',
    'obsidianVault',
  ]);
  if (geminiApiKey) apiKeyInput.value = geminiApiKey;
  if (obsidianVault) vaultInput.value = obsidianVault;
  // Auto-collapse config if both are set
  if (geminiApiKey && obsidianVault) {
    configSec.classList.add('hidden');
  }
  modelLabel.textContent = DEFAULT_MODEL;
}

saveKeyBtn.addEventListener('click', async () => {
  const v = apiKeyInput.value.trim();
  if (!v) return;
  await chrome.storage.local.set({ geminiApiKey: v });
  saveKeyBtn.textContent = 'saved ✓';
  setTimeout(() => (saveKeyBtn.textContent = 'save'), 1200);
});

saveVaultBtn.addEventListener('click', async () => {
  const v = vaultInput.value.trim();
  if (!v) return;
  await chrome.storage.local.set({ obsidianVault: v });
  saveVaultBtn.textContent = 'saved ✓';
  setTimeout(() => (saveVaultBtn.textContent = 'save'), 1200);
});

configToggle.addEventListener('click', () => {
  configSec.classList.toggle('hidden');
});

clearBtn.addEventListener('click', () => {
  traceEl.innerHTML = '<div class="trace-empty">// trace will stream here after you run the agent</div>';
  updateStats(0, 0);
  setStatus('', 'idle');
});

copyBtn.addEventListener('click', async () => {
  const text = buildPlaintextTrace();
  try {
    await navigator.clipboard.writeText(text);
    copyBtn.textContent = 'copied ✓';
    setTimeout(() => (copyBtn.textContent = 'copy'), 1200);
  } catch (e) {
    alert('Copy failed: ' + e.message);
  }
});

stopBtn.addEventListener('click', () => {
  currentRun.cancelled = true;
  setStatus('error', 'cancelling…');
});

function buildPlaintextTrace() {
  const lines = ['=== SECOND BRAIN AGENT — LLM LOG ===', ''];
  for (const entry of traceEl.querySelectorAll('.trace-entry')) {
    const label = entry.querySelector('.trace-label')?.textContent || '';
    const body  = entry.querySelector('.trace-body')?.textContent || '';
    lines.push(`[${label}]`);
    lines.push(body);
    lines.push('');
  }
  return lines.join('\n');
}

// ---------- AGENT LOOP ----------

async function runAgent(userQuery) {
  const { geminiApiKey } = await chrome.storage.local.get('geminiApiKey');
  if (!geminiApiKey) {
    configSec.classList.remove('hidden');
    traceAdd('error', 'config', 'Save your Gemini API key first (top of popup).');
    return;
  }

  currentRun = { cancelled: false };
  runBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('running', 'running…');

  traceAdd('user', 'user query', userQuery);

  // This is the growing history — re-sent in full on every iteration.
  const contents = [
    { role: 'user', parts: [{ text: userQuery }] },
  ];
  updateStats(0, contents.length);

  try {
    for (let iter = 1; iter <= MAX_ITERATIONS; iter++) {
      if (currentRun.cancelled) {
        traceAdd('error', 'cancelled', 'Agent run cancelled by user.');
        break;
      }

      traceAdd('step', `iter ${iter}`, `sending ${contents.length} messages to gemini…`);
      updateStats(iter, contents.length);

      let response;
      try {
        response = await callGemini({
          apiKey: geminiApiKey,
          systemPrompt: SYSTEM_PROMPT,
          contents,
          tools: TOOL_DECLARATIONS,
        });
      } catch (e) {
        traceAdd('error', `iter ${iter} — llm error`, e.message);
        break;
      }

      // Log reasoning text if Gemini returned any
      if (response.text) {
        traceAdd('reasoning', `iter ${iter} — llm reasoning`, response.text);
      }

      // Persist model turn into history (may contain text + function calls)
      contents.push({ role: 'model', parts: response.parts });
      updateStats(iter, contents.length);

      if (response.functionCalls && response.functionCalls.length > 0) {
        // Execute each tool call and gather function responses into one user turn
        const responseParts = [];
        for (const call of response.functionCalls) {
          if (currentRun.cancelled) break;

          traceAdd('tool-call', `tool_call → ${call.name}`, call.args || {});

          let result;
          try {
            result = await executeTool(call.name, call.args || {});
          } catch (e) {
            result = { error: e.message };
          }

          // Truncate very large results for trace readability
          const displayResult = truncateForDisplay(result);
          traceAdd('tool-result', `tool_result ← ${call.name}`, displayResult);

          responseParts.push({
            functionResponse: {
              name: call.name,
              response: result,
            },
          });
        }

        if (currentRun.cancelled) {
          traceAdd('error', 'cancelled', 'Agent run cancelled by user.');
          break;
        }

        contents.push({ role: 'user', parts: responseParts });
        updateStats(iter, contents.length);
      } else {
        // No tool calls -> agent is done
        traceAdd('final', 'final answer', response.text || '(no text)');
        setStatus('done', `done (${iter} iters · ${contents.length} msgs)`);
        return;
      }
    }

    if (!currentRun.cancelled) {
      traceAdd('error', 'limit', `max iterations (${MAX_ITERATIONS}) reached without a final answer.`);
      setStatus('error', 'max iters');
    } else {
      setStatus('error', 'cancelled');
    }
  } finally {
    runBtn.disabled = false;
    stopBtn.disabled = true;
  }
}

// Truncate long strings inside tool results so the trace stays readable.
function truncateForDisplay(obj, max = 600) {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj === 'string') return obj.length > max ? obj.slice(0, max) + ` …[+${obj.length - max} chars]` : obj;
  if (Array.isArray(obj)) return obj.slice(0, 20).map(v => truncateForDisplay(v, max));
  if (typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) out[k] = truncateForDisplay(v, max);
    return out;
  }
  return obj;
}

runBtn.addEventListener('click', () => {
  const q = inputEl.value.trim();
  if (!q) return;
  runAgent(q);
});

// Init
loadStored();
