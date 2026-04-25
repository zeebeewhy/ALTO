@echo off
setlocal

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   本地语言学习系统 — 启动脚本
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REM 1. 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python。请先安装 Python 3.10+
    exit /b 1
)

REM 2. 创建虚拟环境
if not exist ".venv" (
    echo 🧪 创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate

REM 3. 安装依赖
python -c "import openai, spacy, pydantic, streamlit" >nul 2>&1
if errorlevel 1 (
    echo 📦 安装依赖...
    pip install -e . -q
)

REM 4. 下载 spaCy 模型
python -c "import spacy; spacy.load('en_core_web_sm')" >nul 2>&1
if errorlevel 1 (
    echo 🌐 下载 spaCy 英语模型...
    python -m spacy download en_core_web_sm
)

REM 5. 检查 .env
if not exist ".env" (
    echo.
    echo ⚠️  未找到 .env 文件
    echo 请创建 .env 并填入你的 API Key:
    echo.
    echo   echo LLM_API_KEY=sk-你的Key ^> .env
    echo   echo LLM_BASE_URL=https://api.moonshot.cn/v1 ^>^> .env
    echo.
    exit /b 1
)

REM 6. 测试 API 连通性
echo 🔌 测试 API 连通性...
python scripts\test_connection.py
if errorlevel 1 (
    echo ❌ API 测试未通过，请检查 .env 中的 Key
    exit /b 1
)

REM 7. 启动
echo.
echo 🚀 启动 Streamlit...
echo    打开浏览器访问: http://localhost:8501
echo.
streamlit run src\alto\app.py --server.port=8501
