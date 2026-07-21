# AI 执行说明

## 统一报告契约

将全部 A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6（共 21 子项；伞式额外 A4/C4/F7）写入同一张六维评估总表；每行必须有维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。同步写入 `audit.json.indicator_register`。不得以 A 的召回结果汇总、替代、覆盖或弱化 B–F 的任何结论；`not_assessable` 是有效结果，必须保留并说明缺失输入或核验路径。

报告置顶增加"输入完整度表"和末尾增加"本次采用标准"附录——见 [user-intake-template.md](references/user-intake-template.md)。

以 `SKILL.md` 为唯一流程入口。仅处理工程研究问题；纯基础学科或临床问题必须说明超出范围。

## 首次调用：按 `references/intake-protocol.md` 状态机执行

**不再使用四批次死表**。按状态机流程：

1. **S0 识别用户输入形态**（见 intake-protocol 状态机——只给题目/给文献库/说"评估我的库"/超出范围等 8 种入口）
2. **S2 范围路由**——写入 `run-config.json.scope_status`（in_scope / cross_domain / out_of_scope / scope_uncertain）
   - `out_of_scope` → 停止 A-F，可仅输出题录健康
   - `cross_domain` → 适用部分完整评估，非适用部分降级
3. **S3 最小必要确认**——必须确认：研究问题、综述类型、库位置、时间语言边界、自动检索授权、输出格式。可选补充主动提示但不追问。
4. **三层标准确认**——第一层告知默认、第二层展示核心门槛、第三层给四选一（默认/调整/自定义/仅数据）。
5. 确认后**输出 `run-config.json`**，后续流程只读此配置，不重新依赖聊天上下文。

## 不可违反的规则

1. A1/A2 只匹配稳定标识符；标题相似仅进人工核验队列。`search_for_eval.py` 的标题候选绝不计入 A2 分子。
2. 空查询结果的 A2 是实测召回 0；没有执行查询才是不可评估。
3. A3 需要多源、去重、明确边界与假设。单源 count 不得叫覆盖率或 Recall。
4. B 饱和度的趋稳结论需要独立验证、两轮低新增率（GGR ≤ `b_ggr_threshold`）、路径完成和低边际收益（DRR ≤ `b_drr_threshold`）同时成立；仅低数值不够。`search_for_eval.py` 的 discovery candidates 不等于纳入项——只有经标题摘要筛选和全文资格确认后的新增文献才能进入 GGR/DRR 分子。F1 查询可追溯需 run log 结构有效（至少含 source/query/date 字段）。
5. C 的主题与来源平衡使用 CV、Gini、归一化 Shannon 和主题—来源交叉表做诊断；E 的 h-core 和 Tier-1 仅提供质量背景，不是研究质量裁决。F 的去重、版本、撤稿、代码链接只提供上下文或警示。
6. 不把 API key、令牌、绝对本地路径、受限全文写入输出。

## A2/B 的自主检索

若用户未提供 `--query-hits`（A2）或无两轮 `search_rounds`（B），首次评估时通过 `scripts/search_for_eval.py` 自主执行以下：

1. 从 context.keywords 构造 3-5 条梯度检索式（宽：核心关键词 / 中：核心+子方向 / 窄：title 限定）
2. 在线执行（OpenAlex，per-page=50，cited_by_count:desc，仅首屏 top cited——非完整快照），去重
3. A2：走稳定 ID 匹配（DOI/arXiv/OpenAlex ID）；标题候选另存为人工核验参考，绝不计入 A2 分子。产出 `query-hits.json`
4. B：检索结果中不在库内但 title 含核心词+cited_by≥阈值的文献为**发现候选**（discovery candidates），不等于纳入项。首轮 `included_high=0` 直至人工完成筛选。B1 显示 discovery GGR 作为参考，B1 判定标 `not_assessable`（需筛选确认）
5. B2 DRR 需第 2 轮且至少一轮突破 discovery_only 状态才可评；B3 独立验证需用户或人工确认（首轮标 not_assessable）
6. 潜在新增文献清单写入 `potential_additions.json`，前 20 条 title 写入 context.potential_additions，报告"改进建议"段呈现——建议用户纳入后复评 B 饱和度

> ⚠️ `search_for_eval.py` 仅做候选发现/诊断性检索——top-50 cited 不是完整检索快照，`mailto=` 为占位地址。discovery candidates 不等于饱和度的纳入项；只有经过标题摘要筛选、全文确认和资格审核的新增文献才能填入 B1 GGR 分子和 B2 DRR 分子。

首轮 B1 行显示为"发现阶段（需第 2 轮 + 筛选确认趋稳）"。

先读取 `engineering-standards.md` 和 `indicator-dictionary.md`，把默认值与 profile、综述类型和用户协议合并后写入 `context.standards`。逐项执行 A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6（伞式额外 A4/C4/F7）；每项必须同时输出采用阈值、证据状态、verdict、定位原因和行动。不可自动验证的子项写 `not_assessable`，不得省略或默认为通过。

## 交付物

报告输出目录固定含三个文件：`audit.md`（人读）、`audit.html`、`audit.json`（机读，含 `indicator_register` 与全部计算明细）。运行时，`run_audit.py` 会自动将用户提供的输入文件（`query-plan.json`、`source-snapshot.json`、`decision-log.json`、`deduplication-log.json`、`run-log.json`、library 文件）复制到 `out/inputs/`，并生成 `manifest.json`，包含每个文件的 sha256 哈希、原始路径和复制路径。

若用户未提供这些运行产物，对应评估项直接标 `not_assessable` 并在报告中说明缺失输入；**不生成空壳文件**。

### 伞式综述报告额外要求

当 `review_type = "umbrella"` 时，评估总表增加 A4/C4/F7 三行（普通综述仅 A1–F6 共 21 行）。此外，报告**必须在以下位置**加入伞式免责声明：

1. **综合判断段末尾**（紧跟综合判断文字后）——醒目的 blockquote：

> ⚠️ **伞式综述方法学提示**：伞式综述有独立的方法学标准（AMSTAR-2、ROBIS、综述间重叠分析）。本评估报告沿用文献库准备度的通用框架，仅对综述层面的 A4（综述类型确认/C4（综述间覆盖分布）/F7（质量评估就绪度）做初筛诊断。**本报告不能代替**：① AMSTAR-2 的 16 项逐条评分；② ROBIS 偏倚风险评估；③ 综述间结论冲突的实质分析。**强烈建议在完成文献库评估后，由领域专家对纳入综述进行独立的方法学质量审查。**

2. **局限与声明段**——补充说明伞式专用子项的估计边界和不可自动核验项。

3. 仅在报告中出现 A4/C4/F7，非伞式综述不显示。

脚本只计算规范化输入；调用者负责在运行前准备 `library`（题录）、`benchmark`（A1 基准集）、`gold`（A2 Gold set）、`candidate-snapshots`（A3 多源快照）、`context`（含 `search_rounds`/`taxonomy`/`keywords`/`benchmark_method` 等）等输入。对研究设计有效性、撤稿状态、版本等价性与全文可复现性，只能输出自动初筛或待人工核验。
