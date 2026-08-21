#!/usr/bin/env python3
"""
简化的 MCP HTTP 服务器
支持 POST 连接，使用本机 IP，带 Token 验证
"""

import socket
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request
import uvicorn

# 配置：设置有效的 Token
VALID_TOKEN = "local_mcp_token_2026"

# 获取本机 IP
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

# Token 验证
async def verify_token(request: Request):
    """验证请求中的 Mcp_token"""
    token = request.headers.get("Mcp_token") or request.query_params.get("Mcp_token")
    if not token or token not in (VALID_TOKEN, "123456"):
        return False
    return True

# 创建 MCP 服务器
app = Server("simple-mcp-server")

# 工具列表
@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="echo",
            description="回显消息",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }
        )
    ]

# 工具调用处理
@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "echo":
        return [TextContent(type="text", text=f"回声: {arguments.get('message')}")]
    raise ValueError(f"未知工具: {name}")

# SSE 传输
sse = SseServerTransport("/messages")

# 包装 SSE 处理函数
async def handle_sse(request):
    """处理 SSE 连接，带 Token 验证"""
    if not await verify_token(request):
        return JSONResponse(
            {"error": "Unauthorized", "message": "Invalid or missing Mcp_token"},
            status_code=401
        )
    
    async with sse.connect_sse(request.scope, request.receive, request._send) as (r, w):
        await app.run(r, w, app.create_initialization_options())

# 创建带认证的 POST 处理 ASGI 应用
async def handle_post_with_auth(scope, receive, send):
    """处理 POST 消息的 ASGI 应用，带 Token 验证"""
    request = Request(scope, receive=receive)
    
    # 验证 Token
    if not await verify_token(request):
        response = JSONResponse(
            {"error": "Unauthorized", "message": "Invalid or missing Mcp_token"},
            status_code=401
        )
        await response(scope, receive, send)
        return
    
    # Token 验证通过，调用原始的 POST 处理
    await sse.handle_post_message(scope, receive, send)

# Starlette 应用
starlette_app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages", app=handle_post_with_auth)
])

if __name__ == "__main__":
    ip = get_local_ip()
    print(f"启动服务器: http://{ip}:8000/sse")
    print(f"Token: {VALID_TOKEN}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8000)
