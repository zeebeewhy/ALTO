# 构式语法语言学习系统

A neuro-symbolic, multi-layer language tutoring system that combines Construction Grammar theory with LLM-powered interaction and ACT-R inspired cognitive state tracking.

## Architecture

```
L4  DialogueAgent      — LLM-powered natural conversation
L3  ConstructionDiagnosis — spaCy syntax + LLM zero-shot semantic analysis
L2  Memory System       — ACT-R inspired (declarative / procedural / working)
L1  Persistence        — JSON-based long-term learner memory
L0  MetaOrchestrator    — Layer coordination, ZPD scaffolding, noise filtering
```

## Three Core Functions

1. **Goal Emergence & Autonomous Planning** — Detects construction gaps from free conversation, automatically plans teaching sequence
2. **Guided Learning with Noise Filtering** — Distinguishes systematic errors (enter teaching queue) from random noise (filter out)
3. **Memory & Personalization** — Tracks individual construction activation trajectories across sessions

## Quick Start

### Prerequisites

- Python >= 3.10
- An OpenAI-compatible API key (Kimi / OpenAI / etc.)

### Step 1: Get API Key

- **Moonshot (Kimi)**: https://platform.moonshot.cn/ → 注册 → 创建 API Key → 获取免费额度
- 系统只调用 LLM API（模型不部署在本地），Key 只保存在你电脑上的 `.env` 文件中

### Step 2: Clone / Download

```bash
cd project_directory
```

### Step 3: One-Click Start

**Linux / macOS:**
```bash
bash scripts/start.sh
```

**Windows:**
```cmd
scripts\start.bat
```

脚本会自动完成：创建虚拟环境 → 安装依赖 → 下载 spaCy 模型 → 测试 API → 启动 Streamlit

### Manual Setup (if scripts fail)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# Download spaCy model (for L3 symbolic diagnosis)
python -m spacy download en_core_web_sm

# Configure API
# Option A: Create .env file
cp .env.example .env
# Edit .env with your API key

# Option B: Environment variables
export LLM_API_KEY="sk-your-key"
export LLM_BASE_URL="https://api.moonshot.cn/v1"
export LLM_MODEL_NAME="kimi-latest"

# Verify connectivity
python scripts/test_connection.py

# Launch
streamlit run src/alto/app.py
```

Open http://localhost:8501 in your browser.

## Security: How Your API Key is Protected

| Threat | Protection |
|--------|-----------|
| **泄露到前端** | Key 只用于后端 Python 代码，从不传给浏览器 |
| **误提交到 Git** | `.env` 在 `.gitignore` 中，不会被提交 |
| **上传到服务器** | 系统**只设计为本地运行**，不部署到 Vercel/服务器 |
| **硬编码在代码** | Key 从环境变量/`.env` 读取，代码仓库无 Key |
| **他人访问你的界面** | 默认只监听 localhost，除非手动改为 0.0.0.0 |

**系统不部署任何模型。** 所有推理都在 Moonshot/OpenAI 服务器完成，你的笔记本只发送文本请求、接收文本响应。

## Project Structure

```
├── src/alto/
│   ├── __init__.py
│   ├── app.py              # Streamlit frontend
│   ├── config.py           # Pydantic settings (.env + env vars)
│   ├── engine.py           # Main orchestrator
│   ├── models.py           # Pydantic data models (protocols between layers)
│   ├── memory/             # L1+L2: Memory systems
│   │   ├── declarative.py  # Construction mastery (activation 0→1)
│   │   ├── procedural.py   # HTN teaching strategy rules
│   │   └── working.py      # Session context (7±2 capacity)
│   ├── neuro_symbolic/     # L3: Diagnosis engine
│   │   └── diagnostic.py   # spaCy + LLM zero-shot SRL
│   ├── agents/             # L4: LLM agents
│   │   ├── dialogue.py     # Free conversation
│   │   ├── pedagogical.py  # Teaching material generation
│   │   └── orchestrator.py # Meta-orchestrator (L0)
│   └── construction/       # Construction grammar layer
├── scripts/
│   ├── start.sh            # One-click launch (Linux/Mac)
│   ├── start.bat           # One-click launch (Windows)
│   ├── run.py              # CLI launcher
│   └── test_connection.py  # API connectivity checker
├── tests/
├── pyproject.toml
├── .env.example
├── .gitignore              # Protects .env and data/
└── README.md
```

## Theory Mapping

| Theory | Code Location | Self-Supervised? |
|--------|--------------|------------------|
| Construction Grammar (CxG) | `models.py` DiagnosisReport slot structure | ✅ LLM zero-shot auto-detects constructions |
| ACT-R Memory | `memory/` declarative + procedural + working | ✅ Rule-driven, no annotation |
| ZPD / Scaffolding | `procedural.py` select_strategy() | ✅ Activation-threshold based |
| Neuro-Symbolic AI | `diagnostic.py` spaCy + LLM fusion | ✅ spaCy pretrained + LLM zero-shot |
| Usage-Based | `declarative.py` encounter() frequency tracking | ✅ Auto-cumulative from interaction |

## Complete Learning Loop

1. **Free chat** → Learner types "I want eat apple"
2. **L3 Diagnosis** → spaCy detects missing "to"; LLM confirms want-to-V construction gap
3. **L0 Orchestration** → Systematic error detected → enter teaching queue
4. **Enter teaching** → Activation = 0.05 → Stage: Declarative → Demonstration mode
5. **Generate lesson** → LLM generates examples with "want to ___" pattern
6. **Learner practices** → "I want to eat an apple" → Correct!
7. **Update memory** → Activation: 0.05 → 0.30 (associative stage)
8. **Continue or return** → Next exercise or back to chat

## Extending

### Add PyFCG integration (for real FCG parsing)

```bash
pip install pyfcg
```

Then in `neuro_symbolic/diagnostic.py`:
```python
# After spaCy extraction:
fcg_result = pyfcg.parse(sentence)
report.fcg_applied = True
report.fcg_result = fcg_result
```

### Add C2xG as construction discovery frontend

```bash
pip install c2xg
```

```python
import c2xg
cxg = c2xg.C2xG(language="en")
patterns = cxg.learn("corpus.txt", min_freq=5)
# Feed discovered patterns into declarative memory
```

## License

MIT
