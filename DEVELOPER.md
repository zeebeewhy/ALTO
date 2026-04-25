# 开发者工作流指南

> 个人开发者如何像开发 LobeChat/龙虾 那样，高效迭代一个 AI 项目。

---

## 一、项目当前状态（诚实版）

### ✅ 已经验证的

| 组件 | 状态 | 验证方式 |
|------|------|----------|
| L1+L2 记忆系统（声明性/程序性/工作） | **可用** | `test_backend.py` 全部通过 |
| L3 诊断 fallback（无LLM规则模式） | **可用** | 字符串匹配正确识别 want-to-V |
| L0 编排器决策逻辑 | **可用** | 系统性错误进入教学队列 |
| 完整学习循环模拟 | **可用** | 5步模拟激活度正确升降 |
| 代码语法/结构 | **可用** | 全部通过 py_compile |

### ⚠️ 需要用户本地配置的

| 组件 | 为什么需要 | 操作 |
|------|-----------|------|
| spaCy 英语模型 | L3 符号诊断的依存分析 | `python -m spacy download en_core_web_sm` |
| LLM API Key | L4 对话生成 + 诊断确认 | 在 `.env` 填入 Key |
| Streamlit | 前端界面 | `pip install streamlit` |

**结论**：后端逻辑已经 solid，但完整运行需要你在本地装依赖 + 配 Key。这是正常的——任何 AI 项目都需要这步。

---

## 二、环境要求清单

### 最低配置

| 项目 | 要求 | 说明 |
|------|------|------|
| Python | ≥ 3.10 | 3.12 已验证 |
| 操作系统 | macOS / Linux / Windows WSL | 纯 Python，跨平台 |
| 内存 | 4GB+ | spaCy + Streamlit 占用约 500MB |
| 磁盘 | 500MB 可用 | 模型 + 依赖 |
| 网络 | 能访问 Moonshot/OpenAI API | 模型不部署本地 |

### 开发依赖安装

```bash
cd project_directory

# 1. 虚拟环境（必须）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# 2. 安装项目 + 所有依赖
pip install -e .

# 3. 下载 spaCy 模型
python -m spacy download en_core_web_sm

# 4. 验证后端逻辑（不需要 Key）
python scripts/test_backend.py

# 5. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 Key

# 6. 验证 API 连通性（需要 Key）
python scripts/test_connection.py

# 7. 启动前端
streamlit run src/alto/app.py
```

---

## 三、AI CLI 工具链（核心问题：如何像专业开发者一样迭代）

龙虾（LobeChat）这样的项目不是一个人手写几万行代码完成的。核心开发模式是：**AI 辅助编码 + 快速验证循环**。

### 推荐工具链

| 工具 | 作用 | 适用场景 | 成本 |
|------|------|----------|------|
| **Kimi Code CLI** | 交互式 AI 编程助手 | 中文友好，适合复杂逻辑讨论 | 免费（需 Key） |
| **Codex CLI (OpenAI)** | 官方 CLI 编码工具 | 英文项目，GPT-4o 驱动 | 按量计费 |
| **Aider** | 自动化代码修改（编辑文件、Git 提交） | **最适合本项目** | 免费（需 Key） |
| **Claude Code (Anthropic)** | 最强 AI 编程助手 | 英文，处理复杂架构 | 按量计费 |
| **Cursor** | AI IDE（VS Code 分支） | 可视化 + AI 辅助 | 订阅制 |

### 为什么推荐 Aider + Kimi Code CLI 组合

**Aider**（https://aider.chat）是当前最适合这个项目的工具，因为：

1. **它直接编辑文件**：你给自然语言指令，它修改代码文件、运行测试、Git 提交
2. **支持多文件上下文**：可以同时处理 `engine.py` + `diagnostic.py` + `models.py`
3. **Git 集成**：每次修改自动提交，方便回滚
4. **支持国内模型**：可以配置 Moonshot/Kimi 作为后端

**Kimi Code CLI** 作为补充：当你需要深入讨论架构设计、问理论问题、写文档时使用。

### Aider 配置（使用 Kimi 作为后端）

```bash
# 安装
pip install aider-chat

# 配置环境变量
export OPENAI_API_KEY=sk-your-key
export OPENAI_API_BASE=https://api.moonshot.cn/v1

# 启动（在项目根目录）
cd project_directory
aider --model openai/kimi-latest --editor-model openai/kimi-latest

# Aider 会读取所有代码文件，你可以在聊天中直接说：
# "给 diagnostic.py 的 fallback 方法增加一个处理介词短语省略的规则"
# Aider 会自动修改文件、运行测试、告诉你结果
```

### 典型 AI 辅助开发流程

```
你                            Aider / Kimi CLI
|                                   |
├── "我需要增加一个被动语态构式"     → 修改 diagnostic.py + models.py
|   ← "已修改，测试通过，已提交"       |
|                                   |
├── "测试发现激活度上升太快"         → 调整 declarative.py 的公式
|   ← "已修改，后端测试通过"          |
|                                   |
├── "前端教学界面太简陋"            → 修改 app.py 的 UI
|   ← "已修改，Streamlit 正常启动"     |
|                                   |
└── "帮我写这个功能的测试用例"        → 生成 tests/test_xxx.py
    ← "测试已添加，pytest 通过"       |
```

### 关键原则：验证驱动开发

不要用 AI 写一堆代码然后手动检查。正确的模式是：

1. **先写测试**（描述你期望的行为）
2. **让 AI 实现**（基于测试要求修改代码）
3. **自动运行测试**（验证是否满足）

这正是 `test_backend.py` 的设计目的——你可以扩展它，然后让 AI 修改代码直到测试通过。

---

## 四、测试策略

### 三层测试金字塔

```
        /\
       /  \     E2E 测试（Streamlit + LLM）—— 慢，贵，但能验证完整流程
      /----\
     /      \   集成测试（Engine + Memory + Diagnosis）—— 中等速度
    /--------\  
   /          \ 单元测试（单个函数）—— 快，便宜，频繁运行
  /------------\
```

### 当前已有

| 测试 | 文件 | 速度 | 是否需要 Key |
|------|------|------|-------------|
| 后端逻辑验证 | `scripts/test_backend.py` | < 1秒 | ❌ 否 |
| API 连通性 | `scripts/test_connection.py` | ~3秒 | ✅ 是 |
| 完整前端 | Streamlit 界面 | 需手动 | ✅ 是 |

### 建议补充的测试（按优先级）

**高优先级（本周做）**

1. **pytest 单元测试** — 每个模块的独立测试
   - `tests/test_memory.py` — 激活度计算是否正确
   - `tests/test_diagnostic.py` — fallback 规则是否覆盖主要构式
   - `tests/test_procedural.py` — 策略切换阈值是否准确

2. **Mock LLM 测试** — 不花钱测试完整流程
   - 用本地假 LLM 返回固定 JSON
   - 验证 Engine 的编排逻辑不受 LLM 随机性影响

**中优先级（下周做）**

3. **集成测试** — 端到端但不走真实 API
   - 模拟多轮对话 → 检测构式 → 进入教学 → 练习 → 掌握

4. **性能测试** — 内存占用、响应延迟
   - 工作记忆容量限制是否生效
   - 大量构式时 DeclarativeMemory 是否变慢

### 运行所有测试

```bash
# 后端逻辑（不需要 Key，秒级）
python scripts/test_backend.py

# API 连通（需要 Key，秒级）
python scripts/test_connection.py

# pytest 完整套件（需要安装 pytest）
pip install pytest
pytest tests/

# 带覆盖率报告
pytest --cov=src/alto tests/
```

---

## 五、逐步完善路线图

### Phase 0：基础验证（你现在在这）

- [x] 五层架构代码完成
- [x] 后端逻辑测试通过
- [x] 启动脚本（start.sh / start.bat）
- [ ] 本地安装依赖并跑通完整流程（需要你操作）

**目标**：确认"自由对话 → 检测错误 → 进入教学 → 练习 → 回到对话"这个循环能跑通。

### Phase 1：核心闭环打磨（1-2 周）

**用 AI CLI 工具做这些**：

1. **增加更多构式的 fallback 规则**
   - 被动语态（be + past participle）
   - 比较级（more / -er）
   - 冠词省略（a / the）
   - *指令*："给 diagnostic.py 的 fallback 方法增加被动语态检测规则"

2. **优化激活度公式**
   - 当前公式较粗糙，参考 ACT-R 的 BLL（Base Level Learning）公式
   - *指令*："参考 ACT-R 的 base-level learning 公式，优化 declarative.py 的 encounter 方法"

3. **增加教学策略模板**
   - 当前只有 want-to-V 的演示模板
   - *指令*："给 pedagogical.py 增加 ditransitive 和 passive 的 fallback 模板"

4. **添加 pytest 测试**
   - *指令*："为 memory/declarative.py 的 encounter 方法写 pytest 单元测试，覆盖成功/失败/边界情况"

### Phase 2：引入真实 FCG（2-4 周）

1. 安装 PyFCG：`pip install pyfcg`
2. 替换轻量诊断器的 spaCy 部分为 FCG 解析
3. 比较 FCG 和 LLM 零样本的诊断结果，建立"诊断协议"

*AI 辅助方式*：给 Aider 上下文包括 PyFCG 文档，让它写集成代码。

### Phase 3：记忆系统升级（4-6 周）

1. 参考 MemPalace 的分层架构，重构 JSON 持久化
2. 增加跨会话的构式掌握度可视化
3. 构式课程图的自动生成（从 C2xG 发现 → FCG 验证 → 教学排序）

### Phase 4：多语言 + 扩展（6-8 周）

1. C2xG 作为构式发现前端
2. 多语言支持（spaCy 多语言模型）
3. 部署选项（可选）：桌面应用（PyInstaller）、本地 API 服务（FastAPI）

---

## 六、每日开发循环（推荐）

```bash
# 1. 进入项目
cd project_directory
source .venv/bin/activate

# 2. 拉取最新代码（如果你有 Git 仓库）
git pull

# 3. 运行测试确认基准
python scripts/test_backend.py

# 4. 启动 Aider 或 Kimi CLI 进行开发
aider --model openai/kimi-latest

# 5. 在 Aider 中：
#    - 描述你要做的修改
#    - 让 AI 生成代码
#    - 自动运行测试
#    - 提交 Git

# 6. 手动验证（需要 Key 时）
streamlit run src/alto/app.py
# 在浏览器里测试实际对话

# 7. 提交 & 记录
git add .
git commit -m "feat: add passive construction fallback"
```

---

## 七、常见陷阱与避免方法

| 陷阱 | 为什么危险 | 如何避免 |
|------|-----------|----------|
| **过度依赖 AI 写代码** | AI 会生成"看起来对但实际错"的代码 | 始终有测试验证 |
| **没有版本控制** | 改坏了无法回滚 | 每次修改前 `git commit` |
| **在前端暴露 Key** | 安全隐患 | 只本地运行，不部署 |
| **忽视 fallback** | LLM 不稳定时系统崩溃 | 确保所有 LLM 调用都有降级 |
| **激活度公式拍脑袋** | 教学策略失效 | 参考 ACT-R 文献，用数据校准 |
| **过早优化架构** | 死在设计阶段 | Phase 0 先跑通一个完整循环 |

---

## 八、参考资源

### AI 编程工具
- Aider: https://aider.chat
- Kimi Code CLI: https://platform.moonshot.cn/
- Codex CLI: https://github.com/openai/codex
- Claude Code: https://docs.anthropic.com/en/docs/claude-code

### 测试框架
- pytest: https://docs.pytest.org/
- pytest-cov（覆盖率）: https://pytest-cov.readthedocs.io/

### 项目管理
- 用 GitHub Issues / Projects 跟踪 Phase 1-4 的任务
- 每个 Phase 作为一个 Milestone

---

## 结论

你现在有一个**后端逻辑验证通过**的项目骨架。下一步不是写更多代码，而是：

1. **本地安装依赖 + 配 Key**，跑通完整前端流程
2. **选一个 AI CLI 工具**（推荐 Aider + Kimi）
3. **写更多测试**，然后用 AI 辅助修改代码直到测试通过
4. **不要急于 Phase 2-4**，先把 Phase 1 的闭环打磨到可用

龙虾这样的项目也是从一个最小原型开始，然后用 AI 工具 + 测试驱动的方式逐步迭代。区别在于他们有 CI/CD 和团队，你作为个人开发者，更需要**测试 + AI 辅助 + Git 版本控制**这三根支柱。
