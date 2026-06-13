# Session 9 — GitHub Trending comparison agent: one-shot demo runner.
#
# Usage (from anywhere, in a PowerShell terminal):
#     powershell -ExecutionPolicy Bypass -File "d:\TSAI\ERAV3\S9\run_github_demo.ps1"
#
# What it does, end to end (ideal for a single-take screen recording):
#   1. clears stale FAISS memory so old runs can't contaminate this one
#   2. runs the agent — the full [n:...] node trace streams live to this terminal
#   3. builds the HTML replay report for the run that just finished
#   4. opens that report in your browser automatically
#
# Requires the V9 gateway on :8109 (flow.py auto-starts it if it isn't up).

$ErrorActionPreference = "Stop"

# UTF-8 so the box-drawing trace chars don't crash on Windows cp1252.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$codeDir = "d:\TSAI\ERAV3\S9\S9SharedCode\code"
Set-Location $codeDir

# 1 · Clear stale FAISS memory (keeps session traces under state/sessions).
Remove-Item -ErrorAction SilentlyContinue state\index.faiss, state\index_ids.json, state\memory.json

$query = "Open GitHub Trending at https://github.com/trending and find the top trending Python repositories this week. List 5 if clearly shown, at least 3. Use the page's filters to show repositories written in Python, trending over the past week. For each repository give: repository name, primary language, total star count, and stars gained this week, plus a one-line description if shown. Then rank which repository is the fastest-growing or most exciting and explain why in one or two sentences."

# 2 · Run the agent — trace streams live to this terminal.
Write-Host "`n=== Running GitHub Trending comparison agent ===`n" -ForegroundColor Cyan
uv run python flow.py $query

# 3 · Find the session just created and build its HTML replay report.
$sid = (Get-ChildItem "$codeDir\state\sessions" -Directory |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1).Name
Write-Host "`n=== Building replay report for $sid ===`n" -ForegroundColor Cyan
uv run python report.py $sid

# 4 · Open the report in the default browser.
$report = "d:\TSAI\ERAV3\S9\S9SharedCode\replay_$sid.html"
if (Test-Path $report) {
    Write-Host "Opening replay: $report`n" -ForegroundColor Green
    Invoke-Item $report
} else {
    Write-Host "Report not found at $report" -ForegroundColor Yellow
}
