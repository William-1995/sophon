# Sophon

> **技能原生的 AI Agent 平台。** 只需将一个 SKILL.md + 脚本放入文件夹，Sophon 就能自动发现、组合和编排。零注册，无限组合。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**[English](README.md)** | **[贡献指南](CONTRIBUTING.md)** | **[Discord](your-discord-link)**

---

## Sophon 的独特之处

大多数 Agent 框架需要你编写胶水代码来注册工具和实现函数调用。Sophon 颠覆了这一模式：

> **技能定义就是工具本身。**

Sophon 不仅仅是一个 Agent 框架——它是构建 **AI 原生 OS 级别助手**的基础，处理你的工作与生活。我们推崇**工程师精心设计的**能力，而非 AI 随意生成的混乱。

### 工程优先，安全第一

与那些让 AI 即兴发挥并执行任意代码的系统不同，Sophon 基于一个核心原则运作：

**复杂的能力由工程师设计并验证，而非由 AI 实时生成。**

- **结构化抽象**：每个技能都是经过精心设计、测试和版本控制的能力
- **可预测的边界**：技能在隔离的子进程中运行，具有明确定义的输入/输出
- **人类精心策划的智能**：工程师定义 AI 能做什么以及如何做
- **无任意执行**：AI 编排技能，但不能创建新能力或突破定义好的边界

### 技能即工具，技能即子 Agent

Sophon 采用**双层技能架构**，从简单工具到复杂的多步骤工作流都能轻松扩展：

```
┌─────────────────────────────────────────────────────┐
│  主 Agent（编排器）                                  │
│  分析问题 → 选择技能 → 综合结果                      │
└──────────────┬──────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐          ┌────▼─────┐
│ 原语技能        │  │ 功能技能         │
│                 │  │                  │
│ • search        │  │ • deep-research  │
│ • crawler       │  │ • troubleshoot   │
│ • filesystem    │  │ • excel-ops      │
│ • time          │  │                  │
│ • log-analyze   │  │ [自带 ReAct 循环  │
│ • trace         │  │  的子 Agent]      │
│ • metrics       │  │                  │
└─────────────────┘  └──────────────────┘
```

- **原语技能（Primitives）**：单一用途工具（搜索、爬取、文件操作）。专注做好一件事。
- **功能技能（Features）**：复杂能力，本身就是子 Agent。每个功能技能运行自己轻量级的 ReAct 循环，将原语技能作为工具调用。

**示例**：`deep-research` 不是一个工具——它是一个子 Agent，会规划、并行派发搜索请求、过滤结果、抓取页面并综合发现。主 Agent 只需决定*何时调用它*。

---

## 为什么选择 Sophon？

**工程优先的理念**
我们相信复杂的 AI 能力应该由工程师设计、测试和验证，而不是由 AI 实时生成。Sophon 为人类策划的智能提供结构，同时让 AI 专注于编排。

**零摩擦的技能开发**
只需将 `SKILL.md` 和脚本放入文件夹，Sophon 就能自动发现。无需装饰器，无需注册样板代码，无框架锁定。技能是自包含的、可移植的、运行时无关的。

**为真实世界的复杂性而设计**
Sophon 通过父子会话处理多任务工作流，支持并发任务执行，并提供对 AI 思考和操作的完全可见性。随时取消长时间运行的任务，从检查点恢复，并维护完整的审计追踪。

**设计即安全**
进程隔离确保技能崩溃不会拖垮系统。能力边界防止 AI 突破定义的限制。每个技能执行经过验证的脚本，从不执行任意 AI 生成的代码。

**本地优先，隐私优先**
所有数据都保留在你机器的 SQLite 中。无云依赖，无外部向量数据库。你的对话、上下文和工作流完全由你控制。

---

## 快速开始

```bash
# 1. 克隆并设置
git clone https://github.com/William-1995/sophon.git
cd sophon
python -m venv .venv && source .venv/bin/activate

# 2. 配置（选择你的提供商）
# 配置文件位置：
#   - .env（主配置文件，从 .env.example 复制）
#   - config.py（系统参数和默认值）
cp .env.example .env
# 在 .env 中只配置一个 LLM 提供商：
#   - DeepSeek（云端）：DEEPSEEK_API_KEY=...
#   - Qwen/DashScope（云端）：DASHSCOPE_API_KEY=...（可选 QWEN_MODEL，例如 qwen-plus）
#   - Ollama（本地）：确保 Ollama 已安装并运行，例如 `ollama run qwen3.5:9b --think=false`
# 如同时配置多个，优先级：DeepSeek > Qwen > Ollama。

# 3. 启动（自动安装依赖、Playwright 并运行）
python start.py              # API 在 http://localhost:8080

cd frontend && npm install && npm run dev  # UI 在 http://localhost:5173
```

---

## 功能亮点

**技能原生架构**
- **SKILL.md 标准**：可在任何兼容运行时中使用（[agentskills.io](https://agentskills.io/)）
- **自动发现**：通过创建/删除文件夹来添加/移除能力
- **自包含**：每个技能拥有自己的逻辑、常量和依赖

**多会话架构**
Sophon 通过父子会话模型支持复杂的多任务工作流：
- **并发任务**：同时运行多个独立任务，每个任务在自己的会话中
- **父子层级**：后台任务生成子会话；父会话接收摘要，子会话包含完整详情
- **取消与恢复**：随时中断长时间运行的任务；从会话历史中的任意点恢复
- **随处继续**：跳转到任意子会话继续对话
- **会话级并发**：每个会话独立运行，具有隔离的上下文和状态

**子 Agent 能力**
内置的功能技能，本身就是子 Agent：
- **`deep-research`**：多阶段研究，支持并行抓取、LLM 降噪和带引用的综合报告
- **`troubleshoot`**：关联日志、追踪和指标，生成诊断图表
- **`excel-ops`**：AI 辅助的复杂 Excel 操作

**技能组合**
工程师可以通过组合现有技能构建复杂能力：
- **依赖声明**：在 SKILL.md 中声明原语或功能技能为依赖
- **嵌套编排**：功能技能可以调用其他功能技能作为子 Agent
- **DAG 验证**：加载时检测并拒绝循环依赖
- **无限嵌套**：从简单工具到复杂工作流，任意深度组合技能

**工程优先设计**
- **人类精心策划的能力**：复杂的技能由工程师设计、测试和验证
- **结构化抽象**：AI 决策与技能执行之间有清晰的边界
- **人机协作**：向 Agent 委派任务，审查进度，在需要时进行干预
- **可预测的行为**：无任意代码生成或执行

**安全与保障**
- **进程隔离**：每个技能在隔离的子进程中运行；崩溃被隔离
- **能力边界**：AI 编排预定义的技能，不能创建新能力
- **输入验证**：所有技能参数都针对模式进行验证
- **资源限制**：并发控制防止资源耗尽
- **无任意执行**：技能执行经过验证的脚本，而非 AI 生成的代码
- **完整审计追踪**：每个思考、操作和结果都被记录并可检查
- **会话树**：可视化父子会话关系
- **检查点恢复**：从最后一个检查点恢复中断的任务

**文件处理**
内置支持复杂文档操作，包括 Excel 处理，PDF 等更多格式即将推出。

**可见性与可观测性**
Sophon 将可见性视为一等公民：
- **思考透明**：实时查看 LLM 的推理过程
- **工具使用追踪**：观察调用了哪些技能、参数和结果
- **内置诊断**：自我监控能力，用于排查 Agent 自身问题
- **情绪感知**：检测并响应用户对话中的情绪线索

**本地语音识别**
内置基于 faster-whisper 的语音输入（本地运行，无需云端）：
- **模型**：tiny、base（默认）、small、medium、large
- **首次设置**：首次使用时自动下载模型（base 模型约 150MB）
- **语言支持**：支持中文、英文、自动检测
- **可配置**：通过 `SOPHON_SPEECH_MODEL` 环境变量设置模型

**隐私优先**
- **数据本地化**：所有日志、追踪、内存、指标都在 SQLite 中
- **无云依赖**：DuckDuckGo 搜索（无需 API 密钥）
- **仅 LLM 调用**：只有配置的提供商能看到提示词

---

## 内置技能

**原语技能**
| 技能 | 描述 |
|------|------|
| `search` | 通过 DuckDuckGo 进行网页搜索 |
| `crawler` | 使用 Playwright 抓取和提取内容 |
| `filesystem` | 读取、写入、列出工作区文件 |
| `time` | 时区转换、日期格式化 |
| `deep-recall` | 基于 RLM 思想的上下文探索 — 智能地在短期（缓存）和长期（持久化）上下文之间导航，跨会话检索相关信息 |
| `log-analyze` | 查询和分析应用程序日志 |
| `trace` | 分布式追踪分析 |
| `metrics` | 时序指标查询 |
| `diagnostics` | 自我诊断和故障排除 |

**功能技能（子 Agent）**
| 技能 | 描述 |
|------|------|
| `deep-research` | 多步骤研究，包含规划、并行执行、综合 |
| `troubleshoot` | 跨可观测性数据的根因分析 |
| `excel-ops` | 高级 Excel 操作 |

---

## 创建你自己的技能

```bash
mkdir -p skills/primitives/my-skill
cat > skills/primitives/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: "这个技能做什么以及何时使用它"
metadata:
  type: primitive
  dependencies: ""
---

## Tools
### run
| 参数 | 类型 | 必需 | 描述 |
|-----------|------|----------|-------------|
| query | string | 是 | 输入内容 |

## Output Contract
| 字段 | 类型 | 描述 |
|-------|------|-------------|
| result | string | 主要输出 |
| observation | string | 给 LLM 的文本 |
| references | array | 可选引用 |
EOF

# 创建脚本
cat > skills/primitives/my-skill/scripts/run.py << 'EOF'
#!/usr/bin/env python3
import json, sys

params = json.load(sys.stdin)
query = params["query"]

# 你的逻辑
result = f"已处理: {query}"

json.dump({
    "result": result,
    "observation": result
}, sys.stdout)
EOF
chmod +x skills/primitives/my-skill/scripts/run.py
```

重启 Sophon，你的技能会被自动发现并可以使用。

完整指南请参见 [docs/create-skill.md](docs/create-skill.md)。

---

## 文档

- **[架构](docs/ARCHITECTURE.md)** - 技术架构与设计
- **[API 参考](docs/API.md)** - HTTP API 端点
- **[创建技能](docs/create-skill.md)** - 技能编写指南

---

## 即将推出

- **Agent 市场** - 分享和发现社区技能
- **增强的文件处理** - 高级 Excel、PDF 和文档处理能力
- **桌面应用程序** - 原生桌面应用，实现与操作系统的无缝集成

---

## 当前状态

Sophon 仍处于早期开发阶段。许多功能已经可以工作，但仍有大量改进空间——性能优化、边界情况处理、文档完善以及更广泛的技能覆盖。我们相信开放构建，并从社区学习中成长。

如果你遇到问题或有想法，请提交 issue 或参与讨论。你的反馈将帮助塑造 Sophon 的未来。

## 提供商配置（切换提供商）

Sophon 支持多种 LLM 提供商，你可以通过编辑 `.env` 来切换（**只配置一个即可**）：

- **DeepSeek（云端）**：在 `.env` 中设置 `DEEPSEEK_API_KEY`（以及可选的 `DEEPSEEK_MODEL`）。
- **Qwen / DashScope（云端）**：设置 `DASHSCOPE_API_KEY`，可选 `QWEN_MODEL`（例如 `qwen-plus`）。
- **Ollama（本地）**：确保已安装并运行 Ollama，选择非思考模型，例如：
  - `ollama run qwen3.5:9b --think=false`

如同时配置多个提供商，Sophon 的优先级为：DeepSeek > Qwen > Ollama。

## 贡献

我们欢迎各种类型的贡献！技能开发是一个很好的起点——完全不需要了解核心内部。

**特别需要帮助的方向：**
- **新技能**：`weather`、`calculator`、`github`、`database`、`calendar`、`email`
- **LLM 提供商**：OpenAI、Claude、Gemini、本地模型支持
- **文件格式**：PDF、Word、图像处理能力
- **测试与问题反馈**：真实使用场景的反馈
- **文档**：教程、示例、翻译

详情请参见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

MIT © 2025 William-1995
