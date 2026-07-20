# 工程审计默认配置

在一次性确认后，把以下默认值写入 `context.standards`；用户、综述协议或 profile 可覆盖。不要跨项目偷偷沿用已覆盖的值。

```json
{
  "b_new_rate_threshold": 0.02,
  "b_marginal_yield_threshold": 0.05,
  "c_min_records_per_critical_stratum": 1,
  "c_min_classification_confidence": 0.80,
  "c_max_unclassified_rate": 0.10,
  "c_source_dependence_warning": 0.80,
  "d_required_field_rate": 0.80,
  "e_freshness_days": 90,
  "f_core_metadata_rate": 0.95,
  "f_abstract_rate": 0.80,
  "f_access_rate": 0.80,
  "f_provenance_rate": 0.95
}
```

推荐覆盖：AI/软件、电子通信等快速领域将 `e_freshness_days` 设为 30；航空航天、土木、能源基础设施等慢变领域可设为 180。系统综述可把 `c_min_records_per_critical_stratum` 提升为 2，并将 F2/F3/F5/F6 设为阻断。
