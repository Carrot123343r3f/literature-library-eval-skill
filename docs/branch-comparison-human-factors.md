# `human-factors-schema-tests` 分支差异审查

审查日期：2026-07-28。此报告只做分支整理准备，不执行合并、重命名或删除。

## 当前结构

| 分支 | 与 `main` 的关系 | 定位 |
| --- | --- | --- |
| `main` | 稳定基线，`54c0ae1` | 正式基线 |
| `codex/harden-audit-contracts` | 领先 `main` 23 个提交，`a2d10dd` | 当前主开发/PR #2 |
| `human-factors-schema-tests` | 领先 `main` 10 个提交，`fe5b8c8` | 旧的平行实现路线 |

`main` 是两个分支的共同祖先；`human-factors-schema-tests` 与当前 Codex 分支没有可直接快进的关系。`git cherry -v codex/harden-audit-contracts human-factors-schema-tests` 显示其 10 个提交都不是当前分支已有的等价提交。

## 分支包含的内容

它的 10 个提交主要覆盖：

- 首次使用体验和配置校验；
- 检索策略说明与饱和度一致性；
- 报告隐私、可复现归档和用户流程；
- 自动生成临时 anchor、dev/validation 集的首轮评估管线；
- `evidence_isolation.py`、`stable_ids.py`、`build_anchor_candidates.py` 等旧路线组件。

## 独立价值判断

### 值得吸收的思想

1. **首次运行自动准备临时证据集**：没有 benchmark、Gold 或检索式时，先生成 `automated-screening` 级别的 provisional 证据，让用户能立即得到第一版诊断。
2. **证据隔离清单**：明确记录 dev、validation、A3、B2 的来源关系，避免把机械 holdout 误称为独立验证。
3. **稳定 ID 工具集中化**：统一 DOI、arXiv、PMID、OpenAlex ID 归一化。

这些思想已在当前路线中部分替代：当前已有架构内核、双库优化契约、多源检索、autopilot、自动预筛和 `evalset_audit.py`。剩余的“provisional 首轮证据集”可以作为后续增强点移植。

### 不建议整体合并的部分

该分支相对当前 Codex 分支会删除或替换大量文件，包括：

- 当前架构内核、优化模块、质量优化模块和纸面评估模块；
- 当前测试套件和 CI 配置；
- 当前 HTML-only 输出契约、归档脱敏和新的 Schema；
- 已加入仓库的 MCP 组件与示例资产。

它还包含较大的历史 `outputs/` 运行产物，不适合作为源代码合并。其 `run_initial_assessment.py` 依赖旧参数（如 `--ai-provisional`、`--allow-partial`、`--evidence-manifest`），与当前 `search_for_eval.py` 契约不兼容，直接 cherry-pick 会产生回归。

## 推荐删除方案

### 方案 A：归档后删除（推荐）

1. 在 `fe5b8c8` 创建归档 Tag，例如 `archive/human-factors-schema-tests-2026-07-28`；
2. 确认 GitHub 上没有未处理的 PR 或重要讨论；
3. 删除本地分支 `human-factors-schema-tests`；
4. 删除远程分支 `origin/human-factors-schema-tests`；
5. 保留归档 Tag，未来仍可恢复完整历史；
6. 后续将“首次运行 provisional evidence”思想在当前架构中重新实现，而不是合并旧分支。

### 方案 B：暂不删除

如果希望保留研究过程，可只把它标记为 archived/legacy，不再作为开发入口。这样不会改变代码，但 GitHub 分支列表仍会保留噪声。

## 最终建议

建议采用方案 A。该分支有思想价值，但没有足够的代码增量价值；整体合并风险明显高于收益。删除前只需确认是否存在未公开的重要 PR 或评论，之后可安全归档并删除。
