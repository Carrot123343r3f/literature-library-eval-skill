# 工程文献库审计

<p align="center">
  <strong>大多数综述在动笔之前就已经失败了。</strong>
</p>

<p align="center">
  不是因为写得不好，而是因为文献库本身就不完整——检索不可复现、看似饱和只是单一数据库的假象、主题均衡只是没收录对立证据。
  <em>在写综述之前做一次结构审计，比写完被推翻省几个月的时间。</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-18%20tests%20passing-22c55e" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License">
  <img src="https://img.shields.io/badge/indicators-21%20(%2B3%20umbrella)-8b5cf6" alt="Indicators">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Platform">
</p>

---

## 这是什么

**工程文献库审计**是一个综述准备度诊断工具——在写综述之前，验证你的文献库和检索过程是否具备支撑一篇可信综述的结构性证据。它不帮你写综述，不给一个模糊的综合分，它告诉你：能支撑什么、还缺什么、以及为什么。

### 你很可能遇到过这些问题

- 刚进入一个新领域，文献乱七八糟，根本不知道从哪搜起
- 收集了 200 篇论文，心里总不踏实：*是不是漏掉了一整个子方向？*
- 综述写完了交给导师/审稿人，对方一句"你漏了 XXX"——几个月白干
- 只搜了一个数据库，觉得够了——换一个数据库才发现完全是另一批论文
- 写完了再去检查检索是否完整——发现晚了，证据基础根本撑不住结论

**这是结构性浪费。** 综述写作流程应该从一次结构检查开始，而不是在结尾才发现问题。

### 它怎么解决

在动笔**之前**跑一次审计。一条命令（或跟 AI 说一句话），你就能得到：

- 按优先级排列的待修复项——阻断项排在最前面
- 六个独立维度的准备度——没有总分可以掩盖致命短板
- 每个输入都以 sha256 哈希记录——审计可复现
- 缺失的输入标为 `not_assessable` 而非隐藏——*"这是最便宜的修复方式"*

## 三分钟开始

```text
使用 literature-library-eval 评估我的文献库，
判断它能否支撑"工业视觉缺陷检测的跨产线迁移"的系统综述。
```

AI 会自动：

1. 确认研究问题、综述类型、工程领域和边界（一次最多三个问题）
2. 接受你的文献库（Zotero 导出/JSON，或者让 AI 设计检索策略）
3. 执行检索、计算指标、生成审计包

**当前 v1.0 自动化程度：**

| 状态 | 环节 |
|:---:|---|
| ✅ 已自动化 | 审计计算（`run_audit.py`）、单轮诊断检索（`search_for_eval.py`）、候选去重（`normalize_candidates.py`）、迭代验证（`search_iterator.py`）、报告生成 |
| 🔧 半自动 | 多轮检索迭代、跨数据库检索、引文追踪、正式筛选——由 AI agent 在对话中手动编排 |
| 📋 规划中 | 端到端一键编排（`run_full_audit.py`，计划 v2.0） |

```text
输入确认 → 范围建模 → 检索计划 → 多源检索 → 去重 → 筛选 → 迭代优化 → A–F 计算 → 审计包
   ✅          ✅          🔧         🔧       ✅       🔧         🔧           ✅         ✅
```

→ [查看示例报告](example-report.md)

## 六维框架

21 个指标（伞式综述 24 个）。六个维度平级，不合成总分。任何一维的致命短板都不能被其他维度掩盖。

| 维 | 问题 | 衡量什么 |
|:---:|---|---|
| **A · 覆盖** | 已知必收录文献找回来了吗？ | 基准集召回、检索式灵敏度、多源候选下界 |
| **B · 饱和度** | 检索还在继续增长吗？ | GGR、DRR、独立路径完成 + 独立验证 |
| **C · 平衡** | 主题和来源偏斜了吗？ | Top-share、CV、Gini、Shannon 熵、作者集中度、对立观点 |
| **D · 时效** | 文献库是否反映当前研究状态？ | 来源新鲜度、近年比例（按领域自适应）、前沿覆盖 |
| **E · 影响信号** | 核心引用和领域渠道覆盖了吗？ | h-core、Tier-1 覆盖（*仅背景信号——不是质量裁决*） |
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
| Python 3.10+ | `run_audit.py`、`search_for_eval.py`、`search_iterator.py` |
| 互联网 | OpenAlex、Crossref、arXiv 等开放 API |
| **无需 API key** | 全部数据来源为开放获取 |

**开发依赖：** `pip install -r requirements-dev.txt` 安装 `pytest` 和 `jsonschema`，用于运行测试套件。

## 文档

| 读者 | 资源 |
|---|---|
| **新用户** | [README.zh-CN.md](README.zh-CN.md) · [快速开始](#三分钟开始) · [示例报告](example-report.md) |
| **深度了解** | [方法学](docs/methodology.md) · [架构](docs/architecture.md) · [输出说明](docs/outputs.md) |
| **集成** | [集成指南](docs/integrations.md) · Zotero / 数据库 / 配套 skill |
| **标准参考** | [用户标准说明书](references/user-standards-guide.md) · [指标注册表](schemas/indicator-registry.json) |
| **AI Agent** | [SKILL.md](SKILL.md) · [输入协议](references/intake-protocol.md) · [检索协议](references/search-strategy-protocol.md) |
| **开发者** | [run-config-schema.json](schemas/run-config-schema.json) · [架构](docs/architecture.md) · [tests/](tests/) |

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| v1.0 | 核心 A–F（21+3 指标）、CLI、5 种综述类型、9 个工程 profile | ✅ 当前 |
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
