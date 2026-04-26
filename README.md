# ALTO — Adaptive Learning Tutor Orchestrator

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

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — modern Python package manager (replaces pip + venv)
- Python >= 3.10 (uv will auto-install if missing)
- An OpenAI-compatible API key

### Step 1: Get API Key

ALTO 支持多种 LLM Provider，请选择你有额度的方式：

**方式 A：Kimi Code API（推荐，如果你有 Kimi 会员订阅）**
- 访问 https://www.kimi.com/code/console
- 使用 Kimi 会员账号登录
- 创建 API Key（格式以 `sk-kimi-` 开头）
- 这是 Kimi Code 订阅权益，与 Moonshot 开放平台额度不互通

**方式 B：Moonshot Open Platform（如果你有充值额度）**
- 访问 https://platform.moonshot.cn → 注册 → 创建 API Key
- 新用户有免费测试额度

**方式 C：OpenAI / DeepSeek / OpenRouter**
- 使用对应平台的 API Key

所有方式都是 OpenAI-compatible 协议，系统只调用 LLM API（模型不部署在本地），Key 只保存在你电脑上的 `.env` 文件中。

### Step 2: Install & Run

```bash
# 1. 进入项目目录
cd project_directory

# 2. 同步依赖（uv 自动创建 .venv 并安装所有包）
uv sync

# 3. 下载 spaCy 英语模型
uv run python -m spacy download en_core_web_sm

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，取消对应 Provider 的注释并填入 Key

# 5. 验证后端逻辑（不需要 API Key）
uv run python scripts/test_backend.py

# 6. 验证 API 连通性（需要 Key）
uv run python scripts/test_connection.py

# 7. 启动 Streamlit 前端
uv run streamlit run src/alto/app.py
```

浏览器自动打开 http://localhost:8501。

### Daily Commands

```bash
# 运行后端测试
uv run python scripts/test_backend.py

# 运行 API 连通性测试
uv run python scripts/test_connection.py

# 启动前端
uv run streamlit run src/alto/app.py

# 添加新依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 更新所有依赖
uv sync --upgrade

# 运行 pytest
uv run pytest
```

## Security: How Your API Key is Protected

| Threat | Protection |
|--------|-----------|
| **泄露到前端** | Key 只用于后端 Python 代码，从不传给浏览器 |
| **误提交到 Git** | `.env` 在 `.gitignore` 中，不会被提交 |
| **上传到服务器** | 系统**只设计为本地运行**，不部署到 Vercel/服务器 |
| **硬编码在代码** | Key 从环境变量/`.env` 读取，代码仓库无 Key |
| **他人访问你的界面** | 默认只监听 localhost，除非手动改为 0.0.0.0 |

**系统不部署任何模型。** 所有推理都在 LLM 提供商服务器完成，你的笔记本只发送文本请求、接收文本响应。

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
│   ├── run.py              # CLI launcher
│   ├── test_backend.py     # Backend logic verification (no LLM needed)
│   └── test_connection.py  # API connectivity checker
├── tests/
├── pyproject.toml          # Project config + dependencies (uv-managed)
├── .env.example            # API configuration template
├── .gitignore              # Protects .env and data/
├── README.md
└── DEVELOPER.md            # Developer workflow guide
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
uv add pyfcg
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
uv add c2xg
```

```python
import c2xg
cxg = c2xg.C2xG(language="en")
patterns = cxg.learn("corpus.txt", min_freq=5)
# Feed discovered patterns into declarative memory
```

## License

MIT
