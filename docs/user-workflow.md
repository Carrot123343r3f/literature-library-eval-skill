# 用户工作流：从文献库到可行动的审计结果

## 第一次使用

1. 导出你的文献库为 JSON、CSV、RIS 或 BibTeX。
2. 运行 `run_full_audit.py init`，只确认研究问题、综述类型、文献库位置和是否允许三类在线操作。
3. 运行 `run_full_audit.py run`。即使没有检索式、Gold 集或种子文献，也会生成 HTML 首轮报告。

首轮报告会显示全部指标，但会将缺少正式证据的项目明确标为
`not_assessable`。这不是失败，而是后续工作的最小清单。

## 看报告时先看什么

1. **执行摘要**：是否可开始初步写作、最主要的风险是什么。
2. **行动工作台**：每个缺口都有原因和最小补充步骤；勾选仅保存在本地浏览器，不会改变审计证据。
3. **21 项总表**：`measured` 是可复核实测；`estimated` / `screening` 是 AI 或规则初评；`not_assessable` 需要新证据。

## 人工筛选闭环

候选发现后，打开 `screening/screening-workbench.html`：

- 逐篇选择纳入、排除或待定；纳入/排除必须写理由。
- 下载 `screening-decisions.json` 或 CSV。
- 将下载的 JSON/CSV 传回 `screen_candidates.py --decisions` 验证。

只有已确认的人工纳入决定才能进入 B 饱和度指标。AI 候选、推荐分数和自动规则筛选都不能替代该决定。

## 联网、隐私与失败处理

联网默认关闭；元数据补齐、外部候选发现、引文追踪分别需要明确授权。密钥仅从预配置环境读取，不写入 run-config、报告、manifest 或输入快照。若在线操作失败，系统会保留已有库并给出可恢复的缺口，而不会伪造结果。

## 你应保存的文件

- `audit.html`：唯一面向用户的审计报告。
- `audit.json`、`manifest.json`、`inputs/`：复现、共享和后续 Agent 调用。
- `screening-decisions.json`：人工筛选依据。
- `next-actions.json`：机器可读的后续行动队列。
