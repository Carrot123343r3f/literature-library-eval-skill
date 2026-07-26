# 网络与授权确认

这是文献评价流程的第一步，不在检索开始后再临时询问。

## 必须确认的四项

1. 默认允许 AI 联网补齐元数据：DOI、作者、年份、引用数、FWCI、开放全文地址和主题。
2. 是否允许发现新的外部候选文章。它与元数据补齐分开，默认不自动扩展候选库。
3. 是否主动选择完全本地运行。只有用户明确选择后，才使用 `--offline`。
4. 允许使用哪些网站/数据库，以及是否存在合法的预配置登录会话、连接器或环境凭据。

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
    "allow_external_discovery": false,
    "allowed_sources": ["openalex"],
    "authorized_sources": ["openalex"]
  }
}
```

`allow_search` 表示允许已授权的在线操作；`allow_metadata_enrichment` 控制字段补齐；`allow_external_discovery` 控制是否扩展候选文章。完全本地运行时，应在用户确认后使用 `--offline`，而不是静默降级。

对于批量文献库，元数据补齐会在正式 A–F 审计前执行，并输出 `library-enriched.json`。如果来源暂时不可用，项目继续使用原始库并生成缺口报告。
