# Search Strategy Protocol（检索策略协议）

本文件定义文献库评估中检索式迭代的完整协议。它规范从初始策略构建到最终停止判定的全流程，替代此前"AI 自由改词"的隐式行为。

**定位**：本协议是 `literature-library-eval` skill 的子技能。评估流程的 S3 阶段（最小必要确认）完成后，若用户授权自动检索，AI 必须遵循本协议执行迭代，不再使用自由改词策略。

**核心原则**：每一步改动可审计、每轮结果可比较、A2 与 B 的停止条件不混淆、开发集与验证集不交叉污染。

---

## 1. 工程问题的结构化分解（Engineering PICO）

每个工程综述问题固定拆解为四要素。每项记录来源——不来自凭空推断。

| 要素 | 含义 | 来源示例 |
|---|---|---|
| Object/System | 研究对象/系统 | 用户给定、领域 profile、权威综述 |
| Technology/Method | 技术或方法 | 用户给定、种子论文、领域 profile |
| Performance/Metric | 性能目标/指标 | 用户给定、标准/基准论文 |
| Context/Application | 工况/应用场景 | 用户给定、领域标准文档 |

可选补充（视领域需要）：标准规范号、设备型号、数据集名称、缩写与历史术语。

**格式要求**：分解结果写入 `context.search_decomposition`，含每项的 source 字段：

```json
{
  "object": {"term": "industrial defect detection", "source": "user_provided"},
  "technology": {"term": "deep learning; transfer learning", "source": "seed_papers"},
  "performance": {"term": "accuracy; generalization; cross-line", "source": "user_provided"},
  "context": {"term": "manufacturing; production line", "source": "user_provided"},
  "supplements": [
    {"term": "CNN; ViT; ResNet", "source": "seed_papers", "category": "historical_terms"},
    {"term": "MVTec AD; NEU-DET", "source": "benchmark", "category": "datasets"},
    {"term": "AOI; SPI", "source": "standards", "category": "abbreviations"}
  ]
}
```

## 2. 开发集与验证集的分离（Dev Set vs Validation Set）

这是**最关键的科学性修复**。Gold 不能完全由同一轮搜索结果反向构造，否则 A2 会虚高（模型只是记住了自己找到的文献）。验证集可以由 AI 的 Dataset Builder 获取，但必须通过来源留出、冻结和 provenance manifest 实现程序隔离；不同 subagent 的记忆隔离本身不构成独立证据。

### 2.1 开发集（Dev Set）

用于迭代检索式、发现漏项、指导改词方向。

**来源**（按优先级）：
1. 用户提供的明确必纳入文献（≥ 3 篇）
2. 已知的领域高引综述/权威论文（从 profile 或 seed papers 提取）
3. 首轮宽检索的高被引结果（前 20 篇）——但必须标注为 `dev_set_origin: "initial_search"`，且不能同时进入验证集

**用途**：每轮检索后计算 `dev_recall` 作为迭代方向的快速反馈。

### 2.2 独立验证集（Validation Set）

仅用于**最终 A2 判定**，不参与检索式优化。任何迭代过程中看到的验证集论文都不能用于修改检索式——一旦看到，就"烧掉"了独立性。

**来源**（按优先级）：
1. 另一批独立综述/标准/基准论文——与用户提供的种子论文来自不同出处
2. 时间切分：最新发表论文（如近 6 个月）——这些不可能在检索式中被特化过
3. 引文追踪发现：种子论文的 forward/backward 引用中按主题和年份分层抽取

验证集候选不能由被测检索式单独发现。至少留出一条未参与 q* 优化的发现路径，并在 `evidence-manifest.json` 中记录 `source_routes`、`used_tested_query`、`used_for_query_optimization` 和 `frozen_at`。若验证集曾被检索式优化读取，A2 降级为 `estimated`。

**校验**：AI 必须在 `context.gold_set_metadata` 中声明：
- `validation_set_source`: 来源描述
- `independence_rationale`: 为什么与开发集不交叉
- `dev_validation_overlap_check`: 是否已检查开发集与验证集无重叠

### 2.3 A2 的两种 Recall

| Recall 类型 | 计算对象 | 用途 | 在报告中的呈现 |
|---|---|---|---|
| `dev_recall` | 开发集 | 迭代方向反馈——这个改动有效吗？ | 检索迭代比较表中 |
| `validation_recall` | 独立验证集 | 最终 A2 判定——检索式有没有真正泛化？ | A2 评估表中作为 `a2_recall` 的主值 |

**若用户没有提供独立验证集**：AI 可以由 Dataset Builder 从留出的综述、标准和引文路径构建候选验证集；在冻结前不得用于最终评分。若仍没有来源留出或冻结记录，`a2_recall` 使用开发集计算，但证据状态降级为 `estimated`，并在 note 中注明"开发集=验证集复用，A2 可能被高估"。

### 2.4 Subagent 隔离

Dataset Builder、Query Optimizer、Blind Evaluator 和 Audit Agent 可以由同一模型的不同线程执行，但必须使用角色隔离的输入工件：Query Optimizer 只读 dev set，Blind Evaluator 在 q* 冻结后才读 validation set，Audit Agent 检查 manifest 而不参与选文献。共享目录、缓存或把 validation recall 转述给优化器，都视为验证集泄漏。

## 3. 检索路径（True Independent Pathways）

B2 的路径必须是**真正独立的发现通道**——宽/中/窄检索式只是同一数据库中的查询变体，不能充当独立路径。

### 3.1 五类独立路径

| 路径 ID | 类型 | 含义 | 独立性依据 |
|---|---|---|---|
| `db_boolean` | 数据库布尔检索 | 结构化查询（OpenAlex/Crossref/Scopus 等） | 基于关键词/字段索引 |
| `backward_citation` | 后向引文追踪 | 从种子论文的参考文献中提取 | 基于引用关系——不依赖关键词 |
| `forward_citation` | 前向引文追踪 | 找到引用了种子论文的文献 | 基于引用关系——不依赖关键词 |
| `related_articles` | 相关文献网络 | 基于共引/耦合的相似文献推荐 | 基于引用网络——不依赖关键词 |
| `standards_guidelines` | 标准/指南/会议 | 直接检索领域标准文档、指南、核心会议论文集 | 基于来源类型而非关键词 |

### 3.2 每条路径必须记录

```json
{
  "pathway_id": "db_boolean_openalex_v3",
  "type": "db_boolean",
  "search_queries": ["query_v3_wide", "query_v3_narrow"],  // 该路径内的查询变体
  "sources": ["OpenAlex"],
  "candidates": 342,
  "screened_high_confidence": 18,   // 仅筛选确认后填入
  "new_high_confidence": 7,         // 对此前所有路径去重后的净新增
  "dedup_rule": "title-normalized (all prior pathways)",
  "screening_status": "screened_complete" | "discovery_only",
  "yield": 0.020,
  "note": ""
}
```

注意：`new_high_confidence` 必须按路径声明的先后顺序去重——先声明的路径先计数，不能因全局去重顺序让 DRR 失真。

### 3.3 路径数量要求

| 综述类型 | 最少独立路径数 |
|---|---|
| 快速综述 | ≥ 2 |
| 叙事/范围综述 | ≥ 3 |
| 系统综述 | ≥ 4 |
| 伞式综述 | ≥ 5（其中至少 2 条为 citation 类路径）|

## 4. 原子改动规则（Atomic Iteration Rules）

每轮只能做**可审计的原子改动**。禁止 AI 同时大规模重写检索式。

### 4.1 允许的单步改动

| 改动类型 | 示例 | 记录要求 |
|---|---|---|
| `add_synonym` | 加一个同义词组 `"cross-line transfer" → ("cross-line transfer" OR "cross-domain transfer")` | 记录新增词、来源 |
| `add_abbreviation` | 加缩写/历史术语 `"AOI" → ("AOI" OR "automated optical inspection")` | 记录全称、来源 |
| `modify_field` | 改一个字段限制 `title:"defect detection"` → `title,abstract:"defect detection"` | 记录改前/改后字段 |
| `add_source` | 新增一个数据库 `OpenAlex only` → `OpenAlex + Crossref` | 记录新增源、语法映射 |
| `add_exclusion` | 加入一个经过验证的排除条件 `NOT retracted:true` | 记录排除条件、验证方式 |
| `remove_low_yield_term` | 移除一个低频低效关键词 | 记录移除词、移除理由 |

### 4.2 禁止的改动

- 同时修改多个 AND 子句
- 替换整条检索式（"重写为 xxx"）
- 一次加多个同义词组而不记录每个的来源
- 修改检索式后不重新执行、不记录比较表

### 4.3 每轮信息

每轮必须产出以下字段（写入 `context.search_iterations[i]`）：

```json
{
  "iteration_id": "v3",
  "parent_iteration": "v2",
  "change_type": "add_synonym",
  "change_description": "加入 'cross-domain transfer' 同义词组",
  "change_source": "seed_papers: 3 篇种子论文使用了 cross-domain 而非 cross-line",
  "queries": {
    "db_boolean_openalex": {
      "wide": "(\"defect detection\" OR \"anomaly detection\") AND (\"transfer learning\" OR \"domain adaptation\" OR \"cross-domain transfer\")",
      "narrow": "title:(\"defect detection\") AND (\"transfer learning\" OR \"cross-domain transfer\")"
    },
    "db_boolean_crossref": {
      "wide": "...",
      "narrow": "..."
    }
  },
  "execution_date": "2026-07-21",
  "results": {
    "total_hits": 342,
    "deduplicated_hits": 287,
    "dev_recall": 0.73,
    "validation_recall": 0.65,
    "sampled_relevance_rate": 0.72,
    "discovery_candidates": 31
  },
  "failures": [],
  "decision": "continue" | "a2_stop" | "b_stop" | "max_iterations"
}
```

## 5. 多源异构语法映射（Heterogeneous Multi-Source）

不能把同一个字符串原样投到不同数据库。AI 必须先构建**概念矩阵**，再翻译为各来源可执行的字段语法。

### 5.1 概念矩阵

将分解后的核心概念 × 同义词构建为矩阵，发给每个来源时选择该来源支持的字段语法。

```
概念       │ 同义词
───────────┼─────────────────────────────────────────
defect     │ "defect detection", "anomaly detection", "surface defect", "AOI"
transfer   │ "transfer learning", "domain adaptation", "cross-line", "cross-domain"
industrial │ "manufacturing", "production line", "fabrication"
```

### 5.2 来源语法映射

| 来源 | 字段语法 | 示例 |
|---|---|---|
| OpenAlex | `search=` (通用), `filter=title.search:` | `search="defect detection"&filter=title.search:"transfer learning"` |
| Crossref | `query.title=`, `query.bibliographic=` | `query.bibliographic="defect+detection+transfer+learning"` |
| arXiv | `ti:`, `au:`, `all:` | `ti:"defect detection" AND all:transfer` |
| Semantic Scholar | `title:`, `keyword:` | `title:"defect detection" keyword:transfer` |
| IEEE Xplore | `("Article Title":...)`, `("All Metadata":...)` | `("Article Title":"defect detection") AND ("All Metadata":transfer learning)` |
| Scopus/WoS | 通过 API 适配器转换（v1.x roadmap） | — |

**AI 责任**：每次新增来源时，必须在 `context.source_syntax_map` 中记录该来源的字段语法映射和转换规则。

### 5.3 A3 下界的诚实标注

仅当**所有来源**满足以下条件时，A3 才标注为 `estimated_lower_bound`：
- 所有来源完成了分页（无截断）
- 边界一致（时间、语言、文献类型过滤统一）
- 去重规则明确且可重跑

否则标注为 `partial_snapshot` 并在 note 中说明哪些来源不完整。

## 6. 停止条件分离

A2 的停止与 B 的停止是两套独立判据，不能混淆。

### 6.1 A2 停止（检索式已优化到足够好）

| 条件 | 要求 |
|---|---|
| 独立验证集召回达标 | `validation_recall` ≥ `a2_min_recall`（依综述类型） |
| 连续两轮无实质改善 | `validation_recall` 连续两轮增长 < 0.03 |
| 或达到最大迭代轮数 | 默认 8 轮——超出后保留当前最佳检索式并标注 |
| 或无更多可加的术语/来源 | 所有概念矩阵中的同义词已用尽、所有计划来源已添加 |

**A2 停止 ≠ B 饱和**。即使检索式能找回所有已知文献，也不代表检索结果中不存在新的高相关文献。

### 6.2 B 停止（不再发现新的纳入文献）

| 条件 | 要求 |
|---|---|
| GGR 收敛 | 最后两轮经筛选确认的新增纳入量 < `b_ggr_threshold`（默认 0.02） |
| DRR 收敛 | 所有独立路径的边际收益率 < `b_drr_threshold`（默认 0.05） |
| 所有计划路径完成 | 五类独立路径中至少计划内的全部完成 |
| 独立验证未发现漏项 | B3 的独立验证通过 |

**B 停止 ≠ A2 已优化**。尽管 GGR/DRR 很低，但可能因为检索式本身太窄——检索式写得太窄同样会让结果集单调递减。

**A3/B2 证据不得直接复用**。A3 的多源快照只支持候选下界；B2 只能使用经筛选确认的新纳入文献。若 manifest 显示两者共享来源，B2 标为 `not_assessable`。

**A2/B3 验证不得默认复用**。若二者使用同一个 validation dataset，B3 的独立验证不可证明，不能据此声称饱和。

### 6.3 停止的联合判据

最终评估时，A2 与 B 同时满足各自停止条件才可声称检索充分。仅一方满足将在报告中标注另一方不满足的具体原因。

## 7. 自动筛选的诚实标注

AI 可以按冻结的纳入/排除规则完成标题、摘要、全文三阶段筛选。但 B1/B2 的结果必须诚实标注证据状态。

| 筛选阶段 | 证据状态 | 说明 |
|---|---|---|
| 标题筛选完成 | `automated-screening` | 按关键词规则匹配，未人工核验 |
| 摘要筛选完成 | `automated-screening` | 同上 |
| 全文筛选完成 | `automated-screening` | 同上——AI 摘要 ≠ 全文阅读 |
| 人工已抽查确认 | `measured` | 至少 20% 或 20 条（取大者）经人工核验 |

**B1/B2 的分子（`included_high`、`new_high_confidence`）在自动筛选阶段应称为 `screened_inclusions` 而非 `high_confidence`。只有经过人工确认后，才提升为 `measured` 状态的 `included_high`。

## 8. 作为子技能的执行流程

本协议作为 `literature-library-eval` 的子技能嵌入整体流程。AI 在 S3 确认后按以下步骤执行：

```
S3 确认完成（run-config.json 已输出）
  │
  ├─→ [SRCH-1] 工程 PICO 分解 → context.search_decomposition
  │
  ├─→ [SRCH-2] 构建开发集 + 独立验证集 → context.gold_set_metadata
  │     └─ 若用户未提供独立验证集 → 标注，A2 将使用 estimated 证据状态
  │
  ├─→ [SRCH-3] 构建概念矩阵 → context.source_syntax_map
  │
  ├─→ [SRCH-4] 初始检索式（v1）→ 执行 → 记录迭代
  │
  ├─→ [SRCH-5] 原子迭代循环（v2, v3, ...）
  │     │  每轮：诊断漏项 → 选择一种原子改动 → 执行 → 记录比较表
  │     │  检查 A2 停止条件？→ 是 → 停止改检索式
  │     │  检查 B 停止条件？→ 是 → 停止搜新
  │     └  检查最大轮数？→ 是 → 保留最佳
  │
  ├─→ [SRCH-6] 独立路径执行（不依赖关键词的路径不能跳过）
  │
  └─→ [SRCH-7] 汇总 → search_meta.json + query-hits.json → 交给 run_audit.py
```

## 9. 与 run_audit.py 的接口

本协议产出的关键 context 字段：

| 字段 | 类型 | 使用者 |
|---|---|---|
| `context.search_decomposition` | object | 报告方法段——展示 PICO 分解 |
| `context.gold_set_metadata` | object | A2——区分 dev_recall vs validation_recall |
| `context.search_iterations` | array | 报告方法段——展示迭代比较表 |
| `context.source_syntax_map` | object | A3——多源异构语法转换记录 |
| `context.independent_pathways` | array | B2——五类路径的独立证据 |
| `context.search_rounds` | array（已有，增强） | B1/B2—需带 `screening_status` 和 `pathway_type` |
| `context.final_dedup_rule` | string | A3/F4——可复算的去重规则声明 |

## 10. 与现有 search_for_eval.py 的关系

## 10.1 无锚点、无检索式的首轮规则

`run_initial_assessment.py` 是首轮默认编排器。它必须输出 A1–A3、B1–B3：候选锚点以稳定 ID 计算 A1；自动留出的验证集计算 A2；多源快照计算 A3；q0 与原子变体的自动初筛新增率计算 B1；不同数据库索引的来源级边际率作为 B2 初筛；B3 显示路径完成度与独立验证缺口。首轮与后续轮次按同一阈值输出：A1/A2/B1 直接给 pass/fail，B2 因尚非独立路径给 warning，B3 未完成路径或独立验证时给 fail。A1/A2/B1/B2 的证据状态为 `automated-screening`，A3 为 `partial_snapshot` 或 `estimated_lower_bound`；证据状态解释可复核性，不改写结论。它们用于决定下一步优先修什么，不用于声称检索充分、独立验证或最终饱和。

升级条件：A1 需锚点来源与相关性审查并冻结；A2 需真正独立的验证来源和冻结后的盲测；B1/B2 需摘要/全文筛选与人工抽查。B2/B3 的最终结论仍要求非关键词独立发现路径，首轮不会给出替代结论。

`search_for_eval.py` 是**首轮诊断检索的脚本实现**：保留 q0，并在有可用术语时执行原子变体，把版本与过程记录写入 `search_meta.json`。它仍是协议的参考实现而非完整编排器。

| 脚本 | 角色 |
|---|---|
| `search_for_eval.py` | 多源首轮诊断 — q0 + 原子变体、候选发现与快速 A2/B1/B2 初评 |
| `build_anchor_candidates.py` | 多源候选发现 — 产出待筛选 A1 候选与 A3 快照；它本身不能证明独立性，也不直接计入 A1 |
| `search_iterator.py`（新增） | 多轮原子迭代管理器 — 生成比较表 + 追踪改动 |
| `run_audit.py` | 消耗协议产出的 context 字段，无感知迭代细节 |

短期可以继续使用 `search_for_eval.py` 做首轮初探，由 AI 手动执行后续迭代（AI 在对话中执行检索→比对→记录→改词→再执行），`search_iterator.py` 作为验证/辅助脚本验证记录完整性。长期由 `search_iterator.py` 和 `run_full_audit.py` 编排全线。
