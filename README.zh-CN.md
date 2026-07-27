# 工程文献库审计

<p align="center">
  <strong>大多数综述在动笔之前就已经失败了。</strong>
</p>

<p align="center">
  不是因为写得不好，而是因为文献库本身就不完整——检索不可复现、看似饱和只是单一数据库的假象、主题均衡只是没收录对立证据。
  <em>在写综述之前做一次结构审计，比写完被推翻省几个月的时间。</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-test%20suite%20included-22c55e" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License">
  <img src="https://img.shields.io/badge/indicators-21%20(%2B3%20umbrella)-8b5cf6" alt="Indicators">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Platform">
</p>

<p align="center">
  <a href="README.md">English README</a>
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

## 三分钟体验 Demo：无需配置

仓库自带一个完整的本地示例：
[`example-all-modules-report/`](example-all-modules-report/)。里面已经准备好
了一份小型示例文献库、研究问题、检索证据和审计结果。你可以先看懂输出，
再换成自己的数据，也可以先查看[仓库内置的 HTML 报告](example-all-modules-report/audit/audit.html)。

在仓库根目录运行：

```bash
python scripts/run_audit.py \
  --run-config example-all-modules-report/run-config.json \
  --out demo-output
```

然后用浏览器打开 [`demo-output/audit.html`](demo-output/audit.html)。

在运行命令之前，也可以直接查看上面链接的仓库内置报告。

这里的“无需配置”是指：Demo 所需的研究问题、示例文献库、检索记录和
评估参数都已经随仓库提供，因此不需要 API Key、数据库账号或你自己的
Zotero 文献库。它是一个可复现的产品体验，不代表对你自己的研究主题完成
了审计。审计自己的课题时，需要换成自己的文献库并确认研究范围。

如果这个 Demo 帮你发现了综述流程中的问题，欢迎给项目点一个 Star，
也欢迎通过 Issue 分享结果或提出改进建议。

## 它和其他工具有什么不同

它位于“收集文献”和“开始写综述”之间：

| 工具 | 主要用途 |
|---|---|
| Zotero | 保存和整理文献 |
| 学术数据库 | 检索论文 |
| 本项目 | 检查文献库和检索证据是否足以支撑综述 |

它不是文献管理器、学术数据库，也不替代领域专家筛选。它的特点是：
输出可复现、分证据等级的诊断，明确说明当前文献库能支撑什么、缺什么，
以及下一步最应该做什么。

## 三分钟开始自己的审计

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
| ✅ 向导式工作流 | `run_full_audit.py` 产出可恢复的 `workflow-state.json` 与行动清单；支持 JSON/CSV/RIS/BibTeX 导入 |
| 🔧 人工确认 | 多轮迭代、跨库检索、引文追踪与筛选会留下证据工件；候选必须由人工明确纳入/排除 |

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

Windows PowerShell：

```powershell
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git `
  "$env:USERPROFILE\.claude\skills\literature-library-eval"
```

### Codex

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.codex/skills/literature-library-eval
```

Windows PowerShell：

```powershell
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git `
  "$env:USERPROFILE\.codex\skills\literature-library-eval"
```

### 依赖

| 依赖 | 用途 |
|---|---|
| Python 3.10+ | `run_audit.py`、`search_for_eval.py`、`search_iterator.py` |
| 互联网 | OpenAlex、Crossref、arXiv 等开放 API |
| **不在对话中索取凭据** | 开放来源仍可能要求预先配置 API key；不要在对话或输出产物中粘贴密钥 |

**开发依赖：** `pip install -r requirements-dev.txt` 安装 `pytest` 和 `jsonschema`，用于运行测试套件。

本地 Demo 只使用 Python 标准库和仓库内置文件。只有在主动选择联网检索或
元数据补齐时，才需要网络访问和相应数据源的凭据。

## 文档

| 读者 | 资源 |
|---|---|
| **新用户** | [英文 README](README.md) · [快速开始](#三分钟开始自己的审计) · [示例报告](example-report.md) |
| **深度了解** | [方法学](docs/methodology.md) · [架构](docs/architecture.md) · [输出说明](docs/outputs.md) |
| **集成** | [集成指南](docs/integrations.md) · Zotero / 数据库 / 配套 skill |
| **标准参考** | [用户标准说明书](references/user-standards-guide.md) · [指标注册表](schemas/indicator-registry.json) |
| **AI Agent** | [SKILL.md](SKILL.md) · [输入协议](references/intake-protocol.md) · [检索协议](references/search-strategy-protocol.md) |
| **开发者** | [run-config-schema.json](schemas/run-config-schema.json) · [架构](docs/architecture.md) · [tests/](tests/) |
| **贡献者** | [贡献指南](CONTRIBUTING.md) · [发布素材](docs/launch-kit.md) · [Issue 模板](https://github.com/Carrot123343r3f/literature-library-eval-skill/issues/new/choose) |

### 可选模块：单篇文献价值与补库建议

`scripts/run_paper_evaluation.py`（`rank_papers.py` 兼容入口）独立于 A–F 文献库准备度审计，按“资格→研究类型路由→方法学评价→可复核性/完整性/影响信号→库内边际贡献”输出优先精读、核心证据骨架与外部补库候选。它不会把引用量或期刊/会议名称当成研究质量裁决，也不会输出跨研究设计通用的文章质量总分。详见 [V2 依据与字段说明](references/paper-evaluation-v2.md)。

```bash
python scripts/run_paper_evaluation.py --library library.json --context context.json --run-config run-config.json --out paper-evaluation
```

外部候选默认使用 OpenAlex 自动检索，要求 `automation.allow_search=true`、`automation.allowed_sources` 包含 `openalex`，并在已配置环境中提供 `OPENALEX_API_KEY`。检索失败会退出并生成 `paper-evaluation-error.json`，不会虚构“全网 Top 20”。使用 `--external-candidates` 可基于已保存的候选快照离线复跑。

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| v1.0 | 核心 A–F（21+3 指标）、CLI、5 种综述类型、9 个工程 profile | ✅ 当前 |
| v1.x | Scopus/WoS/IEEE 适配器、Semantic Scholar | 🔜 下一步 |
| v1.1 | `run_full_audit.py`——可恢复向导工作流（导入→采集→筛选→审计→行动） | ✅ |
| 未来 | `review-manuscript-audit`——PRISMA 合规、引用完整性、研究质量工具匹配 | 💡 计划中 |

## 参与贡献

MIT License。欢迎 Issue 和 Pull Request。特别有价值的贡献方向：

- Zotero API 与机构数据库适配器
- 数据源适配器（Scopus, Web of Science, IEEE Xplore）
- 报告国际化
- 更多工程领域 profile 和 venue 映射

详见 [LICENSE](LICENSE)。

---

<p align="center">
  不是"你的库够不够好？"——<strong>你下一步该做什么？</strong>
</p>
