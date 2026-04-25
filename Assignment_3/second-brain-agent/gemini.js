// ============================================================
// gemini.js — minimal wrapper around the Gemini generateContent
// endpoint with function calling.
// ============================================================

const DEFAULT_MODEL = 'gemini-2.5-flash';
const API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';

/**
 * Call Gemini with tools (function calling).
 *
 * @param {Object}   opts
 * @param {string}   opts.apiKey         Gemini API key
 * @param {string}   opts.systemPrompt   System instruction
 * @param {Array}    opts.contents       Full message history (see Gemini API docs)
 * @param {Array}    opts.tools          Function declarations
 * @param {string}   [opts.model]        Model name (defaults to gemini-2.5-flash)
 *
 * @returns {Promise<{parts: Array, text: string, functionCalls: Array, raw: Object}>}
 */
export async function callGemini({ apiKey, systemPrompt, contents, tools, model = DEFAULT_MODEL }) {
  const body = {
    systemInstruction: { parts: [{ text: systemPrompt }] },
    contents,
    generationConfig: {
      temperature: 0.4,
      maxOutputTokens: 2048,
    },
  };

  if (tools && tools.length > 0) {
    body.tools = [{ functionDeclarations: tools }];
    body.toolConfig = {
      functionCallingConfig: { mode: 'AUTO' },
    };
  }

  const url = `${API_BASE}/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini API ${res.status}: ${errText.slice(0, 300)}`);
  }

  const data = await res.json();

  const candidate = data?.candidates?.[0];
  if (!candidate) {
    throw new Error('Gemini returned no candidates: ' + JSON.stringify(data).slice(0, 300));
  }

  const parts = candidate?.content?.parts || [];
  const text = parts
    .filter(p => typeof p.text === 'string')
    .map(p => p.text)
    .join('\n')
    .trim();
  const functionCalls = parts
    .filter(p => p.functionCall)
    .map(p => p.functionCall);

  return { parts, text, functionCalls, raw: data };
}

export { DEFAULT_MODEL };
