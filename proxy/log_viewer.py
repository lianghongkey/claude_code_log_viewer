#!/usr/bin/env python3
"""Proxy log viewer web server."""

import http.server
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")


def format_time(timestamp_str: str) -> str:
    """Format ISO timestamp to readable string."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M:%S")
        elif dt.year == now.year:
            return dt.strftime("%m-%d %H:%M")
        else:
            return dt.strftime("%Y-%m-%d")
    except:
        return timestamp_str


def get_log_preview(log_file: Path) -> str:
    """Extract first request path as preview."""
    if not log_file.exists():
        return ""
    try:
        with open(log_file, encoding="utf-8") as f:
            line = f.readline().strip()
            if line:
                entry = json.loads(line)
                method = entry.get("method", "")
                path = entry.get("path", "")
                return f"{method} {path}"
    except:
        pass
    return ""


def list_log_files() -> list:
    """List all log files with metadata."""
    if not LOG_DIR.exists():
        return []

    files = []
    for log_file in sorted(LOG_DIR.glob("proxy_*.jsonl"), reverse=True):
        mtime = log_file.stat().st_mtime
        size = log_file.stat().st_size
        preview = get_log_preview(log_file)

        # Count entries
        count = 0
        try:
            with open(log_file, encoding="utf-8") as f:
                count = sum(1 for _ in f)
        except:
            pass

        files.append({
            "name": log_file.name,
            "display_name": log_file.stem.replace("proxy_", ""),
            "mtime": mtime,
            "size": size,
            "count": count,
            "preview": preview,
            "formatted_time": format_time(datetime.fromtimestamp(mtime).isoformat())
        })

    return files


def list_all_entries() -> list:
    """List all log entries from all files, sorted by timestamp."""
    if not LOG_DIR.exists():
        return []

    all_entries = []
    for log_file in LOG_DIR.glob("proxy_*.jsonl"):
        try:
            with open(log_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            # Add metadata for identification
                            entry["_file"] = log_file.name
                            entry["_line"] = line_num
                            all_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
        except:
            continue

    # Sort by timestamp (newest first)
    all_entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return all_entries


def get_single_entry(filename: str, line_num: int) -> dict:
    """Get a single entry from a log file by line number."""
    log_file = LOG_DIR / filename
    if not log_file.exists() or not str(log_file.resolve()).startswith(str(LOG_DIR.resolve())):
        return {}

    try:
        with open(log_file, encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                if idx == line_num:
                    line = line.strip()
                    if line:
                        return json.loads(line)
                    break
    except:
        pass

    return {}


def get_log_entries(filename: str) -> list:
    """Read all entries from a log file."""
    log_file = LOG_DIR / filename
    if not log_file.exists() or not str(log_file.resolve()).startswith(str(LOG_DIR.resolve())):
        return []

    entries = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
    except:
        pass

    return entries


class ViewerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for log viewer."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._serve_index()
        elif self.path == '/api/entries':
            self._serve_all_entries()
        elif self.path.startswith('/api/entry?'):
            self._serve_single_entry()
        else:
            self.send_error(404)

    def _serve_index(self):
        """Serve the main HTML page."""
        html = get_index_html()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _serve_file_list(self):
        """Serve list of log files."""
        files = list_log_files()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(files, ensure_ascii=False).encode('utf-8'))

    def _serve_all_entries(self):
        """Serve all log entries from all files."""
        entries = list_all_entries()
        # Create summary for each entry
        summaries = []
        for entry in entries:
            method = entry.get("method", "")
            path = entry.get("path", "")
            timestamp = entry.get("timestamp", "")
            status = entry.get("response", {}).get("status", 0)

            summaries.append({
                "file": entry.get("_file", ""),
                "line": entry.get("_line", 0),
                "method": method,
                "path": path,
                "timestamp": timestamp,
                "status": status,
                "formatted_time": format_time(timestamp),
                "preview": f"{method} {path}"
            })

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(summaries, ensure_ascii=False).encode('utf-8'))

    def _serve_single_entry(self):
        """Serve a single log entry."""
        # Parse query string
        query = self.path.split('?', 1)[1] if '?' in self.path else ''
        params = {}
        for param in query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value

        filename = params.get('file', '')
        line_num = params.get('line', '0')

        if not filename or not line_num.isdigit():
            self.send_error(400)
            return

        entry = get_single_entry(filename, int(line_num))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(entry, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """Custom log format."""
        pass  # Suppress default logging


def get_index_html() -> str:
    """Return the main HTML page."""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Proxy Log Viewer</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #fff; --bg-secondary: #f6f8fa; --bg-tertiary: #eef1f4;
  --border: #d1d9e0; --text: #1f2328; --text-muted: #656d76;
  --accent: #0969da; --success: #1a7f37; --error: #cf222e;
  --warning: #bf5700; --user-bg: #f0fff4; --assistant-bg: #f0f7ff;
}
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 15px; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }
.container { display: flex; height: 100vh; }
.sidebar { width: 280px; min-width: 200px; max-width: 500px; background: var(--bg-secondary);
  border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0;
  position: relative; transition: width 0.15s, min-width 0.15s; }
.sidebar.collapsed { width: 0; min-width: 0; overflow: hidden; border-right: none; }
.sidebar-header { padding: 8px 12px; border-bottom: 1px solid var(--border);
  font-weight: 600; font-size: 14px; color: var(--accent); display: flex;
  justify-content: space-between; align-items: center; }
.toggle-btn { background: none; border: none; cursor: pointer; padding: 2px 6px;
  color: var(--text-muted); font-size: 14px; border-radius: 3px; }
.toggle-btn:hover { background: var(--bg-tertiary); color: var(--text); }
.resize-handle { position: absolute; right: 0; top: 0; bottom: 0; width: 4px;
  cursor: col-resize; background: transparent; }
.resize-handle:hover, .resize-handle.dragging { background: var(--accent); }
.expand-btn { position: fixed; left: 0; top: 8px; background: var(--bg-secondary);
  border: 1px solid var(--border); border-left: none; border-radius: 0 4px 4px 0;
  padding: 4px 8px; cursor: pointer; font-size: 14px; color: var(--text-muted);
  display: none; z-index: 10; }
.expand-btn:hover { background: var(--bg-tertiary); color: var(--text); }
.expand-btn.show { display: block; }
.file-list { flex: 1; overflow-y: auto; }
.file-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--border); }
.file-item:hover { background: var(--bg-tertiary); }
.file-item.active { background: var(--accent); color: #fff; }
.file-item.active .file-meta, .file-item.active .file-preview { color: rgba(255,255,255,0.8); }
.file-name { font-size: 15px; font-weight: 500; margin-bottom: 3px; }
.file-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 12px; }
.file-preview { font-size: 13px; color: var(--text-muted); margin-top: 3px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.main-header { padding: 8px 16px; border-bottom: 1px solid var(--border);
  font-size: 13px; color: var(--text-muted); background: var(--bg-secondary); }
.entries { flex: 1; overflow-y: auto; padding: 12px 16px; }
.entry { margin-bottom: 16px; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.entry-header { padding: 8px 12px; background: var(--bg-secondary); display: flex;
  align-items: center; gap: 10px; font-size: 13px; border-bottom: 1px solid var(--border); }
.entry-method { font-weight: 600; font-family: 'SF Mono', Consolas, monospace; }
.entry-method.GET { color: var(--success); }
.entry-method.POST { color: var(--accent); }
.entry-method.PUT { color: var(--warning); }
.entry-method.DELETE { color: var(--error); }
.entry-path { color: var(--text); font-family: 'SF Mono', Consolas, monospace; flex: 1; }
.entry-status { font-weight: 600; font-family: 'SF Mono', Consolas, monospace; }
.entry-status.success { color: var(--success); }
.entry-status.error { color: var(--error); }
.entry-time { color: var(--text-muted); font-size: 12px; }
.entry-body { padding: 12px; }
.section { margin-bottom: 12px; }
.section:last-child { margin-bottom: 0; }
.section-title { font-size: 12px; font-weight: 600; color: var(--text);
  margin-bottom: 6px; letter-spacing: 0.03em; }
.content-block { background: var(--bg-tertiary); border-radius: 4px; padding: 0;
  margin-bottom: 8px; border: 1px solid var(--border); overflow: hidden; }
.content-block:last-child { margin-bottom: 0; }
.block-label { font-size: 13px; font-weight: 600; padding: 8px 12px;
  background: var(--bg-secondary); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 6px; }
.block-label.collapsible { cursor: pointer; user-select: none; }
.block-label.collapsible:hover { background: var(--bg-tertiary); }
.toggle-icon { font-size: 10px; color: var(--text-muted); transition: transform 0.15s; }
.block-content { padding: 12px; font-size: 14px; line-height: 1.6;
  word-break: break-word; overflow-y: visible; }
.block-content.collapsed { display: none; }
.text-block .block-content { background: #f6f8fa; }
.text-block .block-content.raw-text { white-space: pre-wrap; }
.thinking-block .block-label { background: #fff8e1; border-bottom-color: #ffe082; }
.thinking-block .block-content { background: #fffef7; color: #5f4c00; }
.tool-use-block .block-label { background: #e3f2fd; border-bottom-color: #90caf9; }
.tool-use-block .block-content { background: #f0f7ff; }
.tool-result-block .block-label { background: #e8f5e9; border-bottom-color: #a5d6a7; }
.tool-result-block .block-content { background: #f1f8f4; }
.tool-result-block.error .block-label { background: #ffebee; border-bottom-color: #ef9a9a; }
.tool-result-block.error .block-content { background: #fff5f5; color: var(--error); }
.system-block .block-label { background: #f3e5f5; border-bottom-color: #ce93d8; }
.system-block .block-content { background: #faf5fb; color: #4a148c; }
.tools-block .block-label { background: #e0f2f1; border-bottom-color: #80cbc4; }
.tools-block .block-content { background: #f0f9f8; }
.headers-block .block-label { background: #fce4ec; border-bottom-color: #f48fb1; }
.headers-block .block-content { background: #fef5f8; }
.tool-id { font-size: 11px; color: var(--text-muted); font-family: 'SF Mono', Consolas, monospace; }
.json-content, .result-content { font-family: 'SF Mono', Consolas, monospace;
  font-size: 13px; background: #f6f8fa; padding: 8px; border-radius: 3px;
  overflow-x: auto; margin: 0; line-height: 1.5; }
.json-content code, .result-content code { background: none; padding: 0; white-space: pre; }
.markdown-content { line-height: 1.7; }
.markdown-content h1, .markdown-content h2, .markdown-content h3 { margin-top: 16px; margin-bottom: 8px; }
.markdown-content h1:first-child, .markdown-content h2:first-child, .markdown-content h3:first-child { margin-top: 0; }
.markdown-content h1 { font-size: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
.markdown-content h2 { font-size: 1.3em; }
.markdown-content h3 { font-size: 1.1em; }
.markdown-content p { margin-bottom: 12px; }
.markdown-content p:last-child { margin-bottom: 0; }
.markdown-content ul, .markdown-content ol { margin-left: 20px; margin-bottom: 12px; }
.markdown-content li { margin-bottom: 4px; }
.markdown-content code { background: #f6f8fa; padding: 2px 6px; border-radius: 3px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 0.9em; }
.markdown-content pre { background: #f6f8fa; padding: 12px; border-radius: 4px;
  overflow-x: auto; margin-bottom: 12px; }
.markdown-content pre:last-child { margin-bottom: 0; }
.markdown-content pre code { background: none; padding: 0; }
.markdown-content blockquote { border-left: 3px solid var(--border); padding-left: 12px;
  color: var(--text-muted); margin-bottom: 12px; }
.markdown-content a { color: var(--accent); text-decoration: none; }
.markdown-content a:hover { text-decoration: underline; }
.raw-text { white-space: pre-wrap; font-family: 'SF Mono', Consolas, monospace; font-size: 13px; }
.user-section { background: var(--user-bg); padding: 12px; border-radius: 4px;
  border-left: 3px solid var(--success); margin-bottom: 12px; }
.assistant-section { background: var(--assistant-bg); padding: 12px; border-radius: 4px;
  border-left: 3px solid var(--accent); margin-bottom: 12px; }
.unknown-block .block-label { background: #fafafa; }
.info-line { font-size: 12px; color: var(--text-muted); }
.empty-state { display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--text-muted); font-size: 15px; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 10px;
  background: var(--bg-tertiary); color: var(--text-muted); font-weight: 500; }
.error-block { background: #ffebe9; border-left: 3px solid var(--error); }
.error-block .block-content { color: var(--error); }
.diff-view { font-family: 'SF Mono', Consolas, monospace; font-size: 13px; overflow-x: auto; }
.diff-file-header { padding: 5px 12px; background: #f6f8fa; border-bottom: 1px solid var(--border); font-size: 12px; color: var(--text-muted); font-weight: 600; }
.diff-replace-all { padding: 3px 12px; background: #fff8e1; font-size: 11px; color: #bf5700; border-bottom: 1px solid #ffe082; }
.diff-line { display: flex; padding: 1px 0; white-space: pre; line-height: 1.6; min-height: 21px; }
.diff-sign { width: 28px; flex-shrink: 0; text-align: center; user-select: none; font-weight: 700; }
.diff-line-content { flex: 1; padding-right: 12px; white-space: pre-wrap; word-break: break-all; }
.diff-del { background: #ffebe9; color: #82071e; } .diff-del .diff-sign { color: #cf222e; }
.diff-add { background: #dafbe1; color: #116329; } .diff-add .diff-sign { color: #1a7f37; }
</style>
</head>
<body>
<button class="expand-btn" id="expandBtn" onclick="toggleSidebar()">▶</button>
<div class="container">
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <span>请求记录</span>
      <button class="toggle-btn" onclick="toggleSidebar()" title="隐藏侧边栏">◀</button>
    </div>
    <div class="file-list" id="fileList"></div>
    <div class="resize-handle" id="resizeHandle"></div>
  </div>
  <div class="main">
    <div class="main-header" id="header">选择一条记录查看详情</div>
    <div class="entries" id="entries">
      <div class="empty-state">从左侧面板选择一条记录</div>
    </div>
  </div>
</div>
<script>
hljs.configure({ ignoreUnescapedHTML: true });

// Configure marked for better rendering
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value;
      } catch (e) {}
    }
    return hljs.highlightAuto(code).value;
  }
});

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderMarkdown(text) {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch (e) {
    return escapeHtml(text);
  }
}

function highlightCode(code, lang) {
  if (!code) return '';
  try {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  } catch (e) {
    return escapeHtml(code);
  }
}

function detectAndHighlight(text) {
  if (!text) return escapeHtml(text);

  const trimmed = text.trim();

  // Try to detect if it's JSON
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      JSON.parse(trimmed);
      const highlighted = highlightCode(text, 'json');
      return '<pre class="json-content"><code>' + highlighted + '</code></pre>';
    } catch (e) {}
  }

  // Check if it looks like code (has common code patterns)
  if (/^(function|const|let|var|class|import|export|def|class |public |private )/m.test(trimmed) ||
      /[{}\\[\\];]/.test(trimmed)) {
    const highlighted = highlightCode(text, '');
    return '<pre class="result-content"><code>' + highlighted + '</code></pre>';
  }

  // Check if text has many consecutive newlines (likely formatted text)
  const newlineCount = (text.match(/\\n/g) || []).length;
  const textLength = text.length;

  // If more than 10% newlines, it's likely pre-formatted, keep as-is
  if (newlineCount > 10 && newlineCount / textLength > 0.1) {
    return '<div class="raw-text">' + escapeHtml(text) + '</div>';
  }

  // Otherwise render as markdown (will normalize whitespace)
  return '<div class="markdown-content">' + renderMarkdown(text) + '</div>';
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  try {
    const dt = new Date(timestamp);
    return dt.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  } catch {
    return timestamp;
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatJson(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

function renderEditDiff(input) {
  const filePath = input.file_path || input.path || '';
  const oldStr = input.old_string || '';
  const newStr = input.new_string || '';
  if (!oldStr && !newStr) {
    return '<pre class="json-content"><code>' + highlightCode(formatJson(input), 'json') + '</code></pre>';
  }
  let html = '<div class="diff-view">';
  if (filePath) html += `<div class="diff-file-header">📄 ${escapeHtml(filePath)}</div>`;
  if (input.replace_all) html += '<div class="diff-replace-all">⚠ replace_all 模式</div>';
  oldStr.split('\\n').forEach(line => {
    html += `<div class="diff-line diff-del"><span class="diff-sign">-</span><span class="diff-line-content">${escapeHtml(line)}</span></div>`;
  });
  newStr.split('\\n').forEach(line => {
    html += `<div class="diff-line diff-add"><span class="diff-sign">+</span><span class="diff-line-content">${escapeHtml(line)}</span></div>`;
  });
  html += '</div>';
  return html;
}

function renderContentBlock(block, index) {
  if (!block || !block.type) return '';

  let html = '';
  const blockId = `block-${Date.now()}-${index}`;

  switch (block.type) {
    case 'text':
      if (block.text) {
        html += `<div class="content-block text-block">
          <div class="block-label">💬 文本</div>
          <div class="block-content">${detectAndHighlight(block.text)}</div>
        </div>`;
      }
      break;

    case 'thinking':
      if (block.thinking) {
        html += `<div class="content-block thinking-block">
          <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
            <span class="toggle-icon">▶</span> 🤔 思考过程
          </div>
          <div class="block-content collapsed" id="${blockId}">${detectAndHighlight(block.thinking)}</div>
        </div>`;
      }
      break;

    case 'tool_use':
      const toolName = block.name || 'unknown';
      const isEditTool = toolName === 'Edit' || toolName === 'edit';
      let toolBody = '';
      if (isEditTool && block.input) {
        toolBody = renderEditDiff(block.input);
      } else {
        const toolInput = block.input ? formatJson(block.input) : '';
        toolBody = `<pre class="json-content"><code>${highlightCode(toolInput, 'json')}</code></pre>`;
      }
      html += `<div class="content-block tool-use-block">
        <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
          <span class="toggle-icon">▶</span> 🔧 工具调用: <code>${escapeHtml(toolName)}</code>
          ${block.id ? `<span class="tool-id">[${escapeHtml(block.id)}]</span>` : ''}
        </div>
        <div class="block-content collapsed" id="${blockId}">
          ${toolBody}
        </div>
      </div>`;
      break;

    case 'tool_result':
      const toolResultId = block.tool_use_id || '';
      const isError = block.is_error || false;
      let resultContent = '';

      if (typeof block.content === 'string') {
        resultContent = block.content;
      } else if (Array.isArray(block.content)) {
        resultContent = block.content.map(c => {
          if (typeof c === 'string') return c;
          if (c.type === 'text') return c.text || '';
          return formatJson(c);
        }).join('\\n');
      } else {
        resultContent = formatJson(block.content);
      }

      html += `<div class="content-block tool-result-block ${isError ? 'error' : ''}">
        <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
          <span class="toggle-icon">▶</span> ${isError ? '❌' : '✅'} 工具结果
          ${toolResultId ? `<span class="tool-id">[${escapeHtml(toolResultId)}]</span>` : ''}
        </div>
        <div class="block-content collapsed" id="${blockId}">
          ${detectAndHighlight(resultContent)}
        </div>
      </div>`;
      break;

    default:
      html += `<div class="content-block unknown-block">
        <div class="block-label">❓ ${escapeHtml(block.type)}</div>
        <div class="block-content"><pre>${escapeHtml(formatJson(block))}</pre></div>
      </div>`;
  }

  return html;
}

function toggleBlock(blockId) {
  const block = document.getElementById(blockId);
  const label = block?.previousElementSibling;
  if (block && label) {
    block.classList.toggle('collapsed');
    const icon = label.querySelector('.toggle-icon');
    if (icon) {
      icon.textContent = block.classList.contains('collapsed') ? '▶' : '▼';
    }
  }
}

async function loadFileList() {
  try {
    const res = await fetch('/api/entries');
    const entries = await res.json();
    renderFileList(entries);
  } catch (e) {
    console.error('加载记录列表失败:', e);
  }
}

function renderFileList(entries) {
  const container = document.getElementById('fileList');
  if (!entries.length) {
    container.innerHTML = '<div class="empty-state">暂无日志记录</div>';
    return;
  }
  container.innerHTML = entries.map(e => `
    <div class="file-item" onclick="loadEntry('${e.file}', ${e.line})" data-key="${e.file}-${e.line}">
      <div class="file-name">${escapeHtml(e.method)} ${escapeHtml(e.path)}</div>
      <div class="file-meta">
        <span>${escapeHtml(e.formatted_time)}</span>
        ${e.status ? `<span class="entry-status ${e.status >= 200 && e.status < 300 ? 'success' : 'error'}">${e.status}</span>` : ''}
      </div>
    </div>
  `).join('');
}

async function loadEntry(filename, lineNum) {
  try {
    document.querySelectorAll('.file-item').forEach(f => f.classList.remove('active'));
    document.querySelector(`[data-key="${filename}-${lineNum}"]`)?.classList.add('active');

    const res = await fetch(`/api/entry?file=${encodeURIComponent(filename)}&line=${lineNum}`);
    const entry = await res.json();

    document.getElementById('header').textContent = `${entry.method || 'UNKNOWN'} ${entry.path || '/'} - ${filename}:${lineNum}`;
    renderEntry(entry);
  } catch (e) {
    console.error('加载记录失败:', e);
    document.getElementById('entries').innerHTML = '<div class="empty-state">加载失败</div>';
  }
}

function renderEntry(entry) {
  const container = document.getElementById('entries');
  if (!entry || Object.keys(entry).length === 0) {
    container.innerHTML = '<div class="empty-state">记录为空</div>';
    return;
  }

  const method = entry.method || 'UNKNOWN';
  const path = entry.path || '/';
  const timestamp = entry.timestamp || '';
  const status = entry.response?.status || 0;
  const hasError = entry.error || status >= 400;
  const statusClass = status >= 200 && status < 300 ? 'success' : 'error';
  const timeStr = formatTime(timestamp);

  let bodyHtml = '';

  // Render system prompt
  if (entry.request?.body?.system) {
    const system = entry.request.body.system;
    let systemText = '';

    if (Array.isArray(system)) {
      systemText = system.map(s => {
        if (typeof s === 'string') return s;
        if (s.type === 'text') return s.text || '';
        return JSON.stringify(s);
      }).join('\\n\\n');
    } else if (typeof system === 'string') {
      systemText = system;
    }

    if (systemText) {
      const blockId = `system-${Date.now()}`;
      bodyHtml += '<div class="section">';
      bodyHtml += `<div class="content-block system-block">
        <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
          <span class="toggle-icon">▶</span> ⚙️ System Prompt
        </div>
        <div class="block-content collapsed" id="${blockId}">
          <div class="raw-text">${escapeHtml(systemText)}</div>
        </div>
      </div>`;
      bodyHtml += '</div>';
    }
  }

  // Render tools
  if (entry.request?.body?.tools && Array.isArray(entry.request.body.tools)) {
    const tools = entry.request.body.tools;
    const blockId = `tools-${Date.now()}`;
    bodyHtml += '<div class="section">';
    bodyHtml += `<div class="content-block tools-block">
      <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
        <span class="toggle-icon">▶</span> 🔨 Tools <span class="badge">${tools.length}</span>
      </div>
      <div class="block-content collapsed" id="${blockId}">
        <pre class="json-content"><code>${highlightCode(formatJson(tools), 'json')}</code></pre>
      </div>
    </div>`;
    bodyHtml += '</div>';
  }

  // Render request messages
  if (entry.request?.body?.messages) {
    const messages = entry.request.body.messages;
    messages.forEach((msg, msgIdx) => {
      if (msg.role === 'user') {
        bodyHtml += '<div class="section user-section">';
        bodyHtml += '<div class="section-title">👤 User 发送</div>';

        if (Array.isArray(msg.content)) {
          msg.content.forEach((block, blockIdx) => {
            bodyHtml += renderContentBlock(block, `req-${msgIdx}-${blockIdx}`);
          });
        } else if (typeof msg.content === 'string') {
          bodyHtml += `<div class="content-block text-block">
            <div class="block-content">${escapeHtml(msg.content)}</div>
          </div>`;
        }

        bodyHtml += '</div>';
      } else if (msg.role === 'assistant') {
        bodyHtml += '<div class="section assistant-section">';
        bodyHtml += '<div class="section-title">🤖 Assistant (上下文)</div>';

        if (Array.isArray(msg.content)) {
          msg.content.forEach((block, blockIdx) => {
            bodyHtml += renderContentBlock(block, `req-asst-${msgIdx}-${blockIdx}`);
          });
        }

        bodyHtml += '</div>';
      }
    });
  }

  // Render response content
  if (entry.response?.body?.content) {
    bodyHtml += '<div class="section assistant-section">';
    bodyHtml += '<div class="section-title">🤖 Assistant 返回</div>';

    const content = entry.response.body.content;
    if (Array.isArray(content)) {
      content.forEach((block, blockIdx) => {
        bodyHtml += renderContentBlock(block, `resp-${blockIdx}`);
      });
    } else if (typeof content === 'string') {
      bodyHtml += `<div class="content-block text-block">
        <div class="block-content">${escapeHtml(content)}</div>
      </div>`;
    }

    bodyHtml += '</div>';
  }

  // Show model and usage info
  if (entry.response?.body) {
    const res = entry.response.body;
    const infoParts = [];
    if (res.model) infoParts.push(`模型: ${res.model}`);
    if (res.id) infoParts.push(`ID: ${res.id}`);
    if (res.usage) {
      const u = res.usage;
      if (u.input_tokens) infoParts.push(`输入: ${u.input_tokens.toLocaleString()}`);
      if (u.output_tokens) infoParts.push(`输出: ${u.output_tokens.toLocaleString()}`);
      if (u.cache_read_input_tokens) infoParts.push(`缓存读取: ${u.cache_read_input_tokens.toLocaleString()}`);
      if (u.cache_creation_input_tokens) infoParts.push(`缓存创建: ${u.cache_creation_input_tokens.toLocaleString()}`);
    }
    if (res.stop_reason) infoParts.push(`停止原因: ${res.stop_reason}`);

    if (infoParts.length > 0) {
      bodyHtml += '<div class="section">';
      bodyHtml += '<div class="section-title">ℹ️ 响应信息</div>';
      bodyHtml += `<div class="info-line">${infoParts.join(' | ')}</div>`;
      bodyHtml += '</div>';
    }
  }

  // Show request info
  if (entry.request?.body) {
    const req = entry.request.body;
    const reqInfoParts = [];
    if (req.max_tokens) reqInfoParts.push(`max_tokens: ${req.max_tokens.toLocaleString()}`);
    if (req.temperature !== undefined) reqInfoParts.push(`temperature: ${req.temperature}`);
    if (req.top_p !== undefined) reqInfoParts.push(`top_p: ${req.top_p}`);
    if (req.top_k !== undefined) reqInfoParts.push(`top_k: ${req.top_k}`);
    if (req.stream !== undefined) reqInfoParts.push(`stream: ${req.stream}`);

    if (reqInfoParts.length > 0) {
      bodyHtml += '<div class="section">';
      bodyHtml += '<div class="section-title">📤 请求参数</div>';
      bodyHtml += `<div class="info-line">${reqInfoParts.join(' | ')}</div>`;
      bodyHtml += '</div>';
    }
  }

  // Show request headers (collapsed by default)
  if (entry.request?.headers) {
    const headers = entry.request.headers;
    const blockId = `headers-${Date.now()}`;
    bodyHtml += '<div class="section">';
    bodyHtml += `<div class="content-block headers-block">
      <div class="block-label collapsible" onclick="toggleBlock('${blockId}')">
        <span class="toggle-icon">▶</span> 📋 Request Headers
      </div>
      <div class="block-content collapsed" id="${blockId}">
        <pre class="json-content"><code>${highlightCode(formatJson(headers), 'json')}</code></pre>
      </div>
    </div>`;
    bodyHtml += '</div>';
  }

  // Error section
  if (entry.error) {
    bodyHtml += '<div class="section">';
    bodyHtml += '<div class="section-title">❌ 错误</div>';
    bodyHtml += `<div class="content-block error-block">
      <div class="block-content">${escapeHtml(entry.error)}</div>
    </div>`;
    bodyHtml += '</div>';
  }

  // If no useful content found, show message
  if (!bodyHtml) {
    bodyHtml = '<div class="empty-state" style="height: auto; padding: 20px;">无可显示内容</div>';
  }

  const html = `
    <div class="entry">
      <div class="entry-header">
        <span class="entry-method ${method}">${method}</span>
        <span class="entry-path">${escapeHtml(path)}</span>
        ${status ? `<span class="entry-status ${statusClass}">${status}</span>` : ''}
        ${hasError ? '<span class="badge error-badge">ERROR</span>' : ''}
        <span class="entry-time">${timeStr}</span>
      </div>
      <div class="entry-body">${bodyHtml}</div>
    </div>
  `;

  container.innerHTML = html;
}

// Sidebar toggle
let savedWidth = null;
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const expandBtn = document.getElementById('expandBtn');
  if (sidebar.classList.contains('collapsed')) {
    sidebar.classList.remove('collapsed');
    if (savedWidth) sidebar.style.width = savedWidth;
    expandBtn.classList.remove('show');
  } else {
    savedWidth = sidebar.style.width || null;
    sidebar.style.width = '';
    sidebar.classList.add('collapsed');
    expandBtn.classList.add('show');
  }
}

// Resize handle
(function() {
  const sidebar = document.getElementById('sidebar');
  const handle = document.getElementById('resizeHandle');
  let startX, startWidth;

  handle.addEventListener('mousedown', function(e) {
    startX = e.clientX;
    startWidth = sidebar.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    e.preventDefault();
  });

  function onMouseMove(e) {
    const newWidth = startWidth + (e.clientX - startX);
    if (newWidth >= 200 && newWidth <= 500) {
      sidebar.style.width = newWidth + 'px';
    }
  }

  function onMouseUp() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }
})();

loadFileList();
</script>
</body>
</html>"""


def main():
    """Start the log viewer server."""
    import sys

    port = 8902
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'")
            sys.exit(1)

    server_address = ('', port)
    httpd = http.server.HTTPServer(server_address, ViewerHandler)

    print("\n" + "="*60)
    print("Proxy Log Viewer")
    print("="*60)
    print(f"访问地址: http://localhost:{port}")
    print(f"日志目录: {LOG_DIR.resolve()}")
    print("="*60 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n正在关闭服务器...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
