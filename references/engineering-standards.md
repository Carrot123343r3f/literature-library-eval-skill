# 默认阈值（模型 X，A1–A3、B1–B3、C1–C3、D1–D4、E1–E2、F1–F6，共 21 子项）

**所有阈值均为参考值，不代表文献库的真实质量；pass/warning/fail 是自动化诊断提示，具体判断需结合研究问题与领域惯例做人工裁决。**

首次确认后将默认值与 profile、综述类型和用户协议合并到 `context.standards`，并把最终采用值写入报告。

## 分层默认值

| 指标 | 叙事/范围综述 | 系统综述 | 快速综述 | 伞式综述 |
|---|---|---|---|---|
| `a1_min_recall`（A1 基准集召回） | **0.75** | 0.90 | 0.60 | 0.85 |
| `a2_min_recall`（A2 检索式灵敏度） | **0.70** | 0.85 | 0.55 | 0.80 |
| `f_access_rate`（F3 全文获取） | **0.60** | 0.80 | 0.50 | 0.75 |
| `f_provenance_rate`（F5 来源追溯） | **0.85** | 0.95 | 0.70 | 0.90 |
| `f_core_metadata_rate`（F 核心元数据） | **0.90** | 0.95 | 0.80 | 0.90 |
| `f_abstract_rate`（F2 摘要） | 0.80 | 0.85 | 0.70 | 0.80 |

以下指标与综述类型无关，采用统一默认值。`recency_years` / `recency_min_share` 保留 `null` 由 profile 动态推算：

```json
{
  "recency_years": null,
  "recency_min_share": null,
  "d_freshness_days": 90,
  "b_ggr_threshold": 0.02,
  "b_drr_threshold": 0.05,
  "balance_top_share_warning": 0.80,
  "balance_cv_warning": 1.00,
  "balance_gini_warning": 0.60,
  "balance_shannon_low_warning": 0.45,
  "balance_shannon_high_warning": 0.95,
  "topic_top_share_warning": 0.70,
  "topic_cv_warning": 0.80,
  "topic_gini_warning": 0.50,
  "topic_shannon_low_warning": 0.55,
  "topic_target_tvd_warning": 0.25,
  "topic_min_sources": 2,
  "topic_source_top_share_warning": 0.80
}
```

### 默认 `a1_min_recall` / `a2_min_recall`（叙事/范围综述）

| 指标 | 默认值 | 含义 |
|---|---|---|
| `a1_min_recall` | **0.75** | A1 基准集至少命中 75% 的 seminal 锚点——叙事综述允许少量边缘 seminal 未收录（如新兴子方向的代表），但 3/4 以上的核心工作应齐全 |
| `a2_min_recall` | **0.70** | 代表性检索式应能找回至少 70% 的 gold set——反映检索策略本身的覆盖能力，低于此值说明检索词或来源有盲区 |

### 默认 `f_access_rate`（F3 全文获取）

| 默认值 | 含义 |
|---|---|
| **0.60** | 叙事综述不需要逐篇全文核对（写综述时按需取阅即可），60% 的获取率为合理起点。系统综述需要更强证据支撑，设为 0.80 |

### 默认 `f_provenance_rate`（F5 来源追溯）

| 默认值 | 含义 |
|---|---|
| **0.85** | 85% 的文献能追溯到检索批次或来源即可复现大部分建库过程；系统综述需 95% 以上 |

### 默认 `f_core_metadata_rate`（F 核心元数据）

| 默认值 | 含义 |
|---|---|
| **0.90** | 标题、作者、年份、发表载体、标识符五项至少 90% 齐全。考虑到 AI/软件领域大量纯 arXiv 预印本（无正式 venue/DOI），不设 95% 以免过度惩罚正常现象 |

### 默认 `f_abstract_rate`（F2 摘要）

| 默认值 | 含义 |
|---|---|
| **0.80** | 至少 80% 条目有摘要以支撑自动初筛——低于此值时 C 和 E 维的自动评估可靠性下降 |

## profile 动态覆盖

| 领域 | `recency_years` | `recency_min_share` | `d_freshness_days` | 说明 |
|---|---|---|---|---|
| 计算机与 AI / 电子通信 | 3 | 0.40 | **30** | 技术迭代快，三年前论文可能已过时 |
| 机械 / 材料 / 化工 / 生医工 | 5 | 0.35 | 90 | 常规工程节奏 |
| 土木 / 能源 / 航空航天 / 交通 | 7 | 0.30 | **180** | 规范、标准、长期可靠性数据有长尾价值 |

## 诊断类指标阈值（仅警示，不阻断）

- `balance_*` / `topic_*`：来源与主题分布警戒线，基于 Shapiro 信息论经验值，超限仅示意检索偏倚风险
- `b_ggr_threshold` / `b_drr_threshold`：饱和度阈值——最后两轮 GGR<2% 且 DRR<5% 时为趋稳
- E 学术影响/渠道信号（h-core、Tier-1）：**不设硬阈值**，仅作诊断背景

## 阈值来源与调整原则

**来源**：阈值基于综合性指标参考与工程领域实际长期使用经验设定。GGR/DRR 阈值遵循检索饱和文献中的常用界限；A recall 阈值参考系统性综述方法对"完整检索"的定义；F 维阈值基于文献计量学元数据质量标准；C 维阈值基于 Shannon 信息论与 Gini 不均衡判据的经验共识。

**调整原则**：首次确认时将默认值与项目要求合并；数值为诚实经验值的尝试，语境中应把它理解为"区间中心"而非"机械及格线"。如有更好的领域特化证据可覆盖，不可绕过项目要求。报告中始终列出采用的具体阈值以便审查。
