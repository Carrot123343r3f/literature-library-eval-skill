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
5. **C 的主题与来源平衡使用 CV、Gini、归一化 Shannon 和主题—来源交叉表做诊断；E 的 h-core 和 Tier-1 仅提供质量背景，不是研究质量裁决**。F 的去重、版本、撤稿只提供上下文或警示。
6. **不把 API key、令牌、绝对本地路径、受限全文写入输出**。

## A2/B 的自主检索

若用户未提供 `--query-hits`（A2）或无两轮 `search_rounds`（B），**首次评估时必须遵循 `references/search-strategy-protocol.md`**：

```
S3 确认完成 → SRCH-1 工程 PICO 分解 → SRCH-2 构建开发集+验证集
→ SRCH-3 构建概念矩阵 → SRCH-4 初始检索式(v1) → SRCH-5 原子迭代循环
→ SRCH-6 独立路径执行 → SRCH-7 汇总
```

### 检索关键规则

1. **工程 PICO 分解**：固定拆为 Object/Technology/Performance/Context 四要素，每项记录来源（user_provided / seed_papers / profile / standards / gap_diagnosis），写入 `context.search_decomposition`。
2. **开发集与验证集分离**：开发集用于迭代反馈（可多次使用）；独立验证集仅用于最终 A2 判定（看过就"烧掉"）。若无独立验证集，A2 证据状态标 `estimated`。
3. **原子迭代**：每轮只能做一种改动（加同义词/加缩写/改字段/加来源/加排除条件/移除低效词）。禁止同时大规模重写检索式。每轮记录在 `context.search_iterations[i]`。
4. **五类独立路径**：数据库布尔检索、后向引文追踪、前向引文追踪、相关文献网络、标准/指南——宽/中/窄不可充当独立路径。
5. **多源异构语法**：不把同一字符串投到不同数据库——先构建概念矩阵，再为每个来源转换字段语法。
6. **停止条件分离**：A2 停止（验证集 recall 达标 + 连续两轮无改善）≠ B 停止（GGR/DRR 收敛 + 路径完成 + 独立验证）。

### 首次评估简化流程

1. 通过 `scripts/search_for_eval.py` 执行首轮检索（带 `--dev-set` 和 `--pico` 参数）
2. 读取 `search_meta.json` 获取 `dev_recall` 和 `validation_recall`
3. 诊断漏项 → 选择一种原子改动 → 手动执行新检索式 → 记录到 `context.search_iterations`
4. 每轮计算新的 dev_recall 和 validation_recall
5. A2 停止条件满足时停止改检索式；B 停止条件满足时停止搜新

> ⚠️ `search_for_eval.py` 仅做候选发现/诊断性检索——top-50 cited 不是完整检索快照。discovery candidates 不等于纳入项；只有经过筛选确认后的新增文献才能填入 B1 GGR 分子和 B2 DRR 分子。

## 统一报告契约

将全部 21 子项（伞式 24 项：A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6 + A4/C4/F7）写入同一张六维评估总表；每行必须有维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。同步写入 `audit.json.indicator_register`。不得以 A 的召回结果替代或弱化 B–F 的任何结论。`not_assessable` 是有效结果，必须保留并说明缺失输入或核验路径。

报告按以下顺序组织：基本信息 → 本次评估输入与证据状态 → 评估方法与过程 → A-F 六维评估总表 → 各维度分析 → 改进建议 → 局限与声明。

## 伞式综述额外要求

当 `review_type = "umbrella"` 时，评估总表增加 A4/C4/F7 三行。此外报告中必须在综合判断段末尾和局限与声明段加入伞式免责声明，说明本报告不能代替 AMSTAR-2 的 16 项评分、ROBIS 偏倚风险评估、综述间结论冲突的实质分析。

## 交付物

`run_audit.py` 输出 `out/` 目录含：`audit.md`（人读）、`audit.html`、`audit.json`（含 `indicator_register`）、`manifest.json`（含 sha256）、`inputs/`（含所有输入文件的哈希命名副本）。若用户未提供运行产物，对应评估项直接标 `not_assessable` 并在报告中说明缺失输入；**不生成空壳文件**。

## 与脚本的关系

- `scripts/run_audit.py` — A–F 计算 + 报告生成（主入口）
- `scripts/search_for_eval.py` — 单轮 OpenAlex 诊断检索（支持 `--dev-set`/`--validation-set`/`--pico`）
- `scripts/search_iterator.py` — 多轮原子迭代验证（`validate` + `table` 命令）
- `scripts/collect_open_sources.py` — 多源快照收集
- `scripts/normalize_candidates.py` — 去重 + 版本族识别
- `scripts/validate_registry.py` — registry 一致性校验
- `compute.py` — 兼容性包装器（仅 A1 + 库健康，**勿用作主入口**）
