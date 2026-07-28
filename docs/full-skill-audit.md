# Skill 全流程审计记录

审计范围：入口协议、`run-config` 契约、范围路由、A–F 评估、外部检索、候选筛选、优化模块、输出归档、恢复执行和文档/示例一致性。审计日期：2026-07-28。

## 致命 Bug（已修复）

| 问题 | 风险 | 修改方案与结果 |
| --- | --- | --- |
| `scope_uncertain` 可继续进入完整评估 | 在范围未确认时产生伪精确结论 | `run_audit.py` 现在直接拒绝；必须补充范围或走明确的降级服务。 |
| `out_of_scope` 可通过 CLI 覆盖开关进入 A–F | 绕过不可变范围规则 | 删除 `--allow-out-of-scope` 及其覆盖路径；测试验证命令行伪造也失败。 |
| 已授权配置可同时声明 `local_only_confirmed` 与联网权限 | 离线承诺与实际行为冲突 | 共享契约拒绝矛盾组合，并拒绝未开启搜索却开启联网子权限。 |
| 配置未知字段和 Markdown 输出未被统一拒绝 | 下游忽略字段、产出格式越权或失去可复现性 | 代码契约和 `run-config-schema.json` 同时启用白名单/`additionalProperties:false`；持久化人类报告固定为 HTML。 |
| JSON 输入归档可能原样复制提示词、密钥或敏感字段 | 归档泄露和提示注入传播 | JSON 归档先公共字段脱敏；不可解析 JSON 与非 JSON 只保存哈希，不复制原文。 |
| 外部文本未明确标记为不可信数据 | 论文元数据、摘要或检索式可能伪装成指令 | 在 Skill 合约中加入不可信输入规则；HTML 渲染继续统一转义。 |
| 优化历史和反例文件使用普通 append | 并发/中断时可能产生半行，破坏决策历史 | 统一使用原子 JSONL 追加；迭代 ID 和反例 ID 做安全校验。 |

## 功能优化（已修复）

| 问题 | 修改方案 |
| --- | --- |
| 搜索迭代器将负向回退误判为 A2 平台期 | 平台期要求增量为 `0 <= delta < 0.03`，回退不再触发停止。 |
| 搜索迭代器对 primitive、非对象 iteration/results 易抛 traceback | 增加结构校验，CLI 返回可读错误。 |
| 审计输入的 `items`、snapshot 查询和 source 结果结构不稳 | 增加数组/对象边界检查，异常输入统一失败而非静默误算。 |
| 外部授权模块绕过完整 v1 配置契约 | 对带 `schema_version` 的配置调用共享验证器；旧版最小本地 fixture 保留兼容适配。 |
| 外部 API 响应体无上限 | 增加 20 MiB 安全上限，避免异常响应造成资源消耗。 |
| 纸面评估与主流程的 v1 配置契约不一致 | v1 配置进入共享验证；历史无版本 fixture 仅保留显式 legacy adapter。 |
| 示例仍声明 `audit.md`/`formats: md` | 示例、索引和文档统一为 `audit.html` + `audit.json`。 |

## 文本精简与契约澄清（已修复）

- 将输出、范围、双库分离、架构内核和恢复语义集中写入 `docs/contracts.md`、`docs/architecture.md` 与 `docs/outputs.md`。
- 删除会暗示 Markdown 为正式报告的示例描述；保留 Markdown 只作为内部渲染中间表示。
- 将“不确定范围”“跨领域降级”“候选发现不等于正式纳入文库”“validation 不得进入优化库”等边界写成可执行规则。

## 验证结果

- `python -m pytest -q`：全量通过。
- `python scripts/check_consistency.py --strict`：应作为发布前一致性门禁。
- 额外反例覆盖：未知配置字段、非法输出格式、权限冲突、相对库路径、大小写 DOI、畸形 snapshot、HTML 注入字符串、JSON 归档泄露。

## 未自动改变的有意边界

跨领域项目不会把“不适用维度”擅自填成零分；报告写入 `scope_routing.cross_domain_manual_routing` 并增加限制说明，要求人工标注适用性后再解释整体结论。这是防止自动化制造假精度的保守策略。
