# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A local web tool for visualizing Claude Code conversation logs (JSONL files from `~/.claude/projects/`). Zero external dependencies — Python 3 stdlib backend + vanilla JS frontend (single HTML file with embedded CSS/JS). CDN-loaded: marked.js (Markdown), highlight.js (syntax highlighting).

## Running

```bash
python3 server.py        # http://localhost:8899
python3 server.py 9000   # custom port
```

No build step, no package manager, no tests.

## Architecture

**server.py** — HTTP server (`http.server`) with REST API:
- `/api/projects` — list projects from `~/.claude/projects/`
- `/api/files?project=X` — list JSONL files with metadata (preview extracted from first 50 lines)
- `/api/file?project=X&file=Y` — return all entries from a JSONL file
- `/api/tool-result?project=X&session=Y&id=Z` — lazy-load persisted tool result files

**index.html** — Single-file SPA. Rendering pipeline is turn-based:
- `buildModel(entries)` — groups flat JSONL entries into turns: each real user message (not tool_result-only, not `isMeta`) starts a turn; assistant/system/summary entries attach to the current turn. Also builds `toolResults` map (`tool_use_id` → result block) and captures `ai-title`.
- `renderTurn()` — one card per turn: user prompt as header band, assistant flow as body, duration/tokens as footer.
- `renderToolRow()` — tool_use paired with its tool_result (via `toolResults` map) in a single collapsible row with status (✓/✗/无结果). Tool-result-only user messages are never rendered standalone.
- `renderUserString()` — parses `<command-name>`/`<local-command-stdout>`/`<system-reminder>` tags out of user text: commands become chips, injections become collapsed blocks, remainder rendered as Markdown.
- Outline panel (`renderOutline()` + `updateSpy()` scroll spy) — one entry per turn, click to jump; `j`/`k` keyboard navigation.
- Header toggles hide thinking/tools/system via body classes; light/dark theme via `data-theme` + localStorage.
- Tool results: `tryHighlightResult()` auto-detects JSON (→ `colorizeJson()`), numbered code, or plain text; `parsePersistedOutput()` detects persisted-output markers and provides an async load button.

## Key Conventions

- UI text is in Chinese (zh-CN)
- CSS uses custom properties (`:root` variables) for theming
- Collapsible sections (`makeCollapsible()`) used for thinking, tool calls, and results
- Security: path traversal prevention via `..`/`/` checks in server.py
- JSONL entry types: `user`, `assistant`, `summary` — summary has `summary` field at top level, others use `message.content`
