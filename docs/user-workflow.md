# 用户工作流：从文献库到可行动的审计结果

## 第一次使用

1. 导出你的文献库为 JSON、CSV、RIS 或 BibTeX。
2. 运行 `run_full_audit.py init`，第一轮只确认研究问题、工程范围和文献库位置；综述类型先使用 narrative 默认值。它默认完全本地运行；需要在线元数据补齐、外部候选发现或引文追踪时，再逐项明确授权。
3. 运行 `run_full_audit.py run`。如果缺少检索式、独立 Gold 集、人工筛选决定或独立检索路径，流程会交付 `sufficiency-precheck.html`，而不会生成空壳 A–F 报告。

预检查是一次成功交付但不是审计完成：其 JSON 中固定为
`audit_status: "not_started"` 和 `completion: "precheck_delivered"`。仅在
`audit/audit.html` 与 `audit/audit.json` 存在时，A–F 审计才算完成。

## 看报告时先看什么

1. **执行摘要**：是否可开始有限范围初稿、最主要的三个阻断缺口是什么。
2. **行动工作台**：每个缺口都有原因和最小补充步骤；勾选仅保存在本地浏览器，不会改变审计证据。
3. **21 项总表**：`measured` 是可复核实测；`estimated` / `screening` 是 AI 或规则初评；`not_assessable` 需要新证据。

## 人工筛选闭环

候选发现后，打开 `screening/screening-workbench.html`：

- 逐篇选择纳入、排除或待定；纳入/排除必须写理由。
- 下载 `screening-decisions.json` 或 CSV。
- 将下载的 JSON/CSV 传回 `screen_candidates.py --decisions` 验证。

只有已确认的人工纳入决定才能进入 B 饱和度指标。AI 候选、推荐分数和自动规则筛选都不能替代该决定。
每条声明为完成的独立检索路径还必须保存其 `candidate_ids` 与
`screened_candidate_ids`；两者都必须是检索命中的稳定标识符，并与人工
筛选决定逐一对应。重复路径 ID、重复路径类型或不完整的路径筛选覆盖都会
停在 precheck。

## 联网、隐私与失败处理

联网默认关闭；元数据补齐、外部候选发现、引文追踪分别需要明确授权。密钥仅从预配置环境读取，不写入 run-config、报告、manifest 或输入快照。若在线操作失败，系统会保留已有库并给出可恢复的缺口，而不会伪造结果。

## 你应保存的文件

- `sufficiency-precheck.html`、`sufficiency-precheck.json`：证据不足时的唯一交付；后者提供机器可判定状态和缺口。
- `audit/audit.html`：完整 A–F 审计的唯一面向用户报告。
- `audit/audit.json`、`audit/manifest.json`、`audit/inputs/`：完整审计的复现、共享和后续 Agent 调用。
- `screening-decisions.json`：人工筛选依据。
- `next-actions.json`：机器可读的后续行动队列。
