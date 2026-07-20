# Engineering Literature Library Audit

## 统一输出契约

`audit.md` 的唯一主审计表必须逐行列出 A1–A4、B1–B5、C1–C6、D1–D5、E1–E5 与 F1–F8；不得把 A 作为主表、把 B–F 放入附录。表列固定为：母项目、子项目、项目名称、标准、是否达标、当前状态、证据状态、说明与行动。`audit.json` 以同一顺序提供 `indicator_register`，供机器复用。无阈值、无可复跑证据或当前不支持自动判断的项目必须写作 `not_assessable`，不能暗示通过或不合格。

所有子项的易读名称、审计含义、输入与计算/核验方法见 [指标字典](references/indicator-dictionary.md)。

用于审计工程综述文献库的可用性与准备度。它评估证据是否足以支持一个已定义的工程研究问题，而不是为论文数量、引用量或期刊等级打一个“质量总分”。

## 适用范围

支持计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程。排除纯数学、纯物理、纯化学、临床医学和基础生命科学。

支持系统、范围、叙事、快速及伞式综述。任何“充分”“趋稳”结论都只在报告声明的问题、来源、时间和纳入标准内成立。

## 它审计什么

| 维度 | 核心问题 | 可接受结论 |
| --- | --- | --- |
| A 覆盖 | 已知必纳入工作与检索式是否被命中？ | A1 实测召回、A2 灵敏度、A3 多源覆盖下界/区间 |
| B 范围结构 | 工程关键层、工况、方法和应用是否存在缺口？ | taxonomy、分层覆盖与结构集中度 |
| C 证据适用性 | 证据是否匹配所需的工况、基线、指标、标准与验证？ | 工程证据卡与人工核验边界 |
| D 时效与演化 | 检索、版本和前沿窗口是否足够新？ | 来源级新鲜度、前沿与版本时效 |
| E 影响与关联 | 是否连接关键工作、知识路径和影响力上下文？ | 引用数据、知识路径、渠道与权威锚点 |
| F 过程与可复现性 | 查询、路径、趋稳、去重、版本、追溯和更正是否规范？ | 可复跑过程与库健康清单 |

每个 B–F 维度均有细分标准与定位动作，例如 B1–B5、C1–C5、D1–D6、E1–E4 和 F1–F6。默认工程阈值在 `references/engineering-standards.md`；运行时会连同项目覆盖值写入报告，而不是只输出模糊总评。

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
