# ALTO 项目交接文档

> 构式语法神经符号语言教学系统 —— 设计逻辑、技术实现与理论根基

本文档面向后续接手的 AI 助手。阅读后应能理解：项目的理论来源、五层架构设计、关键代码结构、以及下一步方向。

---

## 一、项目目标

ALTO（Adaptive Learning Tutor Orchestrator）是一个**多层融合的语言教学 AI 系统**，核心命题是：

> 单一技术路线（纯 LLM、纯 FCG、纯 C2xG）在语言教学场景下都不够好，需要分层融合。

### 三大核心功能

1. **目标涌现与自主规划** —— 从学习者的自由对话中自动检测构式知识缺口，将其转化为教学目标
2. **引导学习噪声过滤** —— 区分系统性错误（值得进入教学队列）与随机噪声（应过滤），避免过度纠错
3. **记忆与定制化** —— 追踪每个学习者的构式掌握轨迹（声明性→程序性→自动化），实现跨会话个性化

### 背景论文

本项目的直接理论来源是 **Doumen et al. (2024)** *The Computational Learning of Construction Grammars: State of the Art and Prospective Roadmap*（综述）。该文指出当前构式语法计算学习的三条路线都在"偏科"：

| 路线 | 强项 | 短板 |
|------|------|------|
| **FCG** (Fluid Construction Grammar) | 双向形式化、形-义配对严格 | 工程门槛极高、无法处理自然变异 |
| **C2xG** (Dunn) | 十亿词级无监督构式发现 | 只产出"模式库"，无双向处理、无显式意义映射 |
| **LLM** | 覆盖无限变异、自然交互 | 黑箱、无法精确诊断结构性错误、无持久状态 |

本项目取各路线之长，用**分层架构**实现互补。

---

## 二、五层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (Streamlit)                                            │
│  ├─ 对话窗口：自由输入 → 触发"目标涌现"与"噪声诊断"          │
│  └─ 教学界面：策略约束下的生成式练习                         │
├─────────────────────────────────────────────────────────────┤
│  L4 交互层：LLM Dialogue Engine                              │
│     职能：自然语言生成、解释、零样本SRL/错误分析               │
│     输入：学习者句子、系统提示、教学策略约束                 │
│     输出：自然语言回复 / 教学材料 JSON                       │
├─────────────────────────────────────────────────────────────┤
│  L3 神经-符号接口 (Neuro-Symbolic Diagnosis)                 │
│     ├─ 符号侧：spaCy依存签名提取 (自监督)                    │
│     └─ 神经侧：LLM零样本语义角色标注 + 错误类型判断          │
│     理论：Construction Grammar (Slot-filling) + NSAI         │
│     输出：DiagnosisReport (目标构式、填充/缺失/错误槽位、ZPD推荐)│
├─────────────────────────────────────────────────────────────┤
│  L2 认知状态层 (ACT-R Inspired)                              │
│     ├─ 声明性记忆：构式掌握度 (activation 0→1)              │
│     ├─ 程序性记忆：教学策略规则 (HTN简化)                    │
│     └─ 工作记忆：当前目标、最近错误、会话上下文                │
│     理论：ACT-R记忆二分 + ZPD支架 + 程序性知识自动化          │
├─────────────────────────────────────────────────────────────┤
│  L1 记忆层 (JSON持久化)                                      │
│     ├─ 长期记忆：学习者画像、构式网络、错误模式               │
│     └─ 时序轨迹：个体化习得路径                                │
│     理论：Usage-Based (Bybee 2006) + 动态系统                 │
├─────────────────────────────────────────────────────────────┤
│  L0 编排层：MetaOrchestrator                                 │
│     职能：根据L2状态调度教学策略、管理对话/教学模式切换        │
└─────────────────────────────────────────────────────────────┘
```

### 层间通信协议

关键数据结构定义在 `src/alto/models.py`：

- **DiagnosisReport**：L3 输出 → L0/L2 输入。包含 target_cxn、filled_slots、missing_slots、wrong_slots、error_type、zpd_recommendation、is_systematic
- **ConstructionState**：L1/L2 存储单元。包含 activation(0→1)、stable(bool)、exposure_count、success_count、systematic_error_count、error_patterns[]
- **TeachingStrategy**：L2 程序性记忆输出 → L4 输入约束。包含 mode(demonstration|scaffolded_production|guided_production|refinement)、instruction、constraint、allow_free
- **LessonMaterial**：L4 输出 → 前端。包含 title、content、exercise、expected_pattern、hints[]

---

## 三、各层技术实现

### L4 交互层（`src/alto/agents/`）

| 模块 | 文件 | 职责 |
|------|------|------|
| DialogueAgent | `dialogue.py` | 自由对话生成。接收 conversation_history + system_hint，返回自然语言回复 |
| PedagogicalAgent | `pedagogical.py` | 教学材料生成。接收 cxn_id + ConstructionState + TeachingStrategy，返回 LessonMaterial |
| MetaOrchestrator | `orchestrator.py` | 层间协调。process_chat_input() 更新记忆 + 判断 should_teach + 选择 suggested_target |

**设计决策**：L4 只负责"生成"，不负责"决策"。教学策略由 L2 的程序性记忆决定（基于激活度阈值），L4 在策略约束下生成内容。这避免了 LLM 作为自主决策者的不可控性。

### L3 诊断层（`src/alto/neuro_symbolic/diagnostic.py`）

```
学习者句子
    │
    ├──→ spaCy 依存分析 → syntax signature (root, nsubj, dobj, etc.)
    │       自监督（无需人工标注），但仅产出句法骨架
    │
    ├──→ LLM 零样本语义分析 → 目标构式、语义角色、错误类型
    │       灵活但依赖网络、有随机性
    │
    └──→ Fusion: DiagnosisReport
            error_type ∈ {none, omission, commission, misordering, creative}
            is_systematic ∈ {true, false}  ← 噪声过滤核心
            zpd_recommendation ∈ {demonstration, scaffolded_production, guided_production, refinement}
```

**关键设计**：当 LLM 不可用时，fallback 到基于字符串和 spaCy 的规则诊断。确保系统不依赖 LLM 也能运行基础功能。

**与 FCG 的集成位点**：diagnose() 方法预留了 `fcg_applied` 和 `fcg_result` 字段。未来接入 PyFCG 时，FCG 的解析结果可直接填入 DiagnosisReport。

### L2 认知状态层（`src/alto/memory/`）

**声明性记忆**（`declarative.py`）— ConstructionState：

```python
# 激活度更新公式（ACT-R inspired）
# 成功时：指数平滑向 1.0 靠近
state.activation = min(1.0, state.activation * decay + boost)

# 失败时：衰减，但有 floor 防止完全遗忘
state.activation = max(0.0, state.activation * decay - 0.05)

# 稳定化条件：激活度 > 0.85 且 暴露次数 > 5
state.stable = activation > 0.85 and exposure_count > 5
```

**程序性记忆**（`procedural.py`）— 四阶段策略映射：

| 激活度范围 | ACT-R 阶段 | 教学策略 | 是否允许自由产出 |
|-----------|-----------|---------|---------------|
| 0.00–0.25 | Declarative | demonstration（示范） | ❌ |
| 0.25–0.60 | Associative | scaffolded_production（控制练习） | ❌ |
| 0.60–0.85 | Procedural | guided_production（引导产出+即时重铸） | ✅ |
| 0.85–1.00 | Autonomous | refinement（变体比较、语用微调） | ✅ |

**工作记忆**（`working.py`）— 会话上下文：

- 容量限制：ACT-R 的 7±2 chunks（默认 7，可配置）
- 自动淘汰：超出容量时旧 turn 被推出
- 内容：current_target、turn_history、pending_errors、last_diagnosis

### L1 持久化层

JSON 文件存储，路径 `./data/memory/{user_id}_declarative.json`。

每个构式一个 ConstructionState entry，格式：

```json
{
  "want-to-V": {
    "activation": 0.65,
    "stable": false,
    "error_patterns": [
      {"sentence": "I want eat apple", "type": "omission", "missing": ["to-infinitive"]}
    ],
    "exposure_count": 8,
    "success_count": 5,
    "systematic_error_count": 2
  }
}
```

**设计决策**：不选 SQLite/数据库，因为项目定位为本地优先（Local-First）。学习者的数据应该属于学习者自己，存在本地文件而非云端服务器。JSON 足够支撑当前规模，未来可无痛迁移到 SQLite 或 MemPalace 式分层架构。

### L0 编排层（`orchestrator.py` + `engine.py`）

**MetaOrchestrator** 核心逻辑：

1. process_chat_input()：接收学习者句子 + DiagnosisReport
2. 更新声明性记忆（encounter 成功/失败）
3. 如果是系统性错误 → 加入 working.pending_errors
4. 查询弱构式（get_weak_constructions, threshold=0.4）和系统性错误列表
5. 决策：should_teach？suggested_target？system_hint for dialogue？

**Engine**（`engine.py`）是总入口，组合所有层：
- process_chat() — 自由对话模式
- enter_teaching() — 切换到教学模式，生成 LessonMaterial
- evaluate_exercise() — 评估练习答案，更新激活度

---

## 四、完整学习循环

以学习者说 "I want eat apple" 为例：

```
Step 1: 自由输入
  学习者: "I want eat apple"

Step 2: L3 诊断
  spaCy 提取: root="want", 缺少 "to"
  LLM 确认: target_cxn="want-to-V", error_type="omission", is_systematic=true
  → DiagnosisReport

Step 3: L0 编排
  更新声明性记忆: want-to-V activation=0.05 (新构式进入记忆)
  判定: systematic error → 加入 pending_errors
  should_teach = true
  suggested_target = "want-to-V"

Step 4: 进入教学 (Engine.enter_teaching)
  activation=0.05 → 程序性记忆选择 strategy.mode="demonstration"
  PedagogicalAgent 在 demonstration 约束下生成 LessonMaterial
  → 展示 want-to-V 的例子和解释

Step 5: 学习者练习
  学习者输入: "I want to eat an apple"
  L3 诊断: error_type="none"
  更新声明性记忆: activation 0.05 → 0.30 (指数平滑)

Step 6: 继续或返回
  activation < 0.85 → should_continue = true
  生成下一个练习 (scaffolded_production: 填空题)
  
  当 activation ≥ 0.60 后 → guided_production (允许自由产出，即时重铸)
  当 activation ≥ 0.85 后 → refinement (对比 want-to-V 和 want + V-ing)
  当连续成功且无错误 → return_to_chat
```

---

## 五、构式语法计算学习的三条路线（本项目的知识底座）

### 路线1：FCG（Fluid Construction Grammar）

- **核心文献**：Van Eecke & Beuls (2026) arXiv:2603.12754 — 从标注语料自动学习40,688个构式
- **工具**：PyFCG (`pip install pyfcg`)，预训练英语语法可用
- **本项目中的角色**：L3 符号诊断的**理想后端**。FCG 返回的特征结构（feature structures）+ categorial links 是严格的形-义配对
- **当前状态**：代码预留了 `fcg_applied`/`fcg_result` 字段，尚未接入
- **接入难点**：FCG 产出需要翻译为 LLM 可理解的 DiagnosisReport JSON（诊断协议设计）

### 路线2：C2xG（Computational Construction Grammar / Dunn）

- **核心文献**：Dunn (2024) *Computational Construction Grammar: A Usage-Based Approach*
- **工具**：`pip install c2xg`，支持35语言无监督构式发现
- **本项目中的角色**：构式发现**前端**。从大规模语料预挖掘构式候选，供 FCG 验证后进入教学体系
- **当前状态**：尚未接入

### 路线3：LLM 零样本语义分析

- **本项目中的角色**：L3 的神经侧 + L4 的生成引擎
- **当前状态**：已实现 fallback + LLM 双通道
- **关键约束**：LLM 只负责"生成"和"分析"，不自主决策。决策由符号层（激活度阈值）驱动

---

## 六、参考文献与调研资源

### 项目内已有的调研报告

- `调研报告_构式语法计算学习与多层融合架构.md`（完整文献综述，见项目根目录）

### 核心论文清单

| 论文 | 作者 | 作用 |
|------|------|------|
| *The Computational Learning of Construction Grammars: State of the Art and Prospective Roadmap* | Doumen et al. (2024) | 项目直接来源，三条路线对比 |
| *A Method for Learning Large-Scale Computational Construction Grammars* | Van Eecke & Beuls (2026, arXiv:2603.12754) | FCG 自动学习里程碑，PyFCG 可用 |
| *PyFCG: Fluid Construction Grammar in Python* | Van Eecke & Beuls (2025) | FCG 的 Python 接口 |
| *Computational Construction Grammar: A Usage-Based Approach* | Dunn (2024) | C2xG 全面介绍 |
| *Scaffolded Support Model* | Hare et al. (2025) | 神经符号教学框架，ZPD 模糊脚手架 |
| *An Adaptive Multi-Agent Architecture with RL and Generative AI for ITS* | ELA Tutor (2026, MDPI) | 多Agent+RL教学系统工程参考 |
| *Constructing Meaning, Piece by Piece* | Lindes (2019, PhD) | Soar+ECG 认知架构语言理解 |
| *Integrating LM Embeddings into ACT-R* | Frontiers (2026) | 认知架构+LLM融合最新实验 |
| *Memory in LLM-based Multi-agent Systems* | TechRxiv (2025) | 多Agent记忆分类学 |
| *Can LLMs Extract Frame-Semantic Arguments?* | ACL 2025 | LLM 语义角色标注性能评估 |

### 关键开源资源

| 资源 | 获取 | 用途 |
|------|------|------|
| PyFCG | `pip install pyfcg` | FCG 符号引擎 |
| C2xG | `pip install c2xg` | 无监督构式发现 |
| spaCy | `pip install spacy` | 依存分析 |
| FrameNet | framenet.icsi.berkeley.edu | 语义框架资源 |
| PropBank | propbank.github.io | 语义角色标注 |

---

## 七、项目目录结构

```
alto/
├── src/alto/
│   ├── __init__.py
│   ├── app.py              # Streamlit 前端（对话窗口 + 教学界面）
│   ├── config.py           # Pydantic 配置（多Provider Key解析：Kimi Code / Moonshot / OpenAI）
│   ├── engine.py           # 总入口：process_chat / enter_teaching / evaluate_exercise
│   ├── models.py           # 层间通信协议：DiagnosisReport, ConstructionState, TeachingStrategy, LessonMaterial
│   ├── memory/
│   │   ├── declarative.py  # 构式掌握度（激活度 0→1，ACT-R inspired）
│   │   ├── procedural.py   # 四阶段教学策略（demonstration → scaffolded → guided → refinement）
│   │   └── working.py      # 会话工作记忆（7±2 chunks）
│   ├── neuro_symbolic/
│   │   └── diagnostic.py   # spaCy依存 + LLM零样本SRL → DiagnosisReport
│   ├── agents/
│   │   ├── dialogue.py     # LLM对话生成
│   │   ├── pedagogical.py  # 教学材料生成（HTN策略约束下）
│   │   └── orchestrator.py # MetaOrchestrator：层间协调
│   └── construction/       # 预留：构式语法层（PyFCG / C2xG 接入位点）
├── scripts/
│   ├── demo_api_call.py    # SDK vs 原始HTTP调用对比演示
│   ├── test_backend.py     # 后端逻辑验证（无LLM，纯本地）
│   └── test_connection.py  # API连通性检查
├── pyproject.toml          # uv 管理依赖（pydantic, openai, spacy, streamlit）
├── .env.example            # 多Provider配置模板
├── .gitignore              # 保护 .env 和 data/
├── README.md               # 用户安装指南
├── DEVELOPER.md            # 开发者工作流（uv + AI CLI 工具链）
└── 调研报告_构式语法计算学习与多层融合架构.md
```

---

## 八、关键设计决策说明（Why these choices）

### 1. 为什么用 OpenAI SDK 而不是直接 requests？

Moonshot/Kimi Code 的 API 是 **OpenAI-compatible**。使用 `openai` SDK：
- 自动处理 JSON 编码、请求头、错误重试、流式响应
- 一行代码切换 Provider（只改 base_url）
- 行业 de facto 标准

### 2. 为什么激活度公式不用 ACT-R 精确的 BLL？

ACT-R 的 Base Level Learning 公式涉及 `log(t_i^{-d})` 的求和，需要存储每次暴露的时间戳。当前使用指数平滑是**工程简化**：
- 足够表达"练习→进步、遗忘→衰减"的动态
- 存储简单（只需一个 float）
- 未来可以无痛替换为精确 BLL（保留 error_patterns 中的时间戳即可）

### 3. 为什么 ZPD 用阈值而不是模糊控制？

Hare et al. (2025) 的 Scaffolded Support Model 将 ZPD 操作化为模糊控制系统。当前用**离散四阶段**是 MVP 简化：
- 模糊控制需要更复杂的参数校准
- 四阶段（0.25, 0.60, 0.85 阈值）足够启动教学循环
- 未来可以升级为 Hare 的 fuzzy scaffolding JSON control schema

### 4. 为什么教学材料用 LLM 生成而不是模板？

`pedagogical.py` 实际上**两者都有**：
- 首选：LLM 在 TeachingStrategy 约束下生成（content + exercise + hints）
- 降级：`_template_lesson()` 方法提供硬编码模板（want-to-V / ditransitive / passive 等）
- 理由：LLM 生成更自然、更能适应学习者的错误模式；但网络不可用时模板保底

### 5. 为什么不用具身层（Embodiment）？

Doumen et al. (2024) 的路线图提到具身层（物理世界 grounding）。本项目**省略**这一层：
- 语言教学不涉及物理操作（不像机器人指令）
- Lucia/Soar 的具身理解（E3C）复杂度极高，对教学收益有限
- 保持四层 + 编排层，降低工程复杂度

---

## 九、下一步路线图

### Phase 0：基础验证 ✅（已完成）

- 五层架构代码完成
- 后端逻辑测试通过（test_backend.py）
- API 连通性验证成功

### Phase 1：核心闭环打磨（当前阶段）

1. **增加 fallback 构式规则** — passive, comparative, article omission
2. **优化激活度公式** — 参考 ACT-R BLL，引入时间衰减
3. **增加教学策略模板** — ditransitive, passive 等构式的模板
4. **添加 pytest 单元测试** — 覆盖 encounter / select_strategy / diagnose

### Phase 2：引入真实 FCG（2-4周）

1. 安装 PyFCG：`uv add pyfcg`
2. 设计 FCG → DiagnosisReport 的"诊断协议"
3. 替换/增强 spaCy 的符号诊断
4. 比较 FCG 与 LLM 的诊断一致性

### Phase 3：记忆系统升级（4-6周）

1. 参考 MemPalace 分层架构重构 JSON 持久化
2. 构式课程图的自动生成（C2xG 发现 → FCG 验证 → 教学排序）
3. 跨会话可视化仪表盘

### Phase 4：扩展（6-8周）

1. C2xG 作为构式发现前端
2. 多语言支持（spaCy 多语言模型）
3. 可选部署：桌面应用（PyInstaller）或本地 API 服务（FastAPI）

---

## 十、如果你（新 AI 助手）现在接手

你应该先读这三个文件：

1. **`src/alto/engine.py`** — 理解总入口和层间调用关系
2. **`src/alto/models.py`** — 理解层间通信数据结构
3. **`src/alto/memory/declarative.py`** — 理解激活度更新逻辑（项目最核心的算法）

然后按需求继续 Phase 1-4 的任何一项。

---

*文档版本：v1.0*
*对应代码版本：alto 0.1.0*
