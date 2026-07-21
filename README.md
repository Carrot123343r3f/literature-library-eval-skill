# Literature Library Eval

帮工程研究者把模糊的文献库，转变为一份可解释、可复跑、知道下一步该补什么的综述准备度诊断。

**English:** An engineering-focused literature-library readiness diagnostic for systematic, scoping, narrative, rapid & umbrella reviews. Evaluates coverage, saturation, balance, recency, impact signals, and usability — not a single quality score.

[![Tests](https://img.shields.io/badge/tests-passing-green)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)
[![Version](https://img.shields.io/badge/version-model--x--2026--07-lightgrey)](#)

---

## 为什么需要它？

写综述前，你需要知道：**现有文献库能不能开始写？最大风险是什么？下一步补什么最有效？**

它不是"自动判库是否合格"，也不是论文质量打分器。它在三件事上帮你：

1. **诊断**：覆盖够不够？检索还在长吗？主题偏斜吗？近年的够吗？文献能拿到全文吗？
2. **定位**：不是给一个总分说"不行"——而是告诉你 _哪个维度_ 有问题、_为什么_。
3. **指引**：缺什么、怎么补、最小成本是什么。

## 60 秒开始

只需说：

> 使用 literature-library-eval 评估我的文献库，判断它能否支撑关于 **工业视觉缺陷检测的跨产线迁移** 的系统综述。

三步完成：

1. **提供题目**——AI 自动判断是否在工程范围内，询问最小必要信息（一次最多三个问题）
2. **提供库**（可选）——Zotero、CSV、BibTeX、JSON，或者让 AI 帮你设计检索策略
3. **得到报告**——诊断问题 + 优先级行动 + 输入快照 + 可复跑包

[打开示例报告 →](example-report.md)

## 你会得到什么

```text
┌─────────────────────────────────────────────────┐
│ 本次评估输入与证据状态                            │
│ ─────────────────────────────────────────────── │
│ 文献库 ✓ 有效（203 篇）                          │
│ A1 基准集 ✓ 有稳定 ID                            │
│ A2 Gold 集 ⚠ 与 A1 复用（非独立）                 │
│ 查询日志 ✗ 缺失  → F1 不可评估                   │
│ 筛选决定 ✗ discovery_only → B 不可判饱和          │
├─────────────────────────────────────────────────┤
│ 优先级行动                                       │
│ 1. 🔴 F1 检索可复跑：建库时查询未保留              │
│ 2. 🟡 A2 检索式灵敏度：A2 非独立                  │
│ 3. 🟡 A1 基准集召回：75%（6/8）                   │
└─────────────────────────────────────────────────┘
```

一个完整的评估包包含 `audit.md` + `audit.html` + `audit.json`，以及所有输入文件的快照和 `manifest.json`。

## 评估什么（六维框架）

| 维度 | 核心问题 | 要点 |
| --- | --- | --- |
| A 覆盖 | 已知必纳入文献找回来了吗？ | A1 基准集召回、A2 检索灵敏度、A3 多源候选下界 |
| B 饱和度 | 继续搜还会不会长？ | GGR、DRR、路径完成+独立验证 |
| C 平衡 | 主题与来源是不是偏在一边？ | 主题/来源 Top-share、CV、Gini、Shannon |
| D 时效 | 库跟得上当前研究状态吗？ | 来源新鲜度、近年比例、前沿覆盖、版本区分 |
| E 学术影响 | 引用核心与顶级渠道覆盖？ | h-core、Tier-1 命中（仅背景信号） |
| F 可用性 | 文献能拿来写综述吗？ | 查询可复跑、摘要、全文、去重、谱系、撤稿 |

共 21 子项（伞式综述 +3 = 24）。[完整指标说明 →](references/user-standards-guide.md)

## 适用范围

| ✅ 支持 | ❌ 不支持 |
| --- | --- |
| 计算机与 AI、电子通信、机械制造、土木建筑 | 纯数学、纯物理、纯化学 |
| 材料工程、能源、环境工程、化工过程 | 临床医学、基础生命科学 |
| 航空航天、交通、生物医学工程 | — |

**综述类型**：系统综述、范围综述、叙事综述、快速综述、伞式综述。

领域外的研究问题**不会直接被拒绝**——提供降级服务（题录健康检查 / 检索准备度设计）。

## 能做 / 不能做

| 能做 | 不能做 |
| --- | --- |
| 诊断覆盖、饱和、平衡、时效、可用性 | 替代领域专家的纳入判断 |
| 生成可追溯、可复跑的运行包 | 宣称文献库"绝对合格" |
| 在合理假设下估计多源候选下界 | 保证检索已穷尽全球所有文献 |
| 对范围外问题提供降级服务 | 替代 AMSTAR-2、ROBIS 等专门质量评估工具 |
| 自动完成去重、字段补全、检索扩展、基础统计 | 自动判"这篇该不该纳入" |

## 工作流

```text
题目或文献库
  → 最小确认（S0 识别 → S2 范围路由 → S3 必需项）
  → 输出 run-config.json（后台，用户不可见）
  → 规范化 / 检索 / 筛选证据
  → A–F 诊断
  → 报告 + 输入快照 + manifest.json
```

## 安装与兼容性

### Claude

将整个文件夹复制到 `~/.claude/skills/literature-library-eval`，重新打开应用即可。

### Codex

将整个文件夹复制到 `~/.codex/skills/literature-library-eval`，重新打开应用即可。

### 从 GitHub 克隆

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git
# 然后按上方 Claude / Codex 路径放置
```

### 依赖

- Python 3.10+（用于 `scripts/` 下的本地脚本）
- 在线搜索功能需要网络连接
- 无需 API key —— 使用开放源（OpenAlex、Crossref、Europe PMC、arXiv）

## 可复现性与隐私

- 每次运行会在 `out/inputs/` 下保存所有输入文件的副本，生成 `manifest.json`（含 sha256、git commit、Python 版本）
- 输入文件按 `标签__<sha256前12位>.ext` 命名，避免同名覆盖
- **不保存绝对路径** —— `manifest.json` 只记录文件名、sha256 和包内相对路径
- 不要在提示词、报告或仓库中写入 API key

## 文件结构

```text
literature-library-eval/
├── SKILL.md                     # 入口
├── AI_GUIDE.md                  # AI 执行规范
├── README.md                    # 你正在看的
├── references/
│   ├── intake-protocol.md       # 输入状态机
│   ├── user-standards-guide.md  # 标准说明书
│   ├── engineering-profiles.md  # 工程领域路由
│   ├── dimension-model.md       # A–F 六维模型
│   ├── indicator-dictionary.md  # 21+3 子项定义
│   ├── engineering-standards.md # 默认阈值
│   └── run-config-schema.json   # run-config JSON Schema
├── scripts/
│   ├── run_audit.py             # 报告生成器
│   ├── search_for_eval.py       # 诊断性检索器
│   ├── collect_open_sources.py  # 开放源快照采集
│   └── normalize_candidates.py  # 去重与版本族管理
├── tests/                       # 端到端测试
└── example-report.md
```

## 文档

| 面向 | 文档 |
| --- | --- |
| 用户 | [标准说明书](references/user-standards-guide.md)、[README](README.md) |
| AI | [AI 执行说明](AI_GUIDE.md)、[输入协议](references/intake-protocol.md) |
| 开发者 | [tests/](tests/)、[scripts/](scripts/) |

## 贡献与许可

MIT License —— 欢迎通过 Issue 和 PR 贡献。

---

<p align="center">
  不是「自动判库是否合格」——是帮你知道 <b>下一步该补什么</b>。
</p>
