# 证据集与 Subagent 隔离协议

本协议解决一个核心问题：不能用检索式自己发现的文献组成该检索式的独立验证集。

## 四个角色

| 角色 | 可以读取 | 不可以读取 | 产物 |
|---|---|---|---|
| Dataset Builder | 多源发现路径、综述、标准、引文网络 | 不应只用目标检索式 | seed/dev/validation/benchmark + manifest |
| Query Optimizer | 用户 q0、概念矩阵、dev 集 | validation 集及其反馈 | q0、q1…q* 与迭代日志 |
| Blind Evaluator | 冻结的 q0/q* 和 validation 集 | 优化过程中的 validation 反馈 | 最终 A2 validation 结果 |
| Audit Agent | manifest、日志和结果 | 不参与选文献或改检索式 | 独立性与泄漏检查 |

“不同 subagent”不是独立性的充分证明。共享目录、缓存、检索快照和对话转述都可能泄漏验证集。最低要求是：验证集冻结后，优化角色不能读取验证集文件或 validation recall。

## 数据集角色

- `seed`：用于拆解概念和构建 q0，可以参与检索式设计。
- `dev`：用于反复优化 q0 → q*，可以被多次使用。
- `validation`：用于最终 A2，只能在检索式冻结后读取。
- `benchmark`：用于 A1 的已知锚点覆盖，不自动等同于 A2 validation。
- `b3_validation`：用于检验检索过程是否完整，不能默认复用 A2 validation。

## 验证集获取

验证集不要求用户逐篇提供。Dataset Builder 可以从以下路径构建候选池：权威综述、标准/指南、后向引文、前向引文、相关文献网络、不同数据库和时间留出窗口。至少留出一条未用于 q* 优化的来源路径，并在 `evidence-manifest.json` 中记录 `source_routes`、`used_tested_query`、`used_for_query_optimization` 和 `frozen_at`。

如果验证集由目标检索式发现，或在调词过程中被查看，A2 必须降级为 `estimated`。如果没有来源留出和冻结记录，不能声称程序独立实测。

## 证据不复用规则

1. A3 的多源候选快照不能直接作为 B2 的新增纳入文献。
2. A2 validation 与 B3 validation 相同，B3 只能标为 `not_assessable`，不能证明饱和。
3. A3 快照与 B2 路径共享来源时，B2 标为 `not_assessable`，并报告证据重叠。
4. 发现候选未经筛选确认，不得进入 GGR/DRR 分子。

## 独立性等级

- `query_derived`：目标检索式直接产生，不可用于独立验证。
- `query_assisted`：目标检索式参与发现，A2 为 `estimated`。
- `procedurally_independent`：来源留出、冻结、未参与优化，可以作为程序独立实测。
- `externally_confirmed`：另有领域专家或权威外部清单确认。

程序独立不等于绝对完备。报告必须同时展示来源路径、冻结时间和剩余假设。
