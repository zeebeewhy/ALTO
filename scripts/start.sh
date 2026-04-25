#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  本地语言学习系统 — 启动脚本"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 检查 Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ 未找到 Python。请先安装 Python 3.10+"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
$PYTHON --version

# 2. 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "🧪 创建虚拟环境..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate

# 3. 安装依赖
if ! pip show openai spacy pydantic streamlit &> /dev/null; then
    echo "📦 安装依赖..."
    pip install -e . -q
fi

# 4. 下载 spaCy 模型
if ! python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
    echo "🌐 下载 spaCy 英语模型..."
    python -m spacy download en_core_web_sm
fi

# 5. 检查 .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  未找到 .env 文件"
    echo "请创建 .env 并填入你的 API Key:"
    echo ""
    echo "  echo 'LLM_API_KEY=sk-你的Key' > .env"
    echo "  echo 'LLM_BASE_URL=https://api.moonshot.cn/v1' >> .env"
    echo ""
    exit 1
fi

# 6. 测试 API 连通性
echo "🔌 测试 API 连通性..."
python scripts/test_connection.py
if [ $? -ne 0 ]; then
    echo "❌ API 测试未通过，请检查 .env 中的 Key"
    exit 1
fi

# 7. 启动
echo ""
echo "🚀 启动 Streamlit..."
echo "   打开浏览器访问: http://localhost:8501"
echo ""
streamlit run src/alto/app.py --server.port=8501
