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
        elif self.path == '/api/files':
            self._serve_file_list()
        elif self.path.startswith('/api/log?'):
            self._serve_log_entries()
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

    def _serve_log_entries(self):
        """Serve log entries for a specific file."""
        # Parse query string
        query = self.path.split('?', 1)[1] if '?' in self.path else ''
        params = {}
        for param in query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value

        filename = params.get('file', '')
        if not filename:
            self.send_error(400)
            return

        entries = get_log_entries(filename)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {
            "entries": entries,
            "filename": filename
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

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
.content-block { background: var(--bg-tertiary); border-radius: 4px; padding: 12px;
  font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.user-content { background: var(--user-bg); border-left: 3px solid var(--success); }
.assistant-content { background: var(--assistant-bg); border-left: 3px solid var(--accent); }
.info-line { font-size: 12px; color: var(--text-muted); }
.empty-state { display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--text-muted); font-size: 15px; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 10px;
  background: var(--bg-tertiary); color: var(--text-muted); font-weight: 500; }
.error-badge { background: #ffebe9; color: var(--error); }
</style>
</head>
<body>
<button class="expand-btn" id="expandBtn" onclick="toggleSidebar()">▶</button>
<div class="container">
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <span>日志文件</span>
      <button class="toggle-btn" onclick="toggleSidebar()" title="隐藏侧边栏">◀</button>
    </div>
    <div class="file-list" id="fileList"></div>
    <div class="resize-handle" id="resizeHandle"></div>
  </div>
  <div class="main">
    <div class="main-header" id="header">选择一个日志文件查看</div>
    <div class="entries" id="entries">
      <div class="empty-state">从左侧面板选择一个日志文件</div>
    </div>
  </div>
</div>
<script>
hljs.configure({ ignoreUnescapedHTML: true });

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

function extractContent(content) {
  if (!content) return '';
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.map(item => {
      if (typeof item === 'string') return item;
      if (item.type === 'text' && item.text) return item.text;
      if (item.content) return extractContent(item.content);
      return '';
    }).filter(t => t).join('');
  }
  if (content.text) return content.text;
  if (content.content) return extractContent(content.content);
  return '';
}

async function loadFileList() {
  try {
    const res = await fetch('/api/files');
    const files = await res.json();
    renderFileList(files);
  } catch (e) {
    console.error('加载文件列表失败:', e);
  }
}

function renderFileList(files) {
  const container = document.getElementById('fileList');
  if (!files.length) {
    container.innerHTML = '<div class="empty-state">暂无日志文件</div>';
    return;
  }
  container.innerHTML = files.map(f => `
    <div class="file-item" onclick="loadLog('${f.name}')" data-name="${f.name}">
      <div class="file-name">${escapeHtml(f.display_name)}</div>
      <div class="file-meta">
        <span>${escapeHtml(f.formatted_time)}</span>
        <span>${f.count} 条</span>
        <span>${formatSize(f.size)}</span>
      </div>
      ${f.preview ? `<div class="file-preview">${escapeHtml(f.preview)}</div>` : ''}
    </div>
  `).join('');
}

async function loadLog(filename) {
  try {
    document.querySelectorAll('.file-item').forEach(f => f.classList.remove('active'));
    document.querySelector(`[data-name="${filename}"]`)?.classList.add('active');

    const res = await fetch(`/api/log?file=${encodeURIComponent(filename)}`);
    const data = await res.json();

    document.getElementById('header').textContent = `${data.filename} (${data.entries.length} 条记录)`;
    renderEntries(data.entries);
  } catch (e) {
    console.error('加载日志失败:', e);
    document.getElementById('entries').innerHTML = '<div class="empty-state">加载失败</div>';
  }
}

function renderEntries(entries) {
  const container = document.getElementById('entries');
  if (!entries.length) {
    container.innerHTML = '<div class="empty-state">此日志文件为空</div>';
    return;
  }

  const html = entries.map(entry => {
    const method = entry.method || 'UNKNOWN';
    const path = entry.path || '/';
    const timestamp = entry.timestamp || '';
    const status = entry.response?.status || 0;
    const hasError = entry.error || status >= 400;
    const statusClass = status >= 200 && status < 300 ? 'success' : 'error';
    const timeStr = formatTime(timestamp);

    let bodyHtml = '';

    // Extract user messages from request
    if (entry.request?.body?.messages) {
      const messages = entry.request.body.messages;
      messages.forEach(msg => {
        if (msg.role === 'user') {
          const content = extractContent(msg.content);
          if (content) {
            bodyHtml += '<div class="section">';
            bodyHtml += '<div class="section-title">👤 User 发送</div>';
            bodyHtml += `<div class="content-block user-content">${escapeHtml(content)}</div>`;
            bodyHtml += '</div>';
          }
        }
      });
    }

    // Extract assistant response
    if (entry.response?.body?.content) {
      const content = extractContent(entry.response.body.content);
      if (content) {
        bodyHtml += '<div class="section">';
        bodyHtml += '<div class="section-title">🤖 Assistant 返回</div>';
        bodyHtml += `<div class="content-block assistant-content">${escapeHtml(content)}</div>`;
        bodyHtml += '</div>';
      }
    }

    // Show model and usage info
    if (entry.response?.body) {
      const res = entry.response.body;
      const infoParts = [];
      if (res.model) infoParts.push(`模型: ${res.model}`);
      if (res.usage) {
        const u = res.usage;
        if (u.input_tokens) infoParts.push(`输入: ${u.input_tokens.toLocaleString()}`);
        if (u.output_tokens) infoParts.push(`输出: ${u.output_tokens.toLocaleString()}`);
        if (u.cache_read_input_tokens) infoParts.push(`缓存读取: ${u.cache_read_input_tokens.toLocaleString()}`);
      }
      if (infoParts.length > 0) {
        bodyHtml += '<div class="section">';
        bodyHtml += '<div class="section-title">ℹ️ 信息</div>';
        bodyHtml += `<div class="info-line">${infoParts.join(' | ')}</div>`;
        bodyHtml += '</div>';
      }
    }

    // Error section
    if (entry.error) {
      bodyHtml += '<div class="section">';
      bodyHtml += '<div class="section-title">❌ 错误</div>';
      bodyHtml += `<div class="content-block" style="color: var(--error); background: #ffebe9;">${escapeHtml(entry.error)}</div>`;
      bodyHtml += '</div>';
    }

    // If no useful content found, show message
    if (!bodyHtml) {
      bodyHtml = '<div class="empty-state" style="height: auto; padding: 20px;">无可显示内容</div>';
    }

    return `
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
  }).join('');

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

    port = 8901
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
