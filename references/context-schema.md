# context.json 输入规范

`scripts/run_audit.py --context context.json` 读取此文件。agent 在执行评估时把确认结果（见 `confirmation-template.md`）与执行决策写入对应字段。报告的"评估方法与过程"段从这些字段读取，把 agent 的隐式工作显式化。

## 完整示例

```json
{
  "review_type": "范围综述",
  "profile": "计算机与 AI",
  "scope": "2020–2026，英文",
  "year_start": 2020,
  "year_end": 2026,
  "library_name": "Zotero 20959985 / 本地 BibTeX 导出",

  "keywords": ["visual defect detection", "cross-line deployment", "surface inspection", "transfer learning"],
  "queries": [
    {"source": "OpenAlex", "query": "\"defect detection\" AND (\"production line\" OR transfer)", "date": "2026-07-18", "hits": 2143},
    {"source": "IEEE Xplore", "query": "(\"visual inspection\" OR \"surface defect\") AND cross-line", "date": "2026-07-19", "hits": 876}
  ],

  "benchmark_method": "库内 3 篇权威 survey 参考文献求共引交集，取被 ≥2 篇共同引用且 cited_by 排序 top-48，用 DOI + title 归一化匹配库",
  "benchmark_source": "库内 01-奠基夹 survey + 领域高被引锚点",
  "benchmark_note": "用户另提供 6 篇必纳入种子并入基准集",
  "gold_set_method": "A1 基准集 + 用户 6 篇种子，去重后 52 篇",

  "search_sources": ["OpenAlex", "Crossref", "IEEE Xplore", "DBLP"],
  "planned_sources": ["OpenAlex", "Crossref", "IEEE Xplore", "DBLP"],
  "failed_sources": ["Semantic Scholar（无 key 限速）"],

  "last_successful_search": {"openalex": "2026-07-18", "crossref": "2026-07-19", "ieee": "2026-07-19", "dblp": "2026-07-17"},

  "search_rounds": [
    {"pathway": "database", "completed": true, "core_before": 100, "included_high": 3},
    {"pathway": "database", "completed": true, "core_before": 103, "included_high": 1},
    {"pathway": "backward", "completed": true, "core_before": 104, "included_high": 1}
  ],
  "planned_pathways": ["database", "backward", "forward"],
  "source_marginal_yields": [{"yield": 0.02}, {"yield": 0.01}],
  "independent_validation_passed": true,
  "run_log_complete": true,

  "taxonomy": [
    {"name": "低照度", "expected": true, "high_confidence_records": 0, "classification_confidence": 0.85, "target_share": 0.15},
    {"name": "跨产线迁移", "expected": true, "high_confidence_records": 42, "classification_confidence": 0.92},
    {"name": "实时性", "expected": true, "high_confidence_records": 31, "classification_confidence": 0.88}
  ],
  "topic_source_counts": {
    "低照度": {"openalex": 0, "ieee": 0},
    "跨产线迁移": {"openalex": 20, "ieee": 15, "dblp": 7}
  },
  "viewpoint_framework": {
    "claim": "跨产线迁移学习能在目标场景稳定提升缺陷检测泛化性",
    "contested": true,
    "counts": {"supports_claim": 31, "challenges_claim": 6, "mixed_or_conditional": 10, "unclassified": 5},
    "records_assessed": 52,
    "classification_method": "AI 根据题名与摘要按预先声明的主张分类",
    "sample_verified": 12
  },

  "tier1_venues": ["cvpr", "iccv", "eccv", "tpami", "ijcv", "neurips", "icml", "iclr", "aaai", "wacv"],
  "frontier_coverage_verdict": "not_assessable",
  "version_currency_verdict": "not_assessable",

  "standards": {
    "a1_min_recall": 0.85,
    "a2_min_recall": 0.80,
    "b_ggr_threshold": 0.02,
    "b_drr_threshold": 0.05,
    "d_freshness_days": 30
  }
}
```

## 字段与评估项的对应

| context 字段 | 喂给哪个评估项 | 必需性 |
|---|---|---|
| `taxonomy[].high_confidence_records` | C1 主题平衡 | C 维必需 |
| `taxonomy[].target_share` | C1 TVD（可选） | 可选 |
| `topic_source_counts` | C3 主题-来源交叉 | 可选，缺失则 C3 标 not_assessable |
| `viewpoint_framework` | C4 观点偏斜度 | 推荐；须包含中心主张、`records_assessed` 和支持/质疑/条件性计数。缺失时 C4 直接警示“未建立可审计分类”，而非从泛化情绪词臆测立场。 |
| `search_rounds`（≥2 轮，含 `core_before`/`included_high`） | B1 GGR | B 维必需 |
| `planned_pathways` + rounds 的 `completed`/`pathway` | B3 路径完成 | B 维必需 |
| `source_marginal_yields[]`（含 `pathway`/`candidates`/`screened_high_confidence`/`new_high_confidence`/`dedup_rule`/`yield`） | B2 DRR | B 维必需；原始字段供第三方从 query-hits.json 复算 |
| `independent_validation_passed` | B3 独立验证 | B 维必需 |
| `last_successful_search` | D1 来源新鲜度 | D 维必需 |
| `profile`（可控 ID：computer_ai / electronics_communications / mechanical_manufacturing / materials_chemical / biomedical_engineering / civil_infrastructure / energy_environment / aerospace_transportation；text 回退保留兼容） | D1/D2 窗口 | 推荐用可控 ID |
| `classification_method` / `classification_sample_verified` | C1 方法透明 | 可选；标注分类计数来源与抽查校验 |
| `tier1_venues` | E2 Tier-1 覆盖 | E 维必需，缺失则 not_assessable |
| `frontier_coverage_verdict` / `version_currency_verdict` | D3 / D4 | 可选，默认 not_assessable |
| `run_log_complete` | F1 检索可复跑 | 可选；传入 `--run-log` 文件则自动核验 |
| `standards.*` | 各项阈值 | 可选，缺省走 `engineering-standards.md` 默认 |
| `writing_workset` | 叙事综述的写作可用性建议 | 可选；`{core_count, role_counts, fields_confirmed}`。不参与 A–F 评分，也不替代完整库。 |
| `anchor_discovery_query` | 首轮候选锚点发现 | 可选；未提供用户检索式时可与 `keywords` 一起生成候选锚点。 |

## 其他输入文件

除 `context.json` 外，`run_audit.py` 还接收：

- `--library`（必需）：题录数组，每项含 `title`/`DOI`/`date`/`source`/`cited_by_count`/`publicationTitle` 等
- `--benchmark`（A1）：已审查、来源可追溯且已冻结的基准集，每项含稳定标识符（DOI/OpenAlex/arXiv/PMID/PMCID）
- `scripts/build_anchor_candidates.py`：用户未提供锚点时的候选发现；候选未审查前不能作为 A1 基准集
- `--gold` + `--query-hits`（A2）：Gold set 与已执行的检索命中快照
- `--candidate-snapshots`（A3）：采集器输出的多源快照（`collect_open_sources.py` 生成）

未提供的输入 → 对应评估项标 `not_assessable`，报告如实说明缺失，不用替代数字伪装。
