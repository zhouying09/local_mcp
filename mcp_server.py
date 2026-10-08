#!/usr/bin/env python3
"""
简化的 MCP HTTP 服务器 (SSE 传输)
- 支持 SSE 连接 + POST 消息
- 使用本机 IP 监听
- 带 Mcp_token 验证
"""
import socket

from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

import uvicorn

# ---------------- 配置 ----------------
VALID_TOKEN = "local_mcp_token_2026"
ALLOWED_TOKENS = (VALID_TOKEN, "123456")

HOST = "0.0.0.0"
PORT = 8000
SSE_PATH = "/sse"
MESSAGES_PATH = "/messages"   # 注意：不能有前导空格


# ---------------- 获取本机 IP ----------------
def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的发包，只是为了让系统选出默认出口网卡
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ---------------- Token 验证 ----------------
def verify_token(request: Request) -> bool:
    """从 header 或 query 里取 Mcp_token 并校验。"""
    token = request.headers.get("Mcp_token") or request.query_params.get("Mcp_token")
    return bool(token) and token in ALLOWED_TOKENS


def unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": "Unauthorized", "message": "Invalid or missing Mcp_token"},
        status_code=401,
    )


# ---------------- 创建 MCP 服务器 ----------------
app = Server("simple-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="echo",
            description="回显消息",
            inputSchema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "echo":
        return [TextContent(type="text", text=f"回声: {arguments.get('message')}")]
    raise ValueError(f"未知工具: {name}")


# ---------------- SSE 传输 ----------------
sse = SseServerTransport(MESSAGES_PATH)


async def _sse_asgi(scope: Scope, receive: Receive, send: Send) -> None:
    """SSE 端点的纯 ASGI 实现（不带 request/response 语义）。

    为什么必须是纯 ASGI：
      connect_sse 会把 200 + SSE 响应体直接写进 ASGI 通道，函数结束时返回 None。
      若用 Route(endpoint=...) 走 request_response 包装，Starlette 随后会
      await response(scope, receive, send)，而 response 是 None →
      TypeError: 'NoneType' object is not callable。
    """
    request = Request(scope, receive=receive)
    if not verify_token(request):
        await unauthorized()(scope, receive, send)
        return

    async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


async def handle_post_with_auth(scope: Scope, receive: Receive, send: Send) -> None:
    """处理 POST 消息的纯 ASGI 应用，带 Token 验证。"""
    request = Request(scope, receive=receive)
    if not verify_token(request):
        await unauthorized()(scope, receive, send)
        return

    await sse.handle_post_message(scope, receive, send)


class AsgiEndpoint:
    """把一个纯 ASGI 应用包装成 Starlette 的 ASGI 路由条目。

    为什么需要它 —— Starlette Route 的判定规则（源码 routing.py）：
        if inspect.isfunction(endpoint):   # 函数 → 当作 func(request)->response
            self.app = request_response(endpoint)
        else:                              # 非函数（含实例）→ 当作纯 ASGI，直接调用
            self.app = endpoint
    所以：
      - 用 async def + (scope, receive, send) 会被当成 request 端点 → TypeError;
      - 用函数 + (request) 又会变成 GET-only，POST 报 405;
      - 只有"非函数对象"才会被原样当 ASGI 调用 (scope, receive, send)。
    这就是这个类存在的原因：它的 __call__ 必须接收 (scope, receive, send)。
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.asgi_app(scope, receive, send)


# ---------------- Starlette 应用 ----------------
# 完整踩坑记录（全部实测复现并修复）：
#
# 坑1：Route(endpoint=func) 用 inspect.isfunction 判定类型 —— 只要传的是函数，
#      就包装成 func(request)->response。所以：
#        async def h(scope, receive, send)  → 被调 h(request)
#        TypeError: h() missing 2 required positional arguments: 'receive' and 'send'
#
# 坑2：Route 没有 app= 参数（app= 是 Mount 的）：
#        Route(path, app=...) → TypeError: unexpected keyword argument 'app'
#
# 坑3：Mount(MESSAGES_PATH, ...) 会把 POST /messages?session_id=x
#      307 重定向到 /messages/?session_id=x（Starlette 的 redirect_slashes），
#      POST body / session 丢失 → 404 或 500。
#
# 坑4：Starlette(redirect_slashes=False) → TypeError: unexpected keyword argument
#      （该参数属于 Router，不属于 Starlette）
#
# 正解：把纯 ASGI 应用塞进一个"非函数对象"（AsgiEndpoint 实例）。
#      Route 对非函数对象不做包装，直接当 ASGI 调用 (scope, receive, send)。
#      两个端点都用这个方式，就绕过了 request_response 包装带来的所有问题。
#
# 另外：SSE_PATH / MESSAGES_PATH 绝不能带前导或尾随空格。
starlette_app = Starlette(
    routes=[
        Route(SSE_PATH, endpoint=AsgiEndpoint(_sse_asgi)),
        Route(MESSAGES_PATH, endpoint=AsgiEndpoint(handle_post_with_auth)),
    ],
)


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"启动服务器: http://{ip}:{PORT}{SSE_PATH}")
    print(f"Token: {VALID_TOKEN}")
    uvicorn.run(starlette_app, host=HOST, port=PORT)
