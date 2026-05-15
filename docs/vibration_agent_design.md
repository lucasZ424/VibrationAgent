# Vibration Agent Design

Source: `Agent/vibration_agent_design.docx`
Generated for Codex-readable project context. Keep the DOCX as the human design source if both diverge.

# 振动学学习助手设计文档（完整版，含技术栈 / 知识库 / Skills / 示例）

> 用途：自用、长期迭代、工程导向的振动学专精学习与研究助手

> 本文档整合前三步讨论中的完整设计建议，目标是提供一份信息密度高、便于后续交叉验证和实际开发的总设计稿。文档默认采用我认为最合理的方案，除非你之前已经明确补充或订正。它不是面向外部团队的正式 PRD，而是面向你自己后续实现、校验、裁剪和扩展的技术蓝图。核心原则只有一条：这个系统必须明显优于“把文档直接扔给通用模型问答”的做法，否则没有搭建专用 agent 的意义。

## 0. 初期需求重定义（URGENT）

当前阶段的首要目标不是一次性完成完整专业版，而是尽快落地一个短期可用的振动学知识库 Agent。这个首期版本必须能读取知识库文件、提取文字内容、做基础清洗与切分、生成摘要或章节总结，并基于已入库内容完成问答。

实现形态以“LLM 挂 tools + 简单 skills” 为主，强调先把主链路跑通，再逐步补证据核验、多模型协作、taxonomy 与复杂工程能力。首期交付标准应以“可用、可查、可继续迭代”为第一目标，而不是追求完整版设计一次到位。

- URGENT：知识库文件文字提取与基础清洗，优先覆盖 PDF、扫描 PDF、Markdown、TXT、DOCX 等常见资料。
- URGENT：基础 chunking、最小索引与检索能力，保证已入库内容能被稳定召回用于总结与问答。
- URGENT：总结与问答能力，至少支持整篇摘要、章节摘要、针对知识库内容的定向提问。
- URGENT：统一入口 Agent 编排，采用少量简单 skills 连接摄取、检索、总结与问答。
以下能力保留在设计中，但不应阻塞首期：完整多模型审稿链、完善 taxonomy 沉淀、研究检索增强、模型选择与实验测量建议、全面证据标签体系。

## 1. 目标、边界与设计基线（URGENT）

系统的最终目标不是做一个泛化聊天机器人，而是做一个“振动学优先、工程项目优先、证据优先”的个人工作台。它的主要使用场景不是考试题和标准课后题，而是实际工程项目中遇到的概念理解、模型选择、参数意义辨析、公式适用范围判断、文档条文定位、相关论文调研、已有解决路径总结，以及把理论知识转化为工程解释和下一步行动建议。你当前处于学习阶段，但学习的目标是服务真实项目，因此系统必须默认采用工程模式输出，而不是学校考试答案模式。

这一定义直接决定了系统的边界：第一，它不能主要依赖主模型本身的泛化常识，必须尽量依赖本地知识库、结构化文档和可核验的证据。第二，它不能把“相关内容召回到了”误当成“已经有了高质量答案”；它必须对符号、单位、上下文语义和来源等级做进一步处理。第三，它不能以生成流畅答案为主要成功标准，而要以“是否专精、是否稳、是否可追溯、是否能在工程上使用”为成功标准。

## 2. 总体结论：是否适合由一个 agent 集中完成（URGENT）

结论是：适合由一个统一入口的 agent 对外完成，但绝不适合由一个单体大模型、单提示词、单链路来完成。最合理的形式是“一个总控 Tutor-Orchestrator + 多个专业 skills + 本地知识库 / 混合检索层 + 多模型审稿与核验层”。从用户视角看，它仍然是一个学习助手；从系统视角看，它是一个有严格路由和边界控制的领域系统。

这么做的原因在于，你提出的四类核心需求——文档阅读总结、精准问答、增强搜索与知识库、研究辅助——在工程上分别属于文档解析、检索增强问答、知识管理、外部研究检索四条不同任务链。它们的输入类型、失败模式、对时延和准确率的要求都不同。如果粗暴地塞进一个 agent prompt 里，系统会很快退化成“通用模型 + 工具调用”的松散组合，无法形成真正的专精优势。

对应当前阶段的收缩版实现，可先把统一入口压缩为“一个主控 LLM + tools + 少量简单 skills”，优先保留文档摄取与解析、知识库检索、总结/问答三条主链路，其余能力先作为后续扩展接口保留。

## 3. 总体架构（最佳推荐方案）（URGENT）

推荐采用五层架构：交互层、任务层、质量控制层、知识层、数据层。交互层只有一个统一入口，即 Tutor-Orchestrator，负责识别意图、决定路由、汇总结果、控制最终输出风格。任务层由多个 skills 组成，每个 skill 只负责一种任务，不允许同时兼顾检索、推导、总结、教学等多种责任。质量控制层负责证据核验、术语归一、符号和单位检查、多模型反驳审稿以及置信度控制。知识层包括本地知识库、混合检索、术语表、符号表、单位表、工程语境表、主题图谱等。数据层包括原始 PDF、OCR 后 PDF、结构化 JSON/Markdown、chunk 索引、向量索引、元数据数据库和日志。

```text
User
  ↓
URGENT -> Tutor-Orchestrator
  ├─ Task Layer
│   ├─ URGENT -> 文档摄取与解析 Skill
│   ├─ URGENT -> 知识库检索 Skill
│   ├─ URGENT -> 概念解释 / 总结问答 Skill
  │   ├─ 工程问题分析 Skill
  │   ├─ 公式与推导 Skill
  │   ├─ 文献研究检索 Skill
  │   ├─ 模型选择 Skill（增强）
  │   └─ 实验与测量建议 Skill（增强）
  ├─ Quality Control Layer
  │   ├─ 术语/符号/单位规范化
  │   ├─ 引用与证据核验
  │   ├─ 回答审稿
│   └─ URGENT -> 输出风格整形
  ├─ Knowledge Layer
│   ├─ URGENT -> 本地文档库
│   ├─ URGENT -> 混合检索（可先从简单版本起步）
  │   ├─ Glossary / Symbols / Units / Topic Map
  │   └─ 工程语境与案例沉淀
  └─ Data Layer
├─ URGENT -> Raw PDFs / OCR PDFs
├─ URGENT -> Extracted JSON / Markdown / Images / Tables
      ├─ PostgreSQL 元数据
├─ URGENT -> Qdrant 向量索引
      └─ Redis 缓存 / 任务状态 / 日志
```

## 4. 为什么这个系统必须“专精化”而不是“泛化聊天 + RAG”

判断一个系统是否专精，不看它能不能回答振动学问题，而看它在以下方面是否明显强于通用模型直接解析文档：第一，是否真的能稳定处理教材、标准、论文和扫描件，而不是只在少量干净 PDF 上好用。第二，是否对振动学中的多义术语、符号冲突、单位体系和公式适用条件有内建控制。第三，是否能把工程问题与学术定义区分开，并默认以工程意义、前提条件、局限性和下一步建议来组织答案。第四，是否能把知识沉淀为可复用资产，例如术语库、符号表、主题图和案例映射，而不是每次都从头检索。第五，是否能对回答进行证据核验，区分文档明确写出、模型推断、工程经验和不确定内容。

## 5. 技术栈与工具栈（首选方案）（URGENT）

在你“自用、长期迭代、非专业工程师但会借助多模型共同开发”的前提下，首选技术路线应当尽量稳、可读、资料多、便于模型协助生成和重构代码。我推荐的主栈是 Python + FastAPI + PostgreSQL + Qdrant + Redis + PyMuPDF + OCRmyPDF/Tesseract + React/Next.js。Python 是首选，因为文档解析、OCR、科学计算、检索、NLP 和 agent 编排生态都最成熟；FastAPI 适合做本地 API 层；PostgreSQL 负责元数据和结构化索引；Qdrant 适合本地部署 dense/sparse/hybrid 检索；Redis 用于缓存和任务队列；PyMuPDF 适合文字版 PDF 提取与页面级元素处理；OCRmyPDF + Tesseract 适合把扫描版 PDF 转成带文字层的可搜索文档；前端只需 React/Next.js 即可，不要求一开始做复杂应用。

## 6. 本地知识库设计：不是“向量库”，而是“证据中台”（URGENT）

本地知识库不能被理解为“把文档切片做 embedding 然后搜”，而应理解为一个围绕证据组织的中台。它至少要管理四类资产：原始文档资产、结构化文档资产、检索资产和证据资产。原始文档资产是 PDF、扫描件、讲义、项目笔记等；结构化文档资产是章节、段落、公式、图表、表格、图题、术语索引、符号索引；检索资产是 BM25 索引、向量索引、术语别名表、重排特征；证据资产是引用锚点、页码映射、chunk 与回答的对应关系。没有最后这一层，系统就无法形成可追溯优势。

## 7. 文档摄取与解析流水线（URGENT）

文档入库必须走统一流水线，不能“有时 OCR，有时直接切片，有时先问答”。标准流程建议为：文档分类、去重和元数据登记、OCR 判断、结构化提取、语义重组、chunking、索引构建、术语与符号回填、解析质量标记。扫描版 PDF 将是系统早期最主要的痛点。第一代不应追求“全自动完美提取”，而应追求“可搜索、可引用、错误可追踪、局部可人工修补”。

当前阶段在版面解析层暂时保留“原生 PDF 解析 + OCR 输出结构”的组合方案：有高质量文字层的 PDF 优先使用原生解析结果，扫描 PDF 或低质量文字层页面则主要依赖 OCR 输出的 block、bbox、page_no 和 confidence 等结构信息。这样做的目的是先把知识库入口跑通、保证可搜索与可引用，而不是在首期就引入更高颗粒度的独立版面理解层。

## 8. 检索设计：必须采用混合检索（URGENT）

振动学场景下，纯向量检索远远不够，纯关键词检索也不够。必须采用混合检索：先做 query 规范化，再走关键词召回与语义召回双路，再做融合与重排序。大量查询同时具有术语精确性和语义变体，因此 query 规范化、来源优先级和重排逻辑都很关键。来源优先级建议固定为：标准 > 教材 > 综述 > 单篇论文 > 网页；若问题明确要求最新研究，则允许论文和综述优先。

## 9. Taxonomy：真正使系统专精的长期资产

如果系统只存文本和 embedding，它充其量是一个会搜文档的问答器。真正使它专精的是 taxonomy，也就是你逐步沉淀下来的术语、符号、单位和主题关系资产。最少要维护四套表：glossary、symbols、units、engineering_context / topic_map。

## 10. 数据库架构建议（PostgreSQL 侧）（URGENT）

核心表建议至少包括 documents、document_sections、chunks、figures_tables、terms、symbols、units、citations、qa_logs。设计目标不是一次到极致，而是先支持文档入库、分层结构、chunk 检索、术语和符号映射、回答引用和错误追踪。

## 11. Skills 架构：推荐正式版本（URGENT）

对你这个项目，最合理的并不是 skill 越多越好，而是 skill 的边界越清晰越好。推荐采用“8 个核心 skills + 2 个增强 skills + 4 个横向校验/整形 skills”的正式版本。

若以当前初期需求为准，首批 URGENT skills 建议收缩为 4 个：S1 文档摄取与解析、S2 知识库检索、S3 概念解释 / 总结问答、V4 输出风格整形。其他 skills 可以先保留名称与接口，但不作为首期交付阻塞项。

## 12. 多模型协作设计

合理分工很关键。最优做法不是让所有模型都对同一问题各答一遍，而是按角色分工：主回答模型负责组织最终答案，代码实现模型负责写解析流程、检索与 API，审稿模型负责找偷换概念与前提遗漏，证据核对模型负责检查结论是否真的被来源支持。运行阶段只在高风险回答时启用完整校验链。

## 13. 工程导向输出模板（URGENT）

由于系统面向真实项目，最终回答模板建议固定为：先给结论，再解释工程意义，再列适用前提，再说明失效条件和常见误区，必要时给最简模型/公式，最后给下一步建议和证据标签。

## 14. 开发路线与工期估算（URGENT）

演示级 MVP 可以在 2–4 周内完成，但若目标是“明显专精、稳定、优于通用模型直接问答”，更现实的区间是：个人可稳定使用的一代版 6–10 周；较完整专业版 3–5 个月。

如果完全按当前短期目标收缩范围，可新增一个 URGENT 里程碑：先在 1-2 周内打通文件读取与文字提取、基础 chunking 与索引、摘要与问答接口，以及最小可用的 CLI 或页面入口。

## 15. 风险点与真实难点

真正难的地方不在聊天框和模型接线，而在文档处理质量、检索策略、术语和符号统一、证据核验、工程知识表达方式。最主要风险包括：扫描 PDF 质量差、公式图表解析不稳、专业术语多义、符号和单位冲突、缺乏现场上下文时给出伪确定性建议，以及系统前期过度设计。

## 16. 最终定型建议（URGENT）

推荐当前版本直接采用：一个对外统一的 Tutor-Orchestrator；底层使用 Python + FastAPI + PostgreSQL + Qdrant + Redis + PyMuPDF + OCRmyPDF/Tesseract + React/Next.js；知识侧构建本地证据中台而不是单纯向量库；检索侧使用 query 规范化 + BM25 + dense retrieval + reranker 的混合链路；能力侧采用 8 个核心 skills、2 个增强 skills 和 4 个校验/整形 skills；默认回答范式是工程模式；所有基于文档的回答都必须带证据标签和置信边界；所有长期优势都通过 taxonomy、案例沉淀和回归测试累积，而不是寄希望于模型自己越来越懂振动学。

因此，当前最现实的首发版本应定义为：围绕知识库文本提取、总结与问答的短期可用 Agent，而不是一开始就交付完整专业版能力矩阵。

## 附录 A：目录结构建议

```text
vibration_agent/
├─ apps/
│  ├─ api/
│  ├─ worker/
│  └─ ui/
├─ data/
│  ├─ raw/
│  ├─ ocr/
│  ├─ extracted/
│  ├─ chunks/
│  ├─ embeddings/
│  └─ exports/
├─ db/
│  ├─ postgres/
│  └─ qdrant/
├─ configs/
├─ taxonomy/
├─ prompts/
└─ tests/
```

## 附录 B：数据库表建议（URGENT）

| 表名 | 作用 | 核心字段 |
| --- | --- | --- |
| documents (URGENT) | 文档主表 | id, title, type, source, language, year, authors, file_path, ocr_status, parse_status, version, hash |
| document_sections (URGENT) | 章节层级 | id, doc_id, parent_id, heading, level, page_start, page_end |
| chunks (URGENT) | 检索基本单元 | id, doc_id, section_id, page_start, page_end, chunk_type, text, normalized_text, token_count, citation_anchor |
| figures_tables | 图表与图题 | id, doc_id, page_no, kind, caption, image_path, related_chunk_ids |
| terms | 术语规范表 | id, canonical_term, zh_name, en_name, aliases, notes, topic |
| symbols | 符号规范表 | id, canonical_symbol, latex, meaning, unit, notes |
| units | 单位规范表 | id, quantity, canonical_units, aliases, warning_notes |
| citations (URGENT) | 回答与证据映射 | answer_id, chunk_id, evidence_type, confidence |
| qa_logs (URGENT) | 问答记录与调试 | id, query, intent, chosen_skills, retrieved_chunks, final_verdict |

## 附录 C：Skills 架构图（文本版）（URGENT）

```text
URGENT -> Tutor-Orchestrator
├─ URGENT -> S1 文档摄取与解析
├─ URGENT -> S2 知识库检索
├─ URGENT -> S3 概念解释 / 总结问答
  ├─ S4 工程问题分析
  ├─ S5 公式与推导
  ├─ S6 文献研究检索
  ├─ S7 模型选择
  ├─ S8 实验与测量建议
  ├─ V1 术语/符号/单位规范化
  ├─ V2 引用与证据核验
  ├─ V3 回答审稿
└─ URGENT -> V4 输出风格整形
```

## 附录 D：Taxonomy 示例

glossary_zh_en.yaml

```text
term: transmissibility
zh: 传递率
aliases: [传递系数, 响应传递率]
note: 需要区分位移传递率与力传递率

```

symbols.yaml

```text
symbol: omega_n
latex: \omega_n
meaning: undamped natural angular frequency
unit: rad/s
avoid_confusion_with: [\omega_d, \Omega, f_n]

```

engineering_context.yaml

```text
topic: rotor_unbalance
related_topics: [critical_speed, synchronous_response, balancing]
typical_outputs: [振幅, 相位, 临界转速区间]
common_models: [Jeffcott rotor]
```

## 附录 E：JSON I/O 示例（URGENT）

通用 Skill 输入

```text
{
  "task_id": "...",
  "user_query": "...",
  "context": {...},
  "retrieval_results": [...],
  "user_mode": "engineering|definition|derivation|research",
  "constraints": {...}
}
```

通用 Skill 输出

```text
{
  "status": "ok|insufficient|fail",
  "summary": "...",
  "structured_result": {...},
  "citations": [...],
  "warnings": [...],
  "handoff_recommendation": "next_skill_name|finalize"
}
```

知识库检索 Skill 输出

```text
{
  "normalized_query": "half-power bandwidth damping ratio estimation",
  "intent": "definition|comparison|standard_lookup|engineering",
  "hits": [
    {
      "chunk_id": "c_001",
      "doc_id": "book_01",
      "source_type": "book",
      "pages": "134-135",
      "score": 0.92,
      "reason": "contains explicit damping ratio estimation method"
    }
  ]
}
```

工程问题分析 Skill 输出

```text
{
  "diagnosis_summary": "...",
  "likely_causes": ["...", "..."],
  "assumptions": ["operating speed near resonance", "sensor mounting is reliable"],
  "recommended_next_checks": ["run-up test", "phase measurement"],
  "modeling_level": "lumped|sdof|mdof|fem|experimental",
  "citations": [...]
}
```

引用与证据核验 Skill 输出

```text
{
  "verdict": "pass|revise|fail",
  "supported_claims": [...],
  "unsupported_claims": [...],
  "citation_map": [...],
  "labels": ["documented", "inferred", "heuristic"]
}

```

## OCR 子系统补充设计（新增）（URGENT）

本节用于正式补充 OCR 工具选型、双引擎工作流、阶段实施范围与入库策略。结论先行：对于当前振动学学习助手项目，推荐采用 “PaddleOCR 主链路 + Tesseract 兜底链路” 的双引擎方案，但当前只实现第一阶段和第二阶段，不做大批量离线吞吐优化。这里的目标不是追求单一 OCR 引擎在理论速度上的绝对优势，而是让扫描版 PDF、简体中文与英文混合文档、复杂教材与标准页能够稳定进入知识库，并且在后续检索、引用、问答和研究辅助中具备可用性。

### 一、为什么当前不建议把 “核心实现语言” 作为主决策依据。

对 OCR 子系统来说，端到端耗时通常由 PDF 渲染、切页、图像预处理、版面分析、文本检测、文本识别、后处理、结构重建、JSON/Markdown 输出以及知识库写入共同决定，因此并不能简单地根据 “Tesseract 主要以 C++ 开发” 就推断它在整个 agent 工作流里一定更快。你的项目当前也不以大批量离线处理为核心目标，而是以中英混合工程文档的知识库可用性为第一优先级，所以决定工具适配度的关键因素应当是中文支持、复杂版面处理能力、结构化输出能力、与 RAG/Agent 工作流的兼容性，以及后续是否便于做 fallback 与交叉验证。

### 二、主方案为什么推荐 PaddleOCR。

结合你当前的文档类型和系统目标，PaddleOCR 更适合作为主 OCR 方案。第一，你后续进入知识库的主要文档为简体中文和英文，PaddleOCR 在中文场景上天然更贴近你的主需求，同时也能够覆盖英文。第二，你不是在做单张图片 OCR，而是在做教材、标准、论文、扫描 PDF 的结构化解析，PaddleOCR 的整体方向更接近文档理解入口，而不仅仅是传统字符识别。第三，你整个系统的最终用途是知识库入库、RAG 检索、带页码引用问答和研究辅助，这要求 OCR 结果尽量向结构化文档靠拢，而不是只给出一段纯文本。第四，PaddleOCR 更适合被放进 “先解析、再结构化、再入库” 的主工作流中，因此它更符合你当前 agent 的系统目标。

### 三、为什么不把 Tesseract 作为主引擎，但仍然建议保留。

Tesseract 仍然值得保留，原因是它成熟、稳定、语言覆盖广、生态丰富，也适合作为轻量级基础 OCR 或第二引擎进行交叉验证。但就你的项目而言，它更适合扮演 fallback 或补充角色，而不是主链路角色。原因在于：第一，你后续会面对扫描教材、老旧 PDF、双语文档、复杂版面页，而这些页面如果只依赖传统 OCR 结果，往往还需要自己额外补很多预处理和结构重建工作；第二，你的目标不是“抽到字就行”，而是“抽出的内容要能进知识库、能被检索、能被引用”；第三，当前阶段你更重视稳定入库与下游可用性，而不是多语言极限覆盖或轻量部署优先。综合来看，Tesseract 更适合作为补充和保险，而不是首选主引擎。

### 四、正式定型的 OCR 选型结论。（URGENT）

当前项目的 OCR 子系统建议正式定型为：主 OCR 引擎采用 PaddleOCR，辅助 OCR 引擎采用 Tesseract。主链路优先处理所有需要 OCR 的文档页，辅助链路只在指定条件下触发。系统当前不追求大规模批量吞吐能力，也不以 “谁理论速度更快” 作为选型核心，而是以 “谁更适合中英混合工程文档解析并服务知识库” 作为主判断标准。

关于 Tesseract 的使用方式，当前版本明确约定为：仅作为 fallback OCR 引擎预备接入，不作为主链路，不进行任何自主训练。模型侧优先预备官方 tessdata_best 作为 fallback 语言模型集合，并结合 chi_sim、eng、osd 等语言包使用。

### 五、两阶段实施方案。（URGENT）

现阶段只做两步。第一阶段是 “PaddleOCR 主链路跑通”，目标是让扫描版 PDF 与低质量文字层 PDF 能够经过 OCR 后输出为可继续结构化处理的结果，并顺利进入知识库。第二阶段是在主链路稳定后加入 Tesseract fallback，使某些关键页或疑难页在必要时可以进行二次识别或交叉验证。这里的重点不是立刻做复杂的多引擎调度系统，而是先保证主链路可用，再逐步提升鲁棒性。

- URGENT：第一阶段目标：使用 PaddleOCR 作为默认 OCR 入口，优先解决简体中文与英文混合文档、扫描版教材、标准 PDF 等资料的可搜索化和可结构化问题。该阶段要求至少达成以下结果：文档能够成功切页并送入 OCR；OCR 输出能够和页码信息绑定；识别结果能够进入后续 chunking 与知识库入库流程；问答系统在引用时能够回链到原始页。
- 第二阶段目标：在主链路跑通后，为关键页和疑难页增加 Tesseract 兜底分支。该分支不默认全量运行，只在满足触发条件时启用，例如 PaddleOCR 页面置信度明显偏低、版面结构抽取失败、老旧扫描页效果差、或你希望对某些关键页面进行双引擎交叉验证。第二阶段的目标是提高稳健性，而不是替换主链路。
### 六、建议的 OCR 工作流。（URGENT）

推荐把 OCR 子系统接入现有文档摄取管线，形成一条清晰的执行链：上传原始文档后，系统先判断该 PDF 是否已具备高质量文字层；如果文字层充分且抽取质量可接受，则直接进入结构化解析；如果文字层为空、缺失严重或抽取质量不稳定，则进入 OCR 分支。进入 OCR 分支后，默认先调用 PaddleOCR 完成页面识别与基础结构化结果生成，再将结果送入后续的文档分块、术语归一、向量化与知识库写入流程。只有当页面在识别质量上触发预设异常条件时，才会额外调用 Tesseract 作为兜底分支。

在这一阶段，OCR 结果进入知识库前的版面结构整理仍以原生解析结果和 OCR 输出为主，不额外引入高复杂度的 VLM 版面理解层来包揽 layout analysis。后续若时间和评测资源允许，再把标题层级、多栏阅读顺序、复杂表格和异常页面的高颗粒度优化拆成独立升级项。

### 七、建议的 fallback 触发条件。

为了避免第二阶段把系统做得过重，建议只在有限且明确的场景下触发 Tesseract。可采用的触发条件包括：页面 OCR 置信度低于阈值；页面存在大量疑似乱码、缺字、错行或断列；页面被判定为老旧扫描件且 PaddleOCR 输出文本稀疏；页面属于关键证据页，例如你后续需要高精度引用的标准定义页、公式页或结论页；或者你希望对某些高价值页面做双引擎交叉验证。触发后，系统可将 Tesseract 结果与 PaddleOCR 结果进行简单比对，择优保留，或保留双版本供后续人工复核。

### 八、OCR 结果如何进入知识库。（URGENT）

这一部分要与前面已经设计好的本地知识库架构保持一致。OCR 输出不应只是纯文本文件，而应尽量转化为带页码、带块级结构、可回链的中间结果。最小入库单元至少应包含：doc_id、page_no、block_id、raw_text、normalized_text、bbox 或块位置信息、ocr_engine、confidence、language_guess、parse_status。随后再进入 section 重组、chunking、术语映射和 embedding。这样做的意义在于，后续问答如果要引用某个定义或公式，不只是能说“在这本书里出现过”，而是能尽量定位到具体页和具体段落。

### 九、OCR 子系统与现有数据库架构的衔接建议。（URGENT）

如果你后续继续沿用此前建议的 documents、document_sections、chunks、figures_tables、terms、symbols 等表，那么 OCR 补充字段建议至少增加在文档页级或块级结果表中，包括：ocr_engine、ocr_confidence、ocr_version、ocr_run_time、needs_review、fallback_used、fallback_engine、text_density、layout_quality。这样你后期就能基于这些字段做页面质量追踪、问题页回捞和人工复核，而不需要每次都重新跑完整文档。

### 十、建议保留的 OCR 元数据 JSON 示例。（URGENT）

```text
{
  "doc_id": "book_001",
  "page_no": 87,
  "ocr_required": true,
  "primary_engine": "paddleocr",
  "fallback_used": false,
  "ocr_confidence": 0.93,
  "layout_quality": "medium",
  "raw_text": "...",
  "normalized_text": "...",
  "blocks": [
    {"block_id": "p87_b1", "text": "...", "bbox": [x1, y1, x2, y2]},
    {"block_id": "p87_b2", "text": "...", "bbox": [x1, y1, x2, y2]}
  ],
  "needs_review": false
}
```

### 十一、当前阶段不建议做的事情。

为了控制复杂度，当前不建议一开始就做三件事。第一，不要一上来就追求多引擎并发、批量调度和吞吐优化，因为你现在并没有明显的大规模离线需求。第二，不要立刻追求复杂公式 OCR、图表语义理解和全自动完美结构恢复，因为这会迅速把系统复杂度抬高。第三，不要把 Tesseract 和 PaddleOCR 一开始都做成对等主链路，因为这会增加调试与维护成本。当前最合理的路线仍然是：先让 PaddleOCR 把知识库入口打通，再把 Tesseract 接成有边界的兜底模块。

同时，当前不建议因为追求更细的 layout 能力而提前重构整条版面解析链。首期应优先保证原生解析与 OCR 输出的中间结构稳定可落库，等真实文档评测积累到一定规模后，再决定是否把高颗粒度版面分析拆成独立层。

### 十二、这一补充对总成设计的影响。

加入这一 OCR 子系统补充后，你原有的三步走设计不需要推翻，只需要在文档摄取与解析子系统中正式加入 “OCR 双引擎主副方案”。这会让你的系统在扫描 PDF、简中/英文资料和复杂工程文档场景下更稳，同时也不会过早把系统带入高复杂度、多引擎高吞吐优化阶段。换句话说，这一补充不是改变总体架构，而是把总体架构里最容易成为痛点的入口环节具体化、工程化。
