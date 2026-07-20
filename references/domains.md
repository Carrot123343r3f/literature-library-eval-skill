# 领域适配（references）

> 让 skill 跨领域适用。各领域的数据库/锚点/benchmark/seminal 构建法 + 关键词协议。

## 通用流程（所有领域）

1. 定领域 → 选数据库 + 锚点论文 + benchmark 来源
2. 构建关键词（锚定→扩展→分解→去噪→gold-standard 验证）
3. 算全域 count（数据库 API）

## 计算机科学 / AI（CS）

- **数据库**：OpenAlex（综合）、arXiv（预印本）、DBLP（会议正式版）、Semantic Scholar
- **全域 count**：OpenAlex `filter=cites:{锚点WID}&search={关键词}`
- **锚点论文**：领域奠基论文（如 3DGS 的 Kerbl 2023）
- **benchmark**：领域权威 survey 的参考文献（Semantic Scholar `references` API）
- **Tier-1**：CCF-A 类会议（CVPR/ICCV/ECCV/NeurIPS/ICML/SIGGRAPH）+ 中科院一区期刊（TOG/TPAMI）
- **关键词**：英文为主；含缩写（3DGS/GS）+ 上位词（radiance field）

## 医学 / 健康科学

- **数据库**：**PubMed/MEDLINE**（核心）、Cochrane CENTRAL（临床试验）、Embase
- **全域 count**：PubMed E-utilities `esearch.fcgi?db=pubmed&term={关键词}` 返回 count
- **锚点论文**：里程碑 RCT 或指南（如某干预的首篇大样本 RCT）
- **benchmark**：Cochrane review 的纳入研究；或 GRADE 评级相关
- **Tier-1**：中科院一区医学期刊 + Lancet/NEJM/JAMA 等顶级综合刊
- **关键词**：MeSH 主题词（PubMed 医学主题词表）+ PICO 框架（Population/Intervention/Comparator/Outcome）
- **特有**：RCT 偏倚评估（Cochrane RoB 2）超出本 skill

## 社会科学

- **数据库**：**Web of Science**（核心）、Scopus、PsycINFO（心理）、Sociological Abstracts
- **全域 count**：WoS/Scopus API（需订阅 key）
- **锚点论文**：理论奠基或经典实证
- **benchmark**：Annual Review 系列的参考文献
- **Tier-1**：领域顶刊（SSCI 一区）
- **关键词**：概念分解（理论词 + 方法词 + 人群词）；注意同义/多语

## 人文 / 历史

- **数据库**：JSTOR、Project MUSE、Historical Abstracts
- **特有**：非实证为主，h-core/Recency 含义弱；更重代表性+权威
- **建议**：按叙事综述判据，弱化量化指标

## 工程 / 应用科学

- **数据库**：IEEE Xplore、Scopus、Web of Science
- **关键词**：技术术语 + 标准号 + 应用领域

## 关键词构建协议（所有领域通用）

1. **锚定核心术语**：奠基论文标题/权威 survey 用词
2. **同义词扩展**：缩写、多语言、上位词、下位词
3. **子方向分解**：按体系 C 维度拆方向词
4. **去噪词**：排除同名异义（如"苹果"水果 vs 公司）
5. **Gold-standard 验证**：用 10–20 篇 seminal 反测命中率，<100% 则扩展

> 领域不同，"seminal""benchmark""Tier-1"的具体内容不同，但**构建方法通用**。AI 评估时先识别领域 → 套对应数据库/锚点/词汇。

## 领域识别（AI 自动）

从库的 venue / 标题 / 摘要识别领域：
- 含 CVPR/ICCV/arXiv cs.X → CS
- 含 PubMed/PMID/MeSH/临床词 → 医学
- 含 SSCI/PsycINFO/理论词 → 社科
- 识别后告诉用户"推断为X领域，用Y数据库"，确认后采数。
