---
name: literature-library-eval
description: 评估工程研究综述的文献库是否足以支持既定问题、范围与综述类型。适用于计算机与 AI、电子通信、机械制造、土木建筑、材料工程、能源、环境工程、化工过程、航空航天、交通与生物医学工程；不适用于纯数学、纯物理、纯化学、临床医学或基础生命科学。使用于用户要求评估工程文献库、检验检索充分性/覆盖/趋稳、判断 Zotero 或结构化题录库能否支撑综述，或需要生成可复现的文献库准备度评估时。持系统、范围、叙事、快速与伞式综述。不会自动替人决定"库是否合格"——自动结果始终与你的人工判断配合使用。首次使用只需说出题目或提供库位置，AI 会用最少问题补全必要信息，不需要你理解 JSON schema 或文献计量术语。
---

# 文献库评估 Skill

## 核心流程

以本文件为唯一流程入口。仅处理工程研究问题；纯基础学科或临床问题必须说明超出范围。完整规则见 `AI_GUIDE.md`，标准说明书见 `references/`。

### 首次调用：按 `references/intake-protocol.md` 状态机执行

1. **S0 识别用户输入形态**（只给题目 / 给文献库 / 说"评估我的库" / 超出范围等 8 种入口）
2. **S2 范围路由** — 写入 `run-config.json.scope_status`（in_scope / cross_domain / out_of_scope / scope_uncertain）。`out_of_scope` → 停止 A-F；`cross_domain` → 适用部分完整评估
3. **S3 最小必要确认** — 必须确认：研究问题、综述类型、库位置、时间语言边界、自动检索授权、输出格式
4. **三层标准确认** — 默认/调整/自定义/仅数据，四选一
5. 确认后输出 `run-config.json`，后续流程只读此配置

### A2/B 的自主检索

若用户未提供 `--query-hits`（A2）或无两轮 `search_rounds`（B），必须遵循 `references/search-strategy-protocol.md`：

```
S3 确认 → SRCH-1 工程 PICO 分解 → SRCH-2 构建开发集+验证集
→ SRCH-3 构建概念矩阵 → SRCH-4 初始检索式(v1) → SRCH-5 原子迭代循环
→ SRCH-6 独立路径执行 → SRCH-7 汇总
```

## 不可违反的规则

1. **A1/A2 只匹配稳定标识符**（DOI/arXiv/PMID/OpenAlex ID）；标题相似仅进人工核验队列。`search_for_eval.py` 的标题候选绝不计入 A2 分子。
2. **空查询结果的 A2 是实测召回 0**；没有执行查询才是不可评估。
3. **A3 需要多源、去重、明确边界与假设**。单源 count 不得叫覆盖率或 Recall。
4. **B 饱和度的趋稳结论需要独立验证、两轮低新增率、路径完成和低边际收益同时成立**。`search_for_eval.py` 的 discovery candidates 不等于纳入项——只有筛选确认后的文献才能进入 GGR/DRR 分子。F1 查询可追溯需 run log 结构有效（至少含 source/query/date 字段）。
5. **C 的主题与来源平衡使用 CV、Gini、归一化 Shannon 做诊断；E 的 h-core 和 Tier-1 仅作背景信号，不等于研究质量裁决**。
6. **不把 API key、令牌、绝对本地路径、受限全文写入输出**。

## 统一报告契约

将全部 21 子项（伞式 24 项）写入同一张六维评估总表；每行必须有维度、编号、评估项、标准、判定、当前值、证据状态、说明与行动。`not_assessable` 是有效结果，必须保留并说明缺失输入或核验路径。报告按以下顺序组织：基本信息 → 本次评估输入与证据状态 → 评估方法与过程 → A-F 六维评估总表 → 各维度分析 → 改进建议 → 局限与声明。

## 交付物

`run_audit.py` 输出 `out/` 目录含：`audit.md`、`audit.html`、`audit.json`（含 `indicator_register`）、`manifest.json`、`inputs/`（含 sha256 哈希）。

## 与脚本的关系

- `scripts/run_audit.py` — A–F 计算 + 报告生成（主入口）
- `scripts/search_for_eval.py` — 单轮 OpenAlex 诊断检索
- `scripts/search_iterator.py` — 多轮原子迭代验证
- `scripts/collect_open_sources.py` — 多源快照收集
- `scripts/normalize_candidates.py` — 去重 + 版本族识别
- `scripts/validate_registry.py` — registry 一致性校验
- `compute.py` — 兼容性包装器（仅 A1 + 库健康，**勿用作主入口**）
