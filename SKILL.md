---
name: literature-library-eval
description: 评估工程研究综述的文献库是否足以支持既定问题、范围与综述类型。适用于计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程；不适用于纯数学、纯物理、纯化学、临床医学或基础生命科学。使用于用户要求评估工程文献库、检验检索充分性/覆盖/趋稳、判断 Zotero 或结构化题录库能否支撑综述，或需要生成可复现的文献库准备度评估时。持系统、范围、叙事、快速与伞式综述。不会自动替人决定"库是否合格"——自动结果始终与你的人工判断配合使用。首次使用只需说出题目或提供库位置，AI 会用最少问题补全必要信息，不需要你理解 JSON schema 或文献计量术语。
---

本文件是 `SKILL.md` 的兼容性别名，实际入口为 `SKILL.md`（大写）。
所有 AI 和其他工具应读取 `SKILL.md` 作为唯一流程入口。

## Resources

| Resource | Purpose |
|---|---|
| `references/intake-protocol.md` | 用户交互状态机（S0→S2→S3） |
| `schemas/run-config-schema.json` | run-config.json v1.0 schema |
| `schemas/indicator-registry.json` | **指标权威注册表**——所有 21+3 子项的单一定义源 |
| `references/search-strategy-protocol.md` | **检索策略协议**（子技能）——PICO 分解、dev/val 分离、原子迭代、独立路径、多源异构语法、停止条件分离 |
| `references/dimension-model.md` | A–F 六维模型方法论阐述 |
| `docs/methodology.md` | 方法论全文——设计依据、边界、局限 |
| `docs/architecture.md` | 流水线架构、数据契约、扩展点 |
| `docs/outputs.md` | 审计报告解读——每节含义、证据状态、判决意义 |
| `docs/integrations.md` | Zotero、数据库、配套 skill 协作方式 |
| `references/engineering-standards.md` | 默认阈值（按综述类型+profile） |
| `references/indicator-dictionary.md` | 21+3 子项快速参考 |
| `references/engineering-profiles.md` | 9 工程领域 profile + tempo 偏好 |
| `references/user-standards-guide.md` | 用户标准说明书 |
| `scripts/run_audit.py` | 诊断报告生成器 |
| `scripts/search_for_eval.py` | 单轮诊断性检索（支持 --dev-set/--validation-set/--pico） |
| `scripts/search_iterator.py` | 检索迭代合规验证 + 比较表生成 |
| `README.zh-CN.md` | 中文入口——项目故事、快速开始、能力边界 |
