---
name: literature-library-eval
description: 评估工程研究综述的文献库是否足以支持既定问题、范围与综述类型。适用于计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程；不适用于纯数学、纯物理、纯化学、临床医学或基础生命科学。使用于用户要求评估工程文献库、检验检索充分性/覆盖/趋稳、判断 Zotero 或结构化题录库能否支撑综述，或需要生成可复现的文献库准备度评估时。持系统、范围、叙事、快速与伞式综述。不会自动替人决定"库是否合格"——自动结果始终与你的人工判断配合使用。首次使用只需说出题目或提供库位置，AI 会用最少问题补全必要信息，不需要你理解 JSON schema 或文献计量术语。
---

# 工程综述文献库评估

将文献库准备度拆为覆盖、饱和度、平衡、时效性、质量和可用性六个可验证维度。不要生成单一总分，也不要把篇数、引用量、期刊等级或附件数量当作充分性结论。

**定位**：帮工程研究者把模糊的文献库，转变为一份可解释、可复跑、知道下一步该补什么的综述准备度诊断。这不是"自动判库是否合格"，也不能代替人工筛选、人工核验、AMSTAR-2/ROBIS 评分或研究质量裁决。

**自动化边界**：去重、字段补全、检索扩展、基础统计——自动完成。但"是否应纳入""是否属于核心文献""Gold 是否独立可靠""伞式综述中的综述类型判定"本质上需要语义判断或人工复核——自动初筛结果必须显式标注，不得伪装成人工筛选结论。低置信度自动决策不进入核心集合。

**阈值免责**：本 skill 中的各项阈值（如 A1≥0.75、GGR<0.02、Shannon≥0.55 等）均为基于工程文献计量经验的参考值，旨在辅助识别可能的风险信号，不等于文献库质量的绝对标准。所有阈值均应结合具体研究问题、领域惯例和人工判断综合解读；pass/warning/fail 是自动化诊断提示，不是质量裁决。

## 范围与触发

仅用于工程问题：研究对象、系统、方法、工况、性能指标、标准、数据集、基线或应用场景应能被明确界定。遇到纯基础学科或临床问题，说明超出此 skill 的适用范围；此时**不启动 A–F 工程充分性结论**，可提供降级服务——题录健康检查（元数据完整性、去重、基础时效描述），不套用工程充分性结论。

## 一次性确认后自主运行

首次调用不按死表——严格按 `references/intake-protocol.md` 的状态机执行：S0 识别用户输入形态 → S2 范围路由 → S3 最小必要确认 → 输出 `run-config.json`。不要求用户理解 JSON schema、Gold set 或文献计量术语。一次最多问三个问题。范围外问题不拒绝，提供降级护航（题录健康/检索设计）。确认后自主检索、调词、去重、筛选和生成报告；仅在缺少必要输入、无法访问已指定来源，或新发现会实质改变范围时暂停。

读取 `references/intake-protocol.md`（状态机输入协议）、`references/confirmation-template.md`、`references/autonomous-run.md`、`references/engineering-profiles.md`、`references/dimension-model.md`、`references/indicator-dictionary.md`、`references/engineering-standards.md`、`references/user-standards-guide.md`（用户标准说明书），以及与问题对应的检索说明。执行细则见 `AI_GUIDE.md`。保存查询计划、来源快照、筛选/去重/版本决策、失败日志和证据状态。绝不要求用户在提示词中提交 API key；只使用现有 MCP、环境变量或用户已配置的合法连接。

## 执行流程

1. 规范化库，提取 DOI、PMID、PMCID、arXiv、OpenAlex 等稳定标识符；将版本族与重复记录分开处理。
2. 选择一个或多个工程 profile，并记录置信度、数据库覆盖差异和工程问题框架。
3. 生成每个来源的字段化检索式与 `query-plan.json`；记录日期、字段、过滤器和完整原文。
4. 运行分页开放源采集；记录每个来源是否完整、达到上限或失败。存在合法订阅源时增强检索，失败时继续其他来源。
5. 运行候选归一化器：共享稳定标识符可合并；标题—年份冲突和预印本—正式版候选必须进入版本复核队列。
6. 依纳入标准自动筛选，保留每条决策、理由和置信度；低置信度候选不进入核心集合。
7. 构建 A1 基准集、A2 gold set 和 A3 多源候选快照。稳定标识符是 A1/A2 的唯一自动匹配依据。
8. 若 A2（query-hits）或 B（search_rounds）的输入数据缺失，通过 `scripts/search_for_eval.py` 自主执行梯度检索式（宽/中/窄），产出稳定 ID 命中的 A2 数据（标题候选另存为人工核验参考，不入 A2 分子）、首轮 discovery candidates（不等于纳入项）与潜在新增文献清单——此脚本定位为候选发现/诊断性检索，非完整检索快照。
9. 对 gold-set 漏项逐项诊断术语、缩写、字段、来源或过滤条件；最小化修改检索式并保存每轮结果。
10. 按 A–F 六维模型评估并输出 `audit.md`、`audit.html`、`audit.json`（含 `indicator_register`）与输入快照，共 A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6 六维 21 子项；伞式综述额外启用 A4/C4/F7（共 24 子项）。

## 判断规则

- **A 覆盖**：A1/A2 只用稳定 ID 计算 Recall；A3 只报告完整多源去重后的候选下界。
- **B 饱和度**：以连续轮次的核心库增长率（GGR）、新增路径发现率（DRR）、路径完成和独立验证共同判断。
- **C 平衡**：先检查主题空白、主题 Top-share、CV、Gini、Shannon 与可选目标份额 TVD，再检查来源分布及主题—来源交叉依赖。
- **D 时效性**：检查来源检索日期、领域化近年文献比例、前沿检索证据与预印本/正式版关系。
- **E 学术影响/渠道信号**：报告 h-core 与 profile 配置的 Tier-1 覆盖；两者都不是总分或研究质量裁决。真正的研究质量评估应使用与研究设计匹配的批判性评价工具。
- **F 可用性**：检查可复跑查询、摘要、PDF/开放全文、去重/版本、决策追溯与更正核验。

所有结论标为：实测、估计、自动初筛、待人工核验或不可评估。估计或自动初筛不能单独形成阻断结论。

## 资源

- `references/intake-protocol.md`：统一输入状态机——从用户输入形态识别到 `run-config.json` 生成。
- `references/run-config-schema.json`：`run-config.json` 的 JSON Schema（v1.0）。
- `references/user-intake-template.md`：面向用户的输入模板与标准确认表。
- `references/user-standards-guide.md`：面向用户的标准说明书——每个子项的含义、意图、依据、可调整性和证据类型。
- `references/engineering-profiles.md`：工程领域路由、来源与问题框架。
- `references/dimension-model.md`：六维评估模型（A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6，共 21 子项；伞式综述额外启用 A4/C4/F7，共 24 子项）完整阐述。
- `references/indicator-dictionary.md`：21 个子项（+ 3 个伞式专用子项）的报告名称、含义、输入、计算/核验方法与边界；生成报告或解释指标前必须读取。
- `references/engineering-standards.md`：六维默认阈值与 profile 覆盖规则。
- `references/confirmation-template.md`：首次调用的四批次确认模板（必须拍板→默认策略→补充材料→合法性声明）。
- `references/context-schema.md`：`context.json` 输入规范与完整示例（字段→评估项映射）。
- `references/autonomous-run.md`：自主运行状态机、停止规则与诚实边界。
- `references/keywords.md`：工程检索式构建与 gold-set 迭代。
- `AI_GUIDE.md`：AI 执行细则（统一报告契约、不可违反规则、交付物）。
- `USER_GUIDE.md`：面向使用者的说明。
- `scripts/collect_open_sources.py`：开放源查询快照采集器。
- `scripts/normalize_candidates.py`：稳定标识符去重、冲突与版本族候选队列。
- `scripts/run_audit.py`：从规范化输入生成评估报告（`audit.md`/`audit.html`/`audit.json`）。
- `scripts/search_for_eval.py`：自主检索器——构造检索式并在线执行，产出 A2 的 query-hits、B 的首轮 search_rounds、潜在新增文献清单。

先运行脚本的 `--help` 并验证输入结构；脚本只负责可重复计算，领域判别、相关性初筛和集合构建必须记录理由与置信度。
