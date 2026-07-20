# AI 执行说明

## 统一报告契约

将全部 A1–F6 写入同一张六维评估总表；每行必须有维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。同步写入 `audit.json.indicator_register`。不得以 A 的召回结果汇总、替代、覆盖或弱化 B–F 的任何结论；`not_assessable` 是有效结果，必须保留并说明缺失输入或核验路径。
以 `SKILL.md` 为唯一流程入口。仅处理工程研究问题；纯基础学科或临床问题必须说明超出范围。

首次调用按 `references/confirmation-template.md` 的四批次模板执行一次确认：研究问题与边界、综述类型、库位置与格式（批次一·必须）→ 自主策略、数据源、纳入边界、输出格式（批次二·默认可跳过）→ 补充材料（批次三·可选但提示）→ 合法性声明（批次四·告知不征求）。确认后不中断常规工作；只在缺少必要输入、指定来源不可访问或范围发生实质变化时暂停。

## 不可违反的规则

1. A1/A2 只匹配稳定标识符；标题相似仅进人工核验队列。
2. 空查询结果的 A2 是实测召回 0；没有执行查询才是不可评估。
3. A3 需要多源、去重、明确边界与假设。单源 count 不得叫覆盖率或 Recall。
4. B 饱和度的趋稳结论需要独立验证、两轮低新增率（GGR ≤ `b_ggr_threshold`）、路径完成和低边际收益（DRR ≤ `b_drr_threshold`）同时成立；仅低数值不够。F1 查询可追溯需 run log 完整。
5. C 的主题与来源平衡使用 CV、Gini、归一化 Shannon 和主题—来源交叉表做诊断；E 的 h-core 和 Tier-1 仅提供质量背景，不是研究质量裁决。F 的去重、版本、撤稿、代码链接只提供上下文或警示。
6. 不把 API key、令牌、绝对本地路径、受限全文写入输出。

## A2/B 的自主检索

若用户未提供 `--query-hits`（A2）或无两轮 `search_rounds`（B），首次评估时通过 `scripts/search_for_eval.py` 自主执行以下：

1. 从 context.keywords 构造 3-5 条梯度检索式（宽：核心关键词 / 中：核心+子方向 / 窄：title 限定）
2. 在线执行（OpenAlex，per-page=50，cited_by_count:desc），去重
3. A2：检索命中 ∩ gold set（复用 A1 基准集）→ 灵敏度，产出 `query-hits.json`
4. B：检索结果中不在库内但 title 含核心词+cited_by≥阈值的文献为潜在新增 → 首轮 GGR = 潜在新增数/库规模，产出 `search_rounds`
5. B2 DRR 需第 2 轮才评（首轮标 not_assessable）；B3 独立验证需用户或人工确认（首轮标 not_assessable）
6. 潜在新增文献清单写入 `potential_additions.json`，前 20 条 title 写入 context.potential_additions，报告"改进建议"段呈现——建议用户纳入后复评 B 饱和度

首轮 GGR 在 B1 行显示为"首轮 X.XXXX（需第 2 轮确认趋稳）"。

先读取 `engineering-standards.md` 和 `indicator-dictionary.md`，把默认值与 profile、综述类型和用户协议合并后写入 `context.standards`。逐项执行 A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6；每项必须同时输出采用阈值、证据状态、verdict、定位原因和行动。不可自动验证的子项写 `not_assessable`，不得省略或默认为通过。

## 交付物

报告输出目录固定含三个文件：`audit.md`（人读）、`audit.html`、`audit.json`（机读，含 `indicator_register` 与全部计算明细）。若用户在确认时提供了 `query-plan.json`、`source-snapshot.json`、`decision-log.json`、`deduplication-log.json`、`run-log.json`，一并复制进输出目录并在报告"评估方法与过程"段引用；未提供的运行产物**不必生成空壳**，相关评估项直接标 `not_assessable` 并在报告中说明缺失输入。

脚本只计算规范化输入；调用者负责在运行前准备 `library`（题录）、`benchmark`（A1 基准集）、`gold`（A2 Gold set）、`candidate-snapshots`（A3 多源快照）、`context`（含 `search_rounds`/`taxonomy`/`keywords`/`benchmark_method` 等）等输入。对研究设计有效性、撤稿状态、版本等价性与全文可复现性，只能输出自动初筛或待人工核验。
