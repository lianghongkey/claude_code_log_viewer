#!/usr/bin/env python3
"""
Claude Code API 代理服务器
用于转发本地 Claude Code 的 API 请求到指定的目标服务器
"""

import http.server
import json
import urllib.request
import urllib.error
import sys
import os
from datetime import datetime

# 默认配置
DEFAULT_CONFIG = {
    "target_url": "https://ccmax.laoanclaude.top",
    "port": 8900,
    "log_dir": "logs"
}

# 全局配置
config = DEFAULT_CONFIG.copy()


def sanitize_sensitive_data(data):
    """过滤敏感信息（如 Authorization 等）"""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # 过滤敏感的 header 字段
            if key.lower() in ['authorization', 'x-api-key', 'api-key', 'token']:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = sanitize_sensitive_data(value)
            elif isinstance(value, list):
                sanitized[key] = [sanitize_sensitive_data(item) for item in value]
            else:
                sanitized[key] = value
        return sanitized
    elif isinstance(data, list):
        return [sanitize_sensitive_data(item) for item in data]
    else:
        return data


def save_log_entry(log_data):
    """保存日志条目到文件"""
    try:
        log_dir = config.get("log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)

        # 使用日期作为文件名
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"proxy_{date_str}.jsonl")

        # 过滤敏感信息
        sanitized_data = sanitize_sensitive_data(log_data)

        # 追加日志条目
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(sanitized_data, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"⚠ 保存日志失败: {e}")


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """处理代理请求的 HTTP 处理器"""

    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/config':
            self._handle_get_config()
        elif self.path == '/health':
            self._handle_health()
        else:
            self._proxy_request('GET')

    def do_POST(self):
        """处理 POST 请求"""
        if self.path == '/config':
            self._handle_set_config()
        else:
            self._proxy_request('POST')

    def do_PUT(self):
        """处理 PUT 请求"""
        self._proxy_request('PUT')

    def do_DELETE(self):
        """处理 DELETE 请求"""
        self._proxy_request('DELETE')

    def _handle_health(self):
        """健康检查端点"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {
            "status": "ok",
            "target_url": config["target_url"]
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

    def _handle_get_config(self):
        """获取当前配置"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(config, ensure_ascii=False).encode())

    def _handle_set_config(self):
        """更新配置"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            new_config = json.loads(body.decode())

            # 更新配置
            if "target_url" in new_config:
                config["target_url"] = new_config["target_url"].rstrip('/')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "配置已更新"}, ensure_ascii=False).encode())
        except Exception as e:
            self._send_error(400, f"配置更新失败: {str(e)}")

    def _proxy_request(self, method):
        """转发请求到目标服务器"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "method": method,
            "path": self.path,
            "request": {},
            "response": {}
        }

        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # 构建目标 URL
            target_url = config["target_url"] + self.path

            # 准备请求头 - 直接转发原始请求头
            headers = {}
            for header in self.headers:
                if header.lower() not in ['host', 'connection']:
                    headers[header] = self.headers.get(header)

            # 记录请求信息
            log_entry["request"]["url"] = target_url
            log_entry["request"]["headers"] = dict(headers)
            if body:
                try:
                    log_entry["request"]["body"] = json.loads(body.decode('utf-8'))
                except:
                    log_entry["request"]["body"] = body.decode('utf-8', errors='ignore')

            # 打印请求日志
            print(f"\n→ {method} {self.path}")
            print(f"  目标: {target_url}")
            if body:
                print(f"  请求体: {len(body)} bytes")

            # 发送请求
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=headers,
                method=method
            )

            with urllib.request.urlopen(req, timeout=300) as response:
                response_body = response.read()

                # 记录响应信息
                log_entry["response"]["status"] = response.status
                log_entry["response"]["headers"] = dict(response.headers)
                try:
                    log_entry["response"]["body"] = json.loads(response_body.decode('utf-8'))
                except:
                    log_entry["response"]["body"] = response_body.decode('utf-8', errors='ignore')

                # 打印响应日志
                print(f"← {response.status} ({len(response_body)} bytes)")

                # 保存日志
                save_log_entry(log_entry)

                # 转发响应
                self.send_response(response.status)

                # 转发响应头
                for header, value in response.headers.items():
                    if header.lower() not in ['transfer-encoding', 'connection']:
                        self.send_header(header, value)

                self.end_headers()
                self.wfile.write(response_body)

        except urllib.error.HTTPError as e:
            error_body = e.read()

            # 记录错误响应
            log_entry["response"]["status"] = e.code
            log_entry["response"]["headers"] = dict(e.headers)
            try:
                log_entry["response"]["body"] = json.loads(error_body.decode('utf-8'))
            except:
                log_entry["response"]["body"] = error_body.decode('utf-8', errors='ignore')
            log_entry["error"] = f"{e.code} {e.reason}"

            # 打印 HTTP 错误日志
            print(f"✗ {e.code} {e.reason}")
            if error_body:
                error_preview = error_body[:300].decode('utf-8', errors='ignore')
                print(f"  {error_preview}")

            # 保存日志
            save_log_entry(log_entry)

            # 转发 HTTP 错误
            self.send_response(e.code)
            for header, value in e.headers.items():
                if header.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(error_body)

        except Exception as e:
            # 记录异常
            log_entry["error"] = f"{type(e).__name__}: {str(e)}"
            save_log_entry(log_entry)

            # 打印异常日志
            print(f"✗ 异常: {type(e).__name__}: {str(e)}")

            self._send_error(500, f"代理请求失败: {str(e)}")

    def _send_error(self, code, message):
        """发送错误响应"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = {"error": message}
        self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def load_config_file():
    """从配置文件加载配置"""
    try:
        with open('proxy_config.json', 'r') as f:
            file_config = json.load(f)
            config.update(file_config)
            print(f"✓ 已加载配置文件 proxy_config.json")
    except FileNotFoundError:
        print("ℹ 未找到配置文件 proxy_config.json，使用默认配置")
    except Exception as e:
        print(f"⚠ 加载配置文件失败: {e}")


def save_config_file():
    """保存配置到文件"""
    try:
        with open('proxy_config.json', 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✓ 配置已保存到 proxy_config.json")
    except Exception as e:
        print(f"⚠ 保存配置文件失败: {e}")


def main():
    """启动代理服务器"""
    # 加载配置文件
    load_config_file()

    # 从命令行参数获取端口
    port = config["port"]
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'")
            sys.exit(1)

    # 启动服务器
    server_address = ('', port)
    httpd = http.server.HTTPServer(server_address, ProxyHandler)

    print("\n" + "="*60)
    print("Claude Code API 代理服务器")
    print("="*60)
    print(f"监听地址: http://localhost:{port}")
    print(f"目标 URL: {config['target_url']}")
    print(f"日志目录: {config.get('log_dir', 'logs')}/")
    print("\n管理端点:")
    print(f"  GET  /health  - 健康检查")
    print(f"  GET  /config  - 查看配置")
    print(f"  POST /config  - 更新配置 (JSON: {{\"target_url\": \"...\"}})")
    print("\n所有其他请求将转发到目标服务器")
    print("="*60 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n正在关闭服务器...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
