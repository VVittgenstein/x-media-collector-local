@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 检查 Python...
where python >nul 2>&1 || (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [2/4] 准备虚拟环境...
if not exist ".venv" (
    echo 创建虚拟环境...
    python -m venv .venv
)

echo [3/4] 安装依赖...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

echo [4/4] 启动服务...
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"
uvicorn src.backend.app:app --host 127.0.0.1 --port 8000
