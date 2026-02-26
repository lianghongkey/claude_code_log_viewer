#!/usr/bin/env python3
"""Claude Code Log Viewer - Backend Server"""
import http.server, json, os, glob, sys
from urllib.parse import urlparse, parse_qs

CLAUDE_DIR = os.path.expanduser("~/.claude/projects")

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        if p.path == '/api/projects':
            return self.json_resp(self.get_projects())
        if p.path == '/api/files':
            return self.json_resp(self.get_files(q.get('project', [''])[0]))
        if p.path == '/api/file':
            return self.json_resp(self.get_file(q.get('project', [''])[0], q.get('file', [''])[0]))
        if p.path == '/api/tool-result':
            return self.get_tool_result(q.get('project', [''])[0],
                                        q.get('session', [''])[0],
                                        q.get('id', [''])[0])
        if p.path == '/':
            self.path = '/index.html'
        super().do_GET()

    def get_projects(self):
        out = []
        if not os.path.isdir(CLAUDE_DIR):
            return out
        for name in sorted(os.listdir(CLAUDE_DIR)):
            d = os.path.join(CLAUDE_DIR, name)
            if os.path.isdir(d):
                n = len(glob.glob(os.path.join(d, "*.jsonl")))
                if n:
                    display = '/' + name[1:].replace('-', '/') if name.startswith('-') else name
                    out.append({'name': name, 'display': display, 'count': n})
        return out

    def get_files(self, project):
        d = os.path.join(CLAUDE_DIR, project)
        if not os.path.isdir(d):
            return []
        out = []
        for f in glob.glob(os.path.join(d, "*.jsonl")):
            s = os.stat(f)
            out.append({'filename': os.path.basename(f), 'size': s.st_size,
                        'modified': s.st_mtime, **self._preview(f)})
        return sorted(out, key=lambda x: x['modified'], reverse=True)

    def _preview(self, path):
        pv, ts, model, ver = '', '', '', ''
        try:
            with open(path) as f:
                for i, line in enumerate(f):
                    if i > 50: break
                    try:
                        e = json.loads(line)
                    except:
                        continue
                    if e.get('type') == 'user' and not pv:
                        c = e.get('message', {}).get('content', '')
                        if isinstance(c, str):
                            pv = c[:120]
                        elif isinstance(c, list):
                            for item in c:
                                if isinstance(item, dict) and item.get('type') == 'text':
                                    pv = item['text'][:120]
                                    break
                        ts = e.get('timestamp', '')
                        ver = e.get('version', '')
                    if e.get('type') == 'assistant' and not model:
                        model = e.get('message', {}).get('model', '')
        except Exception:
            pass
        return {'preview': pv, 'timestamp': ts, 'model': model, 'version': ver}

    def get_file(self, project, filename):
        if '..' in filename or '/' in filename:
            return []
        fp = os.path.join(CLAUDE_DIR, project, filename)
        if not os.path.exists(fp):
            return []
        out = []
        session_id = filename.replace('.jsonl', '')
        with open(fp) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry['_sessionId'] = session_id
                    out.append(entry)
                except:
                    pass
        return out

    def get_tool_result(self, project, session, tool_id):
        # Security: prevent path traversal
        for val in (project, session, tool_id):
            if '..' in val or '/' in val:
                self.send_error(400)
                return
        fp = os.path.join(CLAUDE_DIR, project, session, 'tool-results', tool_id + '.txt')
        if not os.path.exists(fp):
            self.send_error(404)
            return
        try:
            with open(fp, 'r', errors='replace') as f:
                content = f.read()
            b = json.dumps({'content': content, 'size': os.path.getsize(fp)}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json;charset=utf-8')
            self.send_header('Content-Length', len(b))
            self.end_headers()
            self.wfile.write(b)
        except Exception as e:
            self.send_error(500, str(e))

    def json_resp(self, data):
        b = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json;charset=utf-8')
        self.send_header('Content-Length', len(b))
        self.end_headers()
        self.wfile.write(b)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    srv = http.server.HTTPServer(('0.0.0.0', port), Handler)
    print(f"\n  Claude Log Viewer → http://localhost:{port}\n")
    srv.serve_forever()
