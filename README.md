# Engineering Literature Library Audit

## 统一输出契约

`audit.md` 的唯一主评估表必须逐行列出 A1–A3、B1–B3、C1–C3、D1–D4、E1–E2 与 F1–F6；不得把 A 作为主表、把 B–F 放入附录。表列固定为：维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。`audit.json` 以同一顺序提供 `indicator_register`，供机器复用。无阈值、无可复跑证据或当前不支持自动判断的项目必须写作 `not_assessable`，不能暗示通过或不合格。

所有子项的易读名称、评估含义、输入与计算/核验方法见 [指标字典](references/indicator-dictionary.md)。

用于评估工程综述文献库的可用性与准备度。它评估证据是否足以支持一个已定义的工程研究问题，而不是为论文数量、引用量或期刊等级打一个“质量总分”。

## 适用范围

支持计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程。排除纯数学、纯物理、纯化学、临床医学和基础生命科学。

支持系统、范围、叙事、快速及伞式综述。任何“充分”“趋稳”结论都只在报告声明的问题、来源、时间和纳入标准内成立。

## 它评估什么

| 维度 | 核心问题 | 可接受结论 |
| --- | --- | --- |
| A 覆盖 | 已知必纳入工作与检索式是否被命中？ | A1 实测召回、A2 灵敏度、A3 多源覆盖下界/区间 |
| B 检索是否趋于饱和 | 继续增加检索轮次或路径是否还会找到核心文献？ | GGR、DRR、路径完成与独立验证 |
| C 主题与来源分布是否失衡 | 主题是否有空白或严重偏斜，且每个主题是否只靠单一来源？ | 主题/来源 Top share、CV、Gini、Shannon、TVD、主题—来源交叉表 |
| D 库是否反映当前研究状态 | 检索是否新、近年比例是否足够、前沿与版本是否被核验？ | 来源新鲜度、Recency、前沿、预印本/版本 |
| E 库是否包含足够的学术影响 | 是否具备可解释的引用核心与领域优质渠道覆盖？ | h-core、profile 的 Tier-1 映射 |
| F 文献是否真正可用于写综述 | 是否有摘要、全文、干净题录和可追溯过程？ | 查询、摘要、PDF、去重、谱系、更正 |

六个维度共 21 个子项；详细定义、公式和警示规则在 `references/indicator-dictionary.md`，默认阈值在 `references/engineering-standards.md`。

## 自动化边界

首次确认后，AI 会自主生成检索计划、执行可访问来源、迭代查询、筛选和生成评估包。自动化不会虚构订阅数据库访问、全文质量、撤稿状态或“全世界文献已收齐”。每项结论都会标注为实测、估计、自动初筛、待人工核验或不可评估。

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
│   ├── dimension-model.md
│   ├── indicator-dictionary.md
│   ├── engineering-standards.md
│   ├── confirmation-template.md
│   ├── context-schema.md
│   ├── autonomous-run.md
│   ├── keywords.md
│   ├── review-types.md
│   └── data-sources.md
├── scripts/
│   ├── collect_open_sources.py
│   ├── normalize_candidates.py
│   ├── run_audit.py
│   └── search_for_eval.py  # 自主检索：A2 query-hits + B 首轮 search_rounds + 潜在新增
├── tests/                 # A1/A2/A3 与报告的最小端到端测试
├── compute.py             # 兼容性辅助脚本：A1 检查 + 题录健康（正式入口见 scripts/run_audit.py）
└── example-report.md
```

## 使用

在 Codex/Claude 中直接说明，例如：

> 使用 literature-library-eval 评估我的工程文献库，判断它能否支持关于固态电池热管理的范围综述。

详细使用方式见 [USER_GUIDE.md](USER_GUIDE.md)，执行规则见 [AI_GUIDE.md](AI_GUIDE.md)。
