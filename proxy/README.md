# Claude Code API 代理服务

用于转发本地 Claude Code 的 API 请求到指定的目标服务器。

## 功能特性

- ✅ 透明转发所有 HTTP 方法 (GET, POST, PUT, DELETE)
- ✅ 支持自定义目标 URL
- ✅ 配置持久化（保存到 `proxy_config.json`）
- ✅ 健康检查和配置管理端点
- ✅ 零外部依赖（仅使用 Python 3 标准库）
- ✅ 完整转发所有请求头（包括 API Key）
- ✅ 自动保存请求和响应日志（JSONL 格式，按日期分文件）

## 快速开始

### 1. 启动服务

```bash
cd proxy
python3 proxy_server.py        # 默认端口 8900
python3 proxy_server.py 9000   # 自定义端口
```

### 2. 配置目标 URL（可选）

**方法一：通过 API 设置**

```bash
curl -X POST http://localhost:8900/config \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://your-api-server.com"}'
```

**方法二：创建配置文件**

在 `proxy` 目录下创建 `proxy_config.json`：

```json
{
  "target_url": "https://your-api-server.com",
  "port": 8900
}
```

### 3. 配置 Claude Code

修改 Claude Code 配置，将 API 请求指向代理服务器。

在项目的 `.claude/settings.local.json` 中设置：

```json
{
  "apiBaseUrl": "http://localhost:8900"
}
```

或在全局配置 `~/.claude/settings.json` 中设置。

## API 端点

### 管理端点

- `GET /health` - 健康检查，返回服务状态
- `GET /config` - 查看当前配置
- `POST /config` - 更新配置

### 代理端点

所有其他路径的请求都会被透明转发到配置的目标服务器，例如：

- `/v1/messages` → `{target_url}/v1/messages`
- `/v1/complete` → `{target_url}/v1/complete`

## 配置选项

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `target_url` | 目标 API 服务器地址 | `https://xxxxx.xxxx` |
| `port` | 本地监听端口 | `8900` |
| `log_dir` | 日志保存目录 | `logs` |

## 日志功能

代理服务器会自动将所有请求和响应保存到 JSONL 格式的日志文件中：

- 日志文件路径：`logs/proxy_YYYY-MM-DD.jsonl`
- 每天一个文件，按时间顺序追加
- 每条日志包含：时间戳、请求方法、路径、请求头、请求体、响应状态、响应头、响应体
- JSON 格式便于后续分析和调试

日志示例：
```json
{
  "timestamp": "2026-03-18T14:29:15.123456",
  "method": "POST",
  "path": "/v1/messages",
  "request": {
    "url": "https://xxxxx.xxxx/v1/messages",
    "headers": {"x-api-key": "sk-...", "content-type": "application/json"},
    "body": {"model": "claude-sonnet-4-6", "messages": [...]}
  },
  "response": {
    "status": 200,
    "headers": {"content-type": "application/json"},
    "body": {"id": "msg_...", "content": [...]}
  }
}
```

### 查看日志

使用内置的日志查看器：

```bash
cd proxy
python3 log_viewer.py        # 默认端口 8901
python3 log_viewer.py 9001   # 自定义端口
```

然后在浏览器中打开 `http://localhost:8901`，可以：
- 浏览所有日志文件（按日期分组）
- 查看每个请求的完整信息（请求头、请求体、响应头、响应体）
- 语法高亮显示 JSON 数据
- 可调整侧边栏宽度

## 使用示例

### 查看配置

```bash
curl http://localhost:8900/config
```

### 更新目标 URL

```bash
curl -X POST http://localhost:8900/config \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://custom-api.example.com"}'
```

### 健康检查

```bash
curl http://localhost:8900/health
```

## 工作原理

代理服务器会：
1. 接收来自 Claude Code 的请求
2. 将请求完整转发到目标服务器（包括所有请求头和请求体）
3. 将目标服务器的响应原样返回给 Claude Code

所有认证信息（如 API Key）都由 Claude Code 在请求头中提供，代理服务器不做任何修改或添加。

## 注意事项

- 代理服务器只做透明转发，不修改任何请求内容
- API Key 等认证信息由 Claude Code 客户端提供
- 配置会自动保存到 `proxy_config.json` 文件
- 服务器超时时间设置为 300 秒（5 分钟）
- 仅用于本地开发和测试
