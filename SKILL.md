---
name: literature-library-eval
description: 评估工程文献库是否足以支持既定研究问题、范围与综述类型（系统/范围/叙事/快速/伞式综述）。适用于计算机与AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程；不适用于纯数学、纯物理、纯化学、临床医学或基础生命科学。触发场景：用户说评估我的文献库、我的库够写综述吗、检索充分吗/饱和吗、算覆盖率/召回率、检验Zotero/题录库、准备度评估/文献库审计或给题目让查文献库时自动触发。不会自动替人决定库是否合格——自动结果始终与人工判断配合使用。
---

# 文献库评估 Skill

以本文件为唯一流程入口。仅处理工程研究问题；纯基础学科或临床问题必须说明超出范围。标准说明书见 `references/`。无需用户理解JSON Schema或文献计量术语——首次使用只需说出题目或提供库位置，AI会用最少问题补全必要信息。

## 首次调用：按 `references/intake-protocol.md` 状态机执行

1. **S0 识别用户输入形态**（只给题目 / 给文献库 / 说评估我的库 / 超出范围等 8 种入口）
2. **S2 范围路由** — 写入 `run-config.json.scope_status`（in_scope / cross_domain / out_of_scope / scope_uncertain）。`out_of_scope` → 停止 A-F，可仅输出题录健康；`cross_domain` → 适用部分完整评估，非适用部分降级
3. **S3 最小必要确认** — 必须确认：研究问题、综述类型、库位置、时间语言边界、自动检索授权、输出格式。可选补充（已知必纳入文献、核心关键词、分类框架等）主动提示但不追问
4. **三层标准确认** — 第一层告知默认、第二层展示核心门槛、第三层给四选一（默认/调整/自定义/仅数据）
5. 确认后**输出 `run-config.json`**，后续流程只读此配置，不重新依赖聊天上下文

## 不可违反的规则

1. **A1/A2 只匹配稳定标识符**（DOI/arXiv/PMID/OpenAlex ID）；标题相似仅进人工核验队列。`search_for_eval.py` 的标题候选绝不计入 A2 分子。
2. **空查询结果的 A2 是实测召回 0**；没有执行查询才是不可评估。
3. **A3 需要多源、去重、明确边界与假设**。单源 count 不得叫覆盖率或 Recall。
4. **B 饱和度的趋稳结论需要独立验证、两轮低新增率（GGR ≤ b_ggr_threshold）、路径完成和低边际收益（DRR ≤ b_drr_threshold）同时成立**；仅低数值不够。`search_for_eval.py` 的 discovery candidates 不等于纳入项——只有经标题摘要筛选和全文资格确认后的新增文献才能进入 GGR/DRR 分子。F1 查询可追溯需 run log 结构有效（至少含 source/query/date 字段）。
5. **C 的主题、来源、主题—来源交叉与观点偏斜分别诊断**：观点偏斜必须先声明中心主张，再统计支持/质疑/条件性证据；没有可审计分类时直接标警示，不得从泛化的正负面词猜测立场。E 的 h-core 和 Tier-1 仅提供质量背景，不是研究质量裁决。F 的去重、版本、撤稿只提供上下文或警示。
6. **不把 API key、令牌、绝对本地路径、受限全文写入输出**。

## A2/B 的自主检索

若用户未提供 `--query-hits`（A2）或无两轮 `search_rounds`（B），**首次评估时必须遵循 `references/search-strategy-protocol.md`**：

```
S3 确认完成 → SRCH-1 工程 PICO 分解 → SRCH-2 构建开发集+验证集
→ SRCH-3 构建概念矩阵 → SRCH-4 初始检索式(v1) → SRCH-5 原子迭代循环
→ SRCH-6 独立路径执行 → SRCH-7 汇总
```

### 首轮强制输出 A1–A3、B1–B3

用户未提供 seminal papers 或检索式时，**不得**因缺输入而跳过 A1–A3、B1–B3。默认执行 `scripts/run_initial_assessment.py`：它建立多源候选锚点和 A3 快照、自动初筛并机械留出开发/验证集，执行 AI 生成 q0 与原子变体，再把六项写入报告。首轮与后续轮次使用**同一张表、同一判定词和同一阈值**；A1/A2/B1/B2 的证据状态标为 `automated-screening`，A3 为 `partial_snapshot` 或 `estimated_lower_bound`，B3 如未完成则直接判 `fail`。证据状态只解释可复核性，不取代结果判定；详细边界写在总表后的证据状态说明。

- A1：候选锚点对库的稳定 ID 召回；经来源、相关性与冻结核验后才可升为 `measured`。
- A2：留出集对冻结前首轮策略的召回；经独立来源留出、冻结和盲测后才可升为 `measured`。
- B1：至少 q0 与一个原子变体的自动初筛新增率；经摘要/全文筛选及人工抽查后才可作为饱和判断的一部分。
- A3：至少两个来源去重后的候选下界；若有截断或失败，保留为 `partial_snapshot`，不能称覆盖充分。
- B2：不同数据库索引的来源级自动初筛边际率；它不是独立的引文/标准路径，不能用于最终 DRR 或饱和判定。
- B3：显示计划路径的首轮完成度与独立验证缺口；未完成独立验证时结论只能是“尚未证明饱和”。

首轮可以直接显示 A1/A2/B1 的阈值结果，但这些数值仍是 AI 主导证据；B2 的来源级初筛必须标警示，B3 未完成路径或独立验证必须判不通过。它们都不能被包装成“检索已趋稳”。

### C4 首轮观点偏斜检查

首轮处理完研究问题、PICO 和可用题名/摘要后，agent **必须**执行一次 C4 工作流：

1. 从研究问题写出一个可被反驳的中心主张（不把研究主题本身当作主张）；
2. 以该主张为唯一参照，将去重后的记录标为支持、质疑、条件性/混合或未分类；
3. 将 `claim`、`records_assessed`、四类计数、`classification_method` 与抽样核验数写入 `context.viewpoint_framework`；
4. 用反向术语、失败条件、比较对象和边界条件补检质疑证据，并把这次补检记录进检索迭代过程。

AI 的题名/摘要分类必须标 `automated-screening`；不能因结论看似一致就跳过反向补检。若题名/摘要不足以作分类或中心主张无法合理定义，C4 仍必须出现在首轮总表，直接判 `warning` 并说明“无法检查观点偏斜”，不得伪造计数或判定通过。

### 检索关键规则

1. **工程 PICO 分解**：固定拆为 Object/Technology/Performance/Context 四要素，每项记录来源（user_provided / seed_papers / profile / standards / gap_diagnosis），写入 `context.search_decomposition`。
2. **开发集与验证集分离**：开发集用于迭代反馈（可多次使用）；独立验证集仅用于最终 A2 判定（看过就"烧掉"）。若无独立验证集，A2 证据状态标 `estimated`。
   验证集可以由 AI 的 Dataset Builder 构建，但必须来自留出的发现路径，并记录 `source_routes`、`used_tested_query`、`used_for_query_optimization` 和 `frozen_at`。不同 subagent/线程本身不等于独立；验证集冻结后，Query Optimizer 不得读取验证集或其反馈。
3. **原子迭代**：每轮只能做一种改动（加同义词/加缩写/改字段/加来源/加排除条件/移除低效词）。禁止同时大规模重写检索式。每轮记录在 `context.search_iterations[i]`。
4. **五类独立路径**：数据库布尔检索、后向引文追踪、前向引文追踪、相关文献网络、标准/指南——宽/中/窄不可充当独立路径。
5. **多源异构语法**：不把同一字符串投到不同数据库——先构建概念矩阵，再为每个来源转换字段语法。
6. **停止条件分离**：A2 停止（验证集 recall 达标 + 连续两轮无改善）≠ B 停止（GGR/DRR 收敛 + 路径完成 + 独立验证）。
7. **证据不复用**：A3 快照不得直接作为 B2 新增纳入证据；A2 validation 与 B3 validation 复用时，B3 独立验证不可证明。通过 `evidence-manifest.json` 记录并检查这些关系。

### 首次评估自动诊断流程

> ⚠️ `search_for_eval.py` 是**首轮诊断检索器**：它按 profile 执行 OpenAlex + Crossref 的 q0（必要时补 arXiv/Europe PMC），并在有可用术语时执行透明的原子变体，自动产出 `search_meta.json` 内的版本表和迭代记录。配合 `--ai-provisional`，标题层自动初筛可生成 B1 与来源级 B2 的初评；它们不是筛选确认后的 GGR/DRR，也不能支持 B3 的饱和结论。它不做引文追踪、标准/指南路径或独立验证。首轮报告必须展示这些边界，不能把候选数或低增长率说成趋稳证据。

1. 通过 `scripts/search_for_eval.py` 执行首轮检索（带 `--dev-set` 和 `--pico` 参数）
2. 读取 `search_meta.json` 获取 `dev_recall` 和 `validation_recall`
3. 诊断漏项 → 选择一种原子改动 → **AI agent 手动执行新检索式** → 记录到 `context.search_iterations`
4. 每轮计算新的 dev_recall 和 validation_recall
5. A2 停止条件满足时停止改检索式；B 停止条件满足时停止搜新

### A1 无用户锚点时

用户没有提供必纳入文献时，AI 不得简单把 A1 留空后结束：先用 `scripts/build_anchor_candidates.py` 生成**候选锚点**，再由权威综述、标准、引文或其他留出路径补足来源说明，按相关性审查并冻结为 `benchmark.json`。候选文件只能写“待核验”，不能直接使 A1 成为 `measured`；若未完成审查，A1 如实为 `not_assessable`，报告说明需要冻结的基准集。

## 统一报告契约

将全部 22 子项（伞式 25 项：A1–A3、B1–B3、C1–C4、D1–D4、E1–E2、F1–F6 + A4/C5/F7）写入同一张六维评估总表；每行必须有维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。同步写入 `audit.json.indicator_register`。不得以 A 的召回结果替代或弱化 B–F 的任何结论。`not_assessable` 是有效结果，必须保留并说明缺失输入或核验路径。

报告按以下顺序组织：基本信息 → 本次评估输入与证据状态 → 评估方法与过程 → 检索策略与迭代过程 → A-F 六维评估总表 → 证据状态说明 → 各维度分析 → 改进建议 → 综合分析（含叙事综述写作工作集建议）→ 局限与声明。

## 伞式综述额外要求

当 `review_type = "umbrella"` 时，评估总表增加 A4/C5/F7 三行。此外报告中必须在综合判断段末尾和局限与声明段加入伞式免责声明，说明本报告不能代替 AMSTAR-2 的 16 项评分、ROBIS 偏倚风险评估、综述间结论冲突的实质分析。

## 交付物

`run_audit.py` 输出至 `--out` 指定目录含：`audit.md`（人读）、`audit.html`、`audit.json`（含 `indicator_register`）、`manifest.json`（含 sha256）、`inputs/`（含所有输入文件的哈希命名副本）。若用户未提供运行产物，对应评估项直接标 `not_assessable` 并在报告中说明缺失输入；**不生成空壳文件**。

## 与脚本的关系

- `scripts/run_audit.py` — A–F 计算 + 报告生成（主入口）
- `scripts/run_initial_assessment.py` — 无锚点/无检索式时的一键首轮：强制输出 A1–A3/B1–B3（均为初步证据，非饱和结论）
- `scripts/prepare_first_run_evidence.py` — 自动初筛候选锚点并固定开发/留出集（候选量足够时开发集与留出集均至少 15 篇）
- `scripts/search_for_eval.py` — 多源首轮诊断（q0 + 原子变体，自动输出迭代记录；支持 `--dev-set`/`--validation-set`/`--pico`）
- `scripts/build_anchor_candidates.py` — 多源 A1 候选锚点发现，同时生成 A3 快照；输出必须经审查和冻结后才可作为 benchmark
- `scripts/search_iterator.py` — 多轮原子迭代验证（`validate` + `table` 命令）
- `scripts/evidence_isolation.py` — 证据集来源、冻结状态与泄漏检查
- `scripts/collect_open_sources.py` — 多源快照收集
- `scripts/normalize_candidates.py` — 去重 + 版本族识别
- `scripts/validate_registry.py` — registry 一致性校验

证据集获取、验证集冻结和 subagent 隔离规则见 `references/evidence-isolation-protocol.md`；其机器可读契约见 `schemas/evidence-manifest-schema.json`。
