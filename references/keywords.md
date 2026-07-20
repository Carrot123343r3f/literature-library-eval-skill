# 关键词搜索优化（references）

> 关键词决定全域/benchmark/Recall 的准确性——它是指标可信度的**第一道关**。本文件给严谨的构建+调优方法，引 Cochrane 检索策略 + PRISMA-S。

---

## 一、概念框架（先拆研究问题，再扩词）

不要直接堆关键词。先把研究问题拆成概念维度，每维度独立扩词，最后组合。

### PICO（医学/健康科学）

- **P**opulation（人群）：如"2型糖尿病患者"
- **I**ntervention（干预）：如"SGLT2抑制剂"
- **C**omparator（对照）：如"安慰剂/其他降糖药"
- **O**utcome（结局）：如"心血管事件/死亡率"

每概念列同义词 → `(P同义词) AND (I同义词) AND (O同义词)` 组合检索。

### PECO（环境/流行病学）

Population / Exposure / Comparator / Outcome（同 PICO，I 换 E 暴露）。

### CS/AI 的概念矩阵（通用）

| 维度 | 例（3DGS） |
| --- | --- |
| 核心技术 | gaussian splatting / 3DGS / GS |
| 子方向 | slam / mapping / dynamic / mesh |
| 应用/场景 | autonomous driving / medical / indoor |

笛卡尔积组合：`核心技术 AND (子方向 OR 应用)`。

---

## 二、同义词扩展（穷尽措辞）

每个概念维度，穷尽所有可能措辞：

- **缩写/全称**：3DGS ↔ 3D Gaussian Splatting
- **多语言**：高斯泼溅 ↔ gaussian splatting（跨语言领域）
- **上位词**（更宽）：gaussian splatting → radiance field → novel view synthesis
- **下位词**（更窄）：具体方法名（Mip-Splatting / Scaffold-GS）
- **变体/同义**：splatting / splat / GS / gaussian splat

> 漏同义词 = 漏文献（Recall 下降）。扩词越全，灵敏度越高。

---

## 三、Gold-standard 调优（灵敏度/特异度，核心）

这是关键词质量的关键验证。

### 构建 gold set

- 选 10–20 篇**必中**的经典/seminal 论文（你确信必须被检索到）。
- 来源：领域奠基论文 + 权威 survey 必引的 + 高被引 top。

### 算两个指标

- **灵敏度（sensitivity）** = gold 命中数 / gold 总数 → 越高越好（别漏）
- **特异度（specificity）** = 命中相关 / 命中总数 → 越高越好（别引入无关）

### 迭代调优

| 情况 | 动作 |
| --- | --- |
| 灵敏度 <100%（漏了 gold） | **扩同义词**（加缩写/上位词/变体） |
| 特异度低（引入大量无关） | **加去噪词**（NOT 排除同名异义） |

迭代直到：**gold 100% 命中 + 引入无关可控**。这才算关键词合格。

---

## 四、去噪词（排除同名异义）

关键词可能引入无关（同名异义）：

- "apple" → 医学（苹果/过敏）vs 公司 → 加 NOT company/fruit（视领域）
- "splat" → 图形学 vs 非图形含义
- "GS" → gaussian splatting vs 其他缩写

领域-specific 的歧义词必须排除。

---

## 五、多数据库语法适配

同一组关键词，不同数据库语法不同：

| 数据库 | 字段语法 |
| --- | --- |
| OpenAlex | `search=`（title+abstract+fulltext）/ `filter=` / `title_and_abstract.search:` |
| PubMed | `[MeSH]` + `[Title/Abstract]` + 布尔 AND/OR/NOT |
| Web of Science | `TS=`（主题）/ `TI=`（标题）/ `AK=`（关键词） |
| Scopus | `TITLE-ABS-KEY()` |
| arXiv | `all:` / `ti:` / `abs:` + 布尔 |
| DBLP | 标题子串（无复杂布尔，简单） |

> 每个数据库都要**单独写检索式**（语法适配），记录存档。

---

## 六、PRISMA-S 报告规范（检索可复现）

按 **PRISMA-S**（Rethlefsen et al. 2021，检索策略报告规范）记录：

- 每数据库的**完整检索式**（含布尔/字段/过滤/限制）
- **检索日期** + **时间窗**（如 2020-01-01 至 2026-07-04）
- **数据库版本/快照**（OpenAlex 数据会变）
- **限速/替代策略**（如 OpenAlex 限速时换 Semantic Scholar）
- **gold set 来源 + 命中结果**（灵敏度/特异度）
- **去噪词列表**

> 检索式必须**可复现**——别人按你的式子能跑出同样结果。

---

## 七、完整迭代流程（关键词构建闭环）

```text
1. 拆概念（PICO / 概念矩阵）
   ↓
2. 扩同义词（缩写/多语/上下位/变体）
   ↓
3. 构 gold set（10–20 seminal）
   ↓
4. 跑检索 → 算灵敏度/特异度
   ↓
5. 迭代（灵敏度<100% 扩词；特异度低 加去噪）
   ↓
6. gold 100% + 特异度可接受 → 关键词定稿
   ↓
7. 多数据库语法适配
   ↓
8. PRISMA-S 报告（存档检索式/日期/版本/gold 结果）
```

> 这个闭环保证关键词**系统、可调优、可复现**——不是拍脑袋堆词。

---

## 八、领域特化注意

- **医学**：必用 MeSH 主题词（PubMed 医学受控词表）；PICO 框架
- **社科**：概念定义多变（同概念不同学派用词不同）；注意理论词+方法词+人群词
- **CS/AI**：术语更新快（新方法名层出不穷）；持续补新词
- **人文**：关键词作用弱（非实证为主），更多靠人工遴选

> AI 评估时先识别领域（见 domains.md）→ 套对应框架与注意点。
