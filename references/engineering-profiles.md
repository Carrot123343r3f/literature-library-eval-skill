# 工程领域 profiles

选择最贴近研究问题的 profile；交叉工程问题可并用多个，并报告来源重叠与术语差异。

| Profile | 专业来源优先级 | 开放补充 | 问题框架 | 必查工程字段 |
| --- | --- | --- | --- | --- |
| 计算机与 AI | DBLP、IEEE Xplore、ACM DL | OpenAlex、Semantic Scholar、arXiv | 任务–方法–数据–指标–场景 | 数据泄漏、基线、数据划分、代码、版本 |
| 电子/通信/控制 | IEEE Xplore、Inspec | OpenAlex、arXiv | 系统–方法–指标–工况 | 标准、带宽/功耗、测试设置、基线 |
| 机械/制造/机器人 | Compendex、Scopus | OpenAlex、Crossref | 对象–方法–性能–工况 | 载荷、尺度、材料、试验/仿真、失效模式 |
| 土木/建筑 | Compendex、ASCE Library、Scopus | OpenAlex、Crossref | 结构/系统–干预–性能–环境 | 规范、荷载、地点、寿命、可靠性 |
| 材料工程 | Scopus、Web of Science、Compendex | OpenAlex、Crossref | 材料–制备–结构–性质–应用 | 制备条件、表征、基线、测试协议 |
| 能源/环境工程 | Compendex、Scopus、IEEE Xplore | OpenAlex、Crossref | 系统–过程–地点/尺度–指标 | 边界条件、生命周期、数据来源、法规/标准 |
| 化工过程 | Compendex、Scopus、Engineering Village | OpenAlex、Crossref | 单元/过程–方法–性能–工况 | 物料/能量衡算、操作条件、安全、放大尺度 |
| 航空航天/交通 | AIAA、SAE、TRID、Compendex | OpenAlex、Crossref | 系统–任务–环境–性能 | 工况、认证/标准、仿真验证、可靠性 |
| 生物医学工程 | IEEE Xplore、Compendex、PubMed（工程装置部分） | OpenAlex、Europe PMC | 装置/算法–对象–性能–场景 | 工程指标、验证集、装置版本；临床疗效问题转出范围 |

领域识别应保留理由和置信度。若研究问题主要是临床疗效、基础机制或纯理论，而不是工程系统/方法/性能问题，停止并说明不适用。

## Profile 默认值作为风险触发器，不是合格线

每个 profile 的年龄窗口（3/5/7 年）和比例（40%/35%/30%）是默认提醒值，不是自动强结论。以下情况均属正常：

- AI 领域中存在长期基础方法问题（如优化理论），近年比例低不自动等于库不合格；
- 材料、能源、化工常同时需要经典机理文献和近年工艺论文；
- 标准、规范、数据集、基准论文的年龄分布与普通研究论文不同；
- 新兴方向的预印本比例可能高，不等于库更可靠。

**节奏偏好（tempo）**：首次确认时询问用户倾向，作为 D2 软调整依据：

| tempo | 含义 | D2 窗口调整 |
|---|---|---|
| `frontier`（前沿导向） | 关注最新进展、新兴方法 | 从严——按 profile 默认（3/5/7 年） |
| `balanced`（均衡导向·推荐） | 兼顾经典基础与近年进展 | 从宽——窗口 × 1.5 |
| `classic`（经典基础导向） | 关注长期验证、标准规范 | 从宽——窗口 × 2.0 |

用户也可以指定"我只需要近 2 年"或"我需要 2015 年至今的全量"，直接覆盖自动 tempo。
