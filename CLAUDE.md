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

**index.html** — Single-file SPA with rendering pipeline:
- `renderConversation()` → filters entries by type (user/assistant/summary) → `renderMessage()`
- User messages: `renderContent()` → marked.js for Markdown, delegates to `renderToolUse()`/`renderToolResultBlock()` for tool blocks
- Assistant messages: `renderAssistantContent()` — similar but thinking blocks default collapsed
- Summary messages: reads from `m.summary` field (not `m.message.content`)
- Tool results: `tryHighlightResult()` auto-detects JSON (→ `colorizeJson()`), numbered code, or plain text
- Large results: `parsePersistedOutput()` detects persisted-output markers, provides async load button

## Key Conventions

- UI text is in Chinese (zh-CN)
- CSS uses custom properties (`:root` variables) for theming
- Collapsible sections (`makeCollapsible()`) used for thinking, tool calls, and results
- Security: path traversal prevention via `..`/`/` checks in server.py
- JSONL entry types: `user`, `assistant`, `summary` — summary has `summary` field at top level, others use `message.content`
