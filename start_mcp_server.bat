@echo off
chcp 65001 >nul
echo ===================================
echo MCP HTTP 服务器启动脚本
echo ===================================

REM 设置工作目录
cd /d "C:\Users\V_Zygzhou\CodeBuddy\20260701181944"

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查依赖包
echo [信息] 检查依赖包...
python -c "import mcp, starlette, uvicorn" 2>nul
if errorlevel 1 (
    echo [警告] 部分依赖包缺失，正在安装...
    pip install mcp starlette uvicorn
)

REM 获取本机 IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do set LOCAL_IP=%%a
set LOCAL_IP=%LOCAL_IP:~1%

echo [信息] 本机 IP: %LOCAL_IP%
echo [信息] SSE 端点: http://%LOCAL_IP%:8000/sse
echo [信息] POST 端点: http://%LOCAL_IP%:8000/messages
echo [信息] Token: local_mcp_token_2026
echo ===================================
echo [信息] 正在启动服务器...
echo [提示] 按 Ctrl+C 停止服务器
echo ===================================

REM 启动服务器
python mcp_server.py

pause
