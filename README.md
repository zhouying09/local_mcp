# Python MCP HTTP 服务器

支持 POST 连接的 MCP 服务器，使用本机 IP 地址。

## 功能特点

- ✅ 使用 HTTP SSE 传输协议
- ✅ 支持 POST 请求连接
- ✅ 自动获取本机 IP 地址
- ✅ 提供示例工具（echo、add_numbers、get_server_info）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务器

```bash
python mcp_server.py
```

服务器将启动在 `http://0.0.0.0:8000`，可以通过本机 IP 访问。

## 端点信息

- **SSE 端点**: `http://<本机IP>:8000/sse`
- **POST 端点**: `http://<本机IP>:8000/messages`

## 配置 MCP 客户端

在 MCP 客户端配置中添加：

```json
{
  "mcpServers": {
    "local-mcp-server": {
      "url": "http://30.25.74.63:8000/sse",
      "headers": {
        "Mcp_token": "local_mcp_token_2026"
      },
      "timeout": 60,
      "transportType": "sse",
      "disabled": true
    }
  }
}
```

## 可用工具

1. **echo** - 回显输入的内容
2. **add_numbers** - 将两个数字相加
3. **get_server_info** - 获取服务器信息

## 测试连接

可以使用 curl 测试 SSE 连接：

```bash
curl http://<本机IP>:8000/sse
```
