# 工程文献库审计

<p align="center">
  <strong>一篇综述写成文字之前，先是一条证据链。</strong>
</p>

<p align="center">
  它始于一份文献库、一条检索轨迹，以及一个常被推迟的问题：“这些证据真的撑得起我准备写下的论证吗？”
  <em>在投入数月写作之前回答它，代价最低。</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License">
  <img src="https://img.shields.io/badge/indicators-22%20(%2B3%20umbrella)-8b5cf6" alt="Indicators">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Platform">
</p>

---

## 这是什么

这个项目审计的不只是文献库，也审计**产生这份文献库的检索策略**。一组论文不能脱离检索式、数据库、执行日期和筛选决策而被判断为“充分”。

**工程文献库审计**是一个综述准备度诊断工具——在写综述之前，验证你的文献库和检索过程是否具备支撑一篇可信综述的结构性证据。它不帮你写综述，不给一个模糊的综合分，它告诉你：能支撑什么、还缺什么、以及为什么。

### 你很可能遇到过这些问题

- 刚进入一个新领域，文献乱七八糟，根本不知道从哪搜起
- 收集了 200 篇论文，心里总不踏实：*是不是漏掉了一整个子方向？*
- 综述写完了交给导师/审稿人，对方一句"你漏了 XXX"——几个月白干
- 只搜了一个数据库，觉得够了——换一个数据库才发现完全是另一批论文
- 写完了再去检查检索是否完整——发现晚了，证据基础根本撑不住结论

**这些返工本可避免。** 先检查证据结构，再打磨综述文字，往往更省时间。

### 换一个起点

在动笔**之前**跑一次审计。你可以直接对 AI 说一句话，得到：

- 按优先级排列的待修复项——阻断项排在最前面
- 六个独立维度的准备度——没有总分可以掩盖致命短板
- 每个输入都以 sha256 哈希记录——审计可复现
- 缺失的输入标为 `not_assessable` 而非隐藏——*"这是最便宜的修复方式"*
- 检索式 q0、每次原子改动与首轮诊断会进入报告——检索不再是黑箱

## 快速开始

```text
使用 literature-library-eval 评估我的文献库，
判断它能否支撑"工业视觉缺陷检测的跨产线迁移"的系统综述。
```

AI 会协助你：

1. 确认研究问题、综述类型、工程领域和边界（一次最多三个问题）
2. 接受你的文献库（当前脚本完整支持 JSON；Zotero、BibTeX、RIS、CSV 可先由 AI 协助规范化为 JSON）
3. 执行可用的诊断检查，协助迭代检索，计算指标并生成审计包

你不需要先准备 JSON Schema、Gold set 或去重日志。先告诉 AI 研究问题和文献库位置即可；缺少的证据会在报告中明确列出，并给出最低成本的补充方式。

如果你没有 seminal papers 和检索式，首轮也不会留白：系统会自动建立多源候选锚点、生成 q0 和原子变体，并给出 A1–A3、B1–B3 的 **AI 主导初评**。首轮与后续轮次使用同一张结果表和同一阈值：A1/A2/B1 会直接显示通过或不通过，B2 明确显示独立路径不足的警示，B3 在路径/验证未完成时直接显示不通过。`automated-screening` 只标注证据来源，详细边界移到表后的说明，绝不被包装成“检索已饱和”。

**当前实现状态：**

| 状态 | 环节 |
|:---:|---|
| ✅ 已自动化 | 审计计算、无锚点/无检索式的一键首轮 A1–A3/B1–B3 初评（`run_initial_assessment.py`）、OpenAlex + Crossref（按领域补 arXiv/Europe PMC）的 q0 + 原子变体、多源候选锚点发现、迭代记录验证、报告生成 |
| 🔧 半自动 | 中心主张下的 C4 观点分类与反向补检、多轮检索迭代、引文追踪、标准/指南路径与正式筛选——由 AI agent 在对话中手动编排 |
| 📋 规划中 | 端到端一键编排（`run_full_audit.py`）；项目仍在迭代，尚未定稿 |

验证集不要求用户逐篇提供：AI 可以从综述、标准、引文网络和时间留出路径构建候选验证集，再冻结后评估检索式。验证集的来源、冻结时间和是否接触过检索式会写入 `evidence-manifest.json`；不同 subagent/线程不自动等于独立证据。

对于叙事综述，报告还会给出“写作工作集”建议。一个 1000 篇的库可以在 A–F 上很强，却仍不适合直接拿来写作；正确做法是保留完整证据池，再建立按主题、论证角色、优先级和综合笔记组织的可回溯工作集，而不是删除原库。

### 检索式不再是报告里的黑箱

你带来的检索式会被保留为 **q0**，而不是被 AI 悄悄替换。后续优化只能做可解释的原子改动，例如补一个同义词、增加一个缩写、调整一个字段或新增一个来源；每轮都必须重新执行并留下结果。

报告会把 q0 与后续版本并列展示：检索式原文、来源、执行日期、命中数、执行状态、每轮改动，以及开发集和独立验证集的召回结果。若当前只有首轮探索，它会明确写出“尚未完成优化”，不会把一次试跑包装成稳健策略。

这也是为了避免循环论证：用于调词的开发集不能同时充当最终验证集。Dataset Builder 通过留出的综述、标准、引文或时间路径构建并冻结候选验证集；Query Optimizer 无权读取它；Blind Evaluator 只在最终检索式冻结后评估它。隔离的是证据流程，而不只是不同 agent 的“记忆”。

```text
输入确认 → 范围建模 → 检索计划 → 多源检索 → 去重 → 筛选 → 迭代优化 → A–F 计算 → 审计包
   ✅          ✅          🔧         🔧       ✅       🔧         🔧           ✅         ✅
```

## 六维框架

22 个指标（伞式综述 25 个）。六个维度平级，不合成总分。任何一维的致命短板都不能被其他维度掩盖。

| 维 | 问题 | 衡量什么 |
|:---:|---|---|
| **A · 覆盖** | 已知必收录文献找回来了吗？ | 基准集召回、检索式灵敏度、多源候选下界 |
| **B · 饱和度** | 检索还在继续增长吗？ | GGR、DRR、独立路径完成 + 独立验证 |
| **C · 平衡** | 主题、来源或观点偏斜了吗？ | Top-share、CV、Gini、Shannon 熵、作者集中度、观点偏斜度（支持/质疑/条件性证据） |
| **D · 时效** | 文献库是否反映当前研究状态？ | 来源新鲜度、近年比例（按领域自适应）、前沿覆盖 |
| **E · 学术影响与来源背景** | 核心引用和领域渠道的结构背景如何？ | h-core、Tier-1 覆盖（*仅背景信号——不是质量裁决*） |
| **F · 可用性** | 能实际用来写综述吗？ | 检索可复跑、摘要覆盖率、全文获取率、去重、可追溯、撤稿核查 |

→ [方法学全文](docs/methodology.md) · [指标注册表](schemas/indicator-registry.json) · [标准说明书](references/user-standards-guide.md)

## 你会得到什么

每一次运行产出独立、可复现的审计包：

```text
out/
├── audit.md          ← 人读报告（优先行动项置顶）
├── audit.html        ← 渲染 HTML
├── audit.json        ← 机读（含完整 indicator_register）
├── manifest.json     ← sha256、git commit、Python 版本
├── inputs/           ← 所有输入以哈希前缀复制
└── .tmp/             ← 自动生成的精简配置
```

→ [理解输出](docs/outputs.md)

## 能与不能

| 能 | 不能 |
|---|---|
| 诊断覆盖、饱和、平衡、时效、可用性 | 替代领域专家的纳入判断 |
| 产出可追溯、可复现的运行包 | 保证全球文献穷尽性 |
| 在明确假设下给出多源下界估计 | 替代 AMSTAR-2、ROBIS 或批判性评价工具 |
| 自动去重、字段补全、检索扩展、基础统计 | 自动决定"该不该纳入这篇论文" |
| 为超出范围的问题提供降级服务 | 评估单篇研究的内部有效性 |

## 设计原则

- **不合成总分。** 六个维度平级——完美的 A1 不能掩盖失灵的 F1。（对比：ScholarEval 的 8 维加权平均适合成品质量评估，但用于文献库诊断会掩盖致命的单维短板——就像车子有一个轮子没了，但"平均分"还有 3.8/5.0。）
- **证据分级。** 每个结论标注证据状态：`实测 · 估计 · 自动初筛 · 待人工核验 · 不可评估`。
- **阈值是信号，不是判决。** 所有默认值附有依据说明；所有值可被用户覆盖。
- **隐私优先。** 无绝对路径、不存 API key、输入文件以哈希前缀命名。
- **可复现。** 每次运行记录 git commit、脚本 sha256、Python 版本、全部输入哈希。

## 适用范围

**支持**：计算机与 AI、电子通信、机械制造、土木建筑、材料工程、化工、生医工、能源环境、航空航天、交通工程。

**不支持**：纯数学、纯物理、纯化学、临床医学、基础生命科学。

**综述类型**：系统综述 · 范围综述 · 叙事综述 · 快速综述 · 伞式综述

超出范围的问题提供降级服务（题录健康检查/检索策略设计）——从不直接拒绝。

→ [输入协议](references/intake-protocol.md) · [检索策略协议](references/search-strategy-protocol.md)

## 安装

### Claude Code / Desktop

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.claude/skills/literature-library-eval
```

重启 Claude 即可。

### Codex

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.codex/skills/literature-library-eval
```

### 依赖

| 依赖 | 用途 |
|---|---|
| Python 3.10+ | 所有命令行脚本 |
| 互联网 | OpenAlex、Crossref、arXiv 等开放 API |
| **无需 API key** | 全部数据来源为开放获取 |

## 文档

| 读者 | 资源 |
|---|---|
| **新用户** | [README.zh-CN.md](README.zh-CN.md) · [快速开始](#快速开始) |
| **深度了解** | [方法学](docs/methodology.md) · [架构](docs/architecture.md) · [输出说明](docs/outputs.md) |
| **集成** | [集成指南](docs/integrations.md) · Zotero / 数据库 / 配套 skill |
| **标准参考** | [用户标准说明书](references/user-standards-guide.md) · [指标注册表](schemas/indicator-registry.json) |
| **AI Agent** | [SKILL.md](SKILL.md) · [输入协议](references/intake-protocol.md) · [检索协议](references/search-strategy-protocol.md) |
| **开发者** | [run-config-schema.json](schemas/run-config-schema.json) · [架构](docs/architecture.md) · [指标注册表](schemas/indicator-registry.json) |

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| v1.0 | 核心 A–F（22+3 指标）、CLI、5 种综述类型、9 个工程 profile | ✅ 当前 |
| v1.x | BibTeX/RIS/CSV 导入、Scopus/WoS/IEEE 适配器、Crossref/Semantic Scholar | 🔜 下一步 |
| v2.0 | `run_full_audit.py`——端到端编排（搜→筛→评→报一键执行） | 📋 规划中 |
| 未来 | `review-manuscript-audit`——PRISMA 合规、引用完整性、研究质量工具匹配 | 💡 计划中 |

## 参与贡献

MIT License。欢迎 Issue 和 Pull Request。特别有价值的贡献方向：

- 格式导入器（BibTeX, RIS, CSV, Zotero API）
- 数据源适配器（Scopus, Web of Science, IEEE Xplore）
- 报告国际化
- 更多工程领域 profile 和 venue 映射

详见 [LICENSE](LICENSE)。

---

<p align="center">
  不是"你的库够不够好？"——<strong>你下一步该做什么？</strong>
</p>
