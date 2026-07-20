# A–F 工程默认阈值

首次确认后将默认值与 profile、综述类型和用户协议合并到 `context.standards`，并把最终采用值写入报告。

```json
{
  "b_min_records_per_critical_stratum": 1,
  "b_min_classification_confidence": 0.80,
  "b_max_unclassified_rate": 0.10,
  "b_source_dependence_warning": 0.80,
  "c_required_field_rate": 0.80,
  "d_freshness_days": 90,
  "e_citation_data_rate": 0.80,
  "f_new_rate_threshold": 0.02,
  "f_marginal_yield_threshold": 0.05,
  "f_core_metadata_rate": 0.95,
  "f_abstract_rate": 0.80,
  "f_access_rate": 0.80,
  "f_provenance_rate": 0.95,
  "balance_top_share_warning": 0.80,
  "balance_cv_warning": 1.00,
  "balance_gini_warning": 0.60,
  "balance_shannon_low_warning": 0.45,
  "balance_shannon_high_warning": 0.95
}
```

AI/软件、电子通信等快速领域推荐 `d_freshness_days=30`；航空航天、土木、能源基础设施可设为 `180`。系统综述可将 `b_min_records_per_critical_stratum=2`，并把 F1/F2/F4/F6/F8 设为阻断。
