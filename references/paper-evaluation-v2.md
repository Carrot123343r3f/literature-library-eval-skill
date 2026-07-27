# 单篇文献证据评价 V2

## 目的与边界

本模块用于“优先精读”“核心证据骨架”和“建议补库候选”三种不同决策；不输出跨研究设计通用的文章质量总分。资格、研究方法、可复核性、学术完整性、影响信号和库内边际贡献必须分开记录。

## 依据

- Cochrane Handbook Chapter 3：综述资格条件应从预先定义的问题、PICO 和研究设计推出；见 <https://training.cochrane.org/handbook/current/chapter-03>。
- PRISMA 2020：筛选过程、自动化工具和排除理由应透明记录；见 <https://www.bmj.com/content/bmj/372/bmj.n71.full.pdf>。
- RoB 2 与 ROBINS-I：研究质量评价应按研究设计、偏倚域和信号问题开展；见 <https://www.bmj.com/content/366/bmj.l4898.short> 和 <https://www.bmj.com/content/355/bmj.i4919>。
- Ivarsson & Gorschek：工程/软件研究的严谨性与工业相关性是不同维度；见 <https://www.researchgate.net/publication/220277895_A_method_for_evaluating_rigor_and_industrial_relevance_of_technology_evaluations>。
- DORA 与 Leiden Manifesto：期刊指标、原始引用数不能替代单篇文章质量；见 <https://sfdora.org/read/> 和 <https://www.nature.com/articles/520429a>。
- TOP、FAIR、NeurIPS 和 ACM artifact 评审：数据、代码、材料和可运行工件是可复核性证据，而不是结论正确性的替代；见 <https://pmc.ncbi.nlm.nih.gov/articles/PMC4550299/>、<https://doi.org/10.1038/sdata.2016.18>、<https://www.jmlr.org/papers/v22/20-303.html>、<https://www.acm.org/publications/policies/artifact-review-and-badging-current>。
- OpenAlex：外部候选只能代表已授权数据源与已记录检索范围；字段-年份归一化信号优先于原始引文；见 <https://developers.openalex.org/api-reference/works/get-a-single-work>。

## 输入

`context.paper_evaluation_scope` 可定义 `object`、`technology`、`performance` 和 `context`。题录可选字段包括 `study_type`、`topics`、`evidence_roles`、`method_appraisal`、`code_url`、`data_url`、`citation_normalized_percentile`、`fwci`、`retracted` 和 `corrected`。

也可将范围写入 `run-config.json.paper_evaluation.scope`；当 context 未指定时，运行器以该持久化配置为准。成功运行会输出 `paper-evaluation.html`、`paper-evaluation.json`、`external-search-snapshot.json` 与 `manifest.json`。manifest 仅保存输入文件名、哈希、脱敏副本和步骤状态，不保存绝对路径或密钥。

## 研究类型路由

支持 algorithm_ml、system_software、hardware_materials、field_observational、benchmark_dataset、review_guideline 与 qualitative_mixed。每一类都有独立的必查项；未提供全文级检查时方法学结果为 `not_assessable`。

## 输出约束

- `metadata_priority` 只能指导阅读顺序，不能称作高质量。
- 外部文献统一标记为 `candidate_discovery`，未筛选前不能计入正式文献库或 B 饱和度。
- 无授权、无 API key、联网失败或无法保存快照时，外部检索硬错误，写入 `paper-evaluation-error.json`。
- OpenAlex key 仅从已配置的 `OPENALEX_API_KEY` 环境变量读取，绝不在对话、报告或日志中索取/输出。
