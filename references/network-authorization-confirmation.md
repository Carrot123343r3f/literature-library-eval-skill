# 网络与授权确认

这是文献评价流程的第一步，不在检索开始后再临时询问。

## 必须确认的五项

1. 默认不联网。只有用户明确授权后，AI 才能联网补齐元数据：DOI、作者、年份、引用数、FWCI、开放全文地址和主题。
2. 是否允许执行诊断检索与调词（`allow_query_refinement`）。它不扩展文献库。
3. 是否允许发现新的外部候选文章。它与调词和元数据补齐分开，默认不自动扩展候选库。
4. 是否允许引文追踪。它只产生未筛选候选。
5. 是否主动选择完全本地运行，并确认允许使用的网站/数据库及预配置合法连接器。

## 安全边界

- 不要求用户在对话中粘贴 API key、密码或 cookie。
- `run-config.json` 只记录来源名称和授权状态，不记录秘密。
- 联网结果必须保存来源、查询时间、匹配方式、匹配置信度和原始快照。
- 低置信度匹配不能覆盖用户已有字段；无法匹配时保留 `not_assessable`。

## 推荐配置语义

```json
{
  "automation": {
    "allow_search": true,
    "allow_metadata_enrichment": true,
    "allow_query_refinement": false,
    "allow_external_discovery": false,
    "allow_citation_tracking": false,
    "allowed_sources": ["openalex"],
    "authorized_sources": ["openalex"]
  }
}
```

`allow_search` 是在线操作的总开关；四项独立权限（元数据补齐、诊断检索/调词、外部候选发现、引文追踪）均默认 `false`，不能相互替代。完整映射以 `docs/execution-contract.md` 为准。完全本地运行时，应在用户确认后使用 `--offline`。

对于批量文献库，元数据补齐会在正式 A–F 审计前执行，并输出 `library-enriched.json`。如果来源暂时不可用，项目继续使用原始库并生成缺口报告。
