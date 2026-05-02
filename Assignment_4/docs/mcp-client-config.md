# MCP client configuration

The News Diffractor server speaks **MCP over stdio**, so any MCP-capable client works. Below are snippets for the common ones. Replace `<ABS_PATH>` with the absolute path to this repo's root (e.g. `/path/to/news-diffractor` or `C:\path\to\news-diffractor`).

> **Note:** All snippets set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1`. On Windows these prevent a `UnicodeEncodeError` in Prefab's logging path on cp1252 consoles.

---

## Claude Code

Add to the project's `.mcp.json` (per-project) or `~/.claude/mcp_servers.json` (global):

```json
{
  "mcpServers": {
    "news-diffractor": {
      "command": "<ABS_PATH>/.venv/Scripts/python.exe",
      "args": ["<ABS_PATH>/server.py"],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PREFAB_PORT": "5175"
      }
    }
  }
}
```

Then restart Claude Code. The 3 tools (`fetch_coverage`, `manage_diffraction`, `show_diffractor`) appear in the tool palette.

---

## Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "news-diffractor": {
      "command": "<ABS_PATH>\\.venv\\Scripts\\python.exe",
      "args": ["<ABS_PATH>\\server.py"],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PREFAB_PORT": "5175"
      }
    }
  }
}
```

Quit Claude Desktop fully (tray icon → Quit), then relaunch.

---

## Cursor

`Settings → MCP → Add new MCP server`:

- **Name:** `news-diffractor`
- **Command:** `<ABS_PATH>/.venv/Scripts/python.exe <ABS_PATH>/server.py`
- **Env:** `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`

---

## Verifying the wiring

After registering, in your client run:

> "List the tools you have available."

You should see `fetch_coverage`, `manage_diffraction`, and `show_diffractor`.

Then run the canonical demo prompt:

> "Diffract today's coverage of the OpenAI EU regulatory probe across major outlets, compare their framing and headlines, save the analysis with a Markdown synthesis, then show me my news diffractor dashboard."

A browser tab should open onto `http://localhost:5175/` showing the side-by-side comparison.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser tab doesn't open automatically | The tool's response includes the URL — open it manually. |
| `prefab serve` fails on Windows with `UnicodeEncodeError` | Make sure `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` are in the `env` block. |
| Port 5175 already in use | Set `PREFAB_PORT` to anything free (e.g. `"5180"`). |
| Tools appear but `fetch_coverage` returns 0 articles | Try a more specific topic (the keyword overlap must be present in at least one outlet's headline). |
| Dashboard shows stale data | The MCP server touches `dashboard.py` after writes; if you killed `prefab serve` manually, restart the server. |
