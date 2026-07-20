# Engineering Literature Library Audit

用于审计工程综述文献库的可用性与准备度。它评估证据是否足以支持一个已定义的工程研究问题，而不是为论文数量、引用量或期刊等级打一个“质量总分”。

## 适用范围

支持计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程。排除纯数学、纯物理、纯化学、临床医学和基础生命科学。

支持系统、范围、叙事、快速及伞式综述。任何“充分”“趋稳”结论都只在报告声明的问题、来源、时间和纳入标准内成立。

## 它审计什么

| 维度 | 核心问题 | 可接受结论 |
| --- | --- | --- |
| A 覆盖 | 已知必纳入工作与检索式是否被命中？ | A1 实测召回、A2 灵敏度、A3 多源覆盖下界/区间 |
| B 过程 | 检索是否在已声明范围内趋稳？ | 多条独立过程证据共同支持，或“未证明稳定” |
| C 结构 | 工程关键层、工况、方法和应用是否存在缺口？ | taxonomy 驱动的覆盖图与来源依赖描述 |
| D 适用性 | 证据是否匹配所需的工况、基线、指标与标准？ | 自动初筛与人工核验边界 |
| E 更新 | 检索是否新鲜，前沿窗口是否存在风险？ | 来源级成功检索日期与更新风险 |
| F 库健康 | 元数据、重复、版本、访问、追溯和更正状态是否可用？ | 可复跑的库健康清单 |

## 自动化边界

首次确认后，AI 会自主生成检索计划、执行可访问来源、迭代查询、筛选和生成审计包。自动化不会虚构订阅数据库访问、全文质量、撤稿状态或“全世界文献已收齐”。每项结论都会标注为实测、估计、自动初筛、待人工核验或不可评估。

开放源默认包括 OpenAlex、Crossref、Europe PMC 和 arXiv；采集器会记录分页是否完成，达到上限的来源只能形成“部分快照”。归一化器仅自动合并共享稳定标识符，标题相似和预印本—正式版关系会进入复核队列。工程订阅来源只在已有合法访问方式时使用。不要在提示词、报告或仓库中写入 API key。

## 文件结构

```text
literature-library-eval/
├── SKILL.md
├── AI_GUIDE.md
├── USER_GUIDE.md
├── README.md
├── agents/openai.yaml
├── references/
│   ├── engineering-profiles.md
│   ├── coverage-model.md
│   ├── noncoverage-model.md
│   ├── autonomous-run.md
│   └── keywords.md
├── scripts/
│   ├── collect_open_sources.py
│   ├── normalize_candidates.py
│   └── run_audit.py
├── tests/                 # A1/A2/A3 与报告的最小端到端测试
└── example-report.md
```

`compute.py` 是兼容性辅助脚本；新版正式审计入口是 `scripts/run_audit.py`。

## 使用

在 Codex/Claude 中直接说明，例如：

> 使用 literature-library-eval 审计我的工程文献库，判断它能否支持关于固态电池热管理的范围综述。

详细使用方式见 [USER_GUIDE.md](USER_GUIDE.md)，执行规则见 [AI_GUIDE.md](AI_GUIDE.md)。
