# vibration_agent 设计文档

## 0. 文档定位

本文档是 `vibration_agent` 的主设计文档，用于记录产品定位、系统边界、架构原则、Phase-0 范围和后续扩展方向。它不是外部 PRD，也不是一次性完整专业版规格，而是面向本地个人部署、长期迭代和工程学习使用的技术蓝图。

## 1. 产品定位

`vibration_agent` 是一个本地个人部署的振动学专精学习与知识库 Agent。目标用户是一名工程学习者/实践者，使用场景是围绕真实工业项目理解振动学、旋转机械、状态监测、信号分析和标准条文，而不是为了考试刷题。

默认运行模式是：单用户、本地文件、localhost CLI/API、私有知识库。它不是多用户 SaaS，也不是公开 Web 服务。当前阶段应优先保证语料质量、检索可靠性、证据可追溯、中英工程可用性和本地可复现性；共享、远程或公开部署需要单独进入 API 安全加固范围。

核心原则：系统必须明显优于“把文档直接交给通用模型问答”。如果不能提供稳定的文档入库、结构化检索、证据定位、工程化输出和可迭代知识沉淀，就没有搭建专用 Agent 的意义。

## 2. Phase-0 紧急范围

当前阶段不是完整专业版，而是先落地短期可用的振动学知识库 Agent。Phase-0 只交付以下能力：

- **S1 文档摄取与解析**：读取本地知识库文件，提取文字和页级结构，输出可继续处理的结构化数据。
- **S2 知识库检索**：基于已入库内容进行稳定召回，返回带原因和来源信息的检索结果。
- **S3 概念解释 / 摘要 / 问答**：只基于检索证据做解释、摘要和问答；证据不足时返回 `insufficient`。
- **V1 术语/符号/单位规范化**：可选质量层，在 S3 输入侧和 V4 输出侧规范术语与 SI 表述；两个调用点可独立关闭。
- **V2 引用与证据核验**：检查 S3 claim 是否引用 S2 可见 chunk，拦截 unsupported claim。
- **V4 输出风格整形**：把 V2 检查后的上游结果渲染为固定工程回答模板，不新增事实或工程判断。

以下能力保留名称和接口概念，但不在 Phase-0 激活：

- S4 工程问题分析
- S5 公式与推导
- S6 文献研究检索
- S7 模型选择
- S8 实验与测量建议
- V3 回答审稿

Phase-0 的主链路为：

```text
S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V2 citation check -> V4 style -> user/API/CLI
```

用户查询路径为：

```text
User query -> TutorOrchestrator -> S2 -> S3 -> V2 -> V4 -> SkillOutput/API/CLI JSON
```

S1 用于显式准备知识库，不在每次查询时自动运行。

## 3. 目标、边界与成功标准

系统目标不是泛化聊天，而是一个“振动学优先、工程项目优先、证据优先”的个人工作台。主要任务包括：

- 概念理解
- 模型选择依据
- 参数意义辨析
- 公式适用范围判断
- 文档条文定位
- 相关资料总结
- 理论知识到工程解释的转换
- 下一步行动建议

边界要求：

- 不主要依赖模型泛化常识，优先依赖本地知识库和可核验证据。
- 不把“召回到相关内容”误当成“已经得到高质量答案”。
- 不以流畅生成作为成功标准，而以专精性、稳定性、可追溯性和工程可用性作为成功标准。
- 范围限制在振动学、旋转机械、信号分析、状态监测、相关标准和工程语境；超出范围的问题应返回 out-of-scope 或 insufficient。

## 4. 总体架构

系统采用五层架构：

```text
User
  -> Tutor-Orchestrator
       -> Task Layer      skills/
       -> Quality Layer   quality/ + skills/v4_style.py
       -> Knowledge Layer knowledge/ + taxonomy/
       -> Data Layer      storage/ + db/ + data/
```

### 4.1 交互层

交互层只有一个统一入口：`TutorOrchestrator`。它负责识别意图、判断范围、选择技能链路、汇总中间结果，并控制最终输出形态。

### 4.2 任务层

任务层由多个 skill 组成。每个 skill 只负责一种任务，不把检索、推导、总结、审稿、教学混在一个模块里。Phase-0 主链路只激活 S1、S2、S3、V2、V4，V1 作为可选规范化层接入。

### 4.3 质量层

质量层用于术语/符号/单位规范化、引用核验、回答审稿和置信边界控制。Phase-0 中质量层当前主动接入可选 V1、V2 和 V4。

### 4.4 知识层

知识层包括本地文档库、混合检索、术语表、符号表、单位表、工程语境表和主题图谱。它是系统长期专精化的主要资产。

### 4.5 数据层

数据层管理原始文档、OCR 输出、结构化页面、chunk、导出文件、数据库 schema、向量库 payload 和运行日志。

## 5. 技术栈

当前技术栈约定为：

- Python 3.11
- FastAPI
- PostgreSQL，含 `pg_trgm`，可选 `pgvector`
- Qdrant
- Redis
- PyMuPDF
- PaddleOCR 主链路
- Tesseract fallback
- React/Next.js 延后

选型原则：优先使用成熟、可本地部署、可调试、适合模型辅助开发的技术。文档解析、OCR、检索、科学计算和 Agent 编排优先放在 Python 生态中完成。

## 6. 本地知识库：证据中台而不是单纯向量库

本地知识库不应被理解为“把文档切片后做 embedding 再搜索”。它应被理解为围绕证据组织的中台，至少管理四类资产：

- **原始文档资产**：PDF、扫描件、讲义、项目笔记、标准等。
- **结构化文档资产**：章节、段落、公式、图表、表格、图题、术语索引、符号索引。
- **检索资产**：BM25 索引、向量索引、术语别名、重排特征、来源优先级。
- **证据资产**：引用锚点、页码映射、chunk 与回答的对应关系、证据类型和置信度。

没有证据资产层，系统就只能“搜到内容”，不能稳定地“给出可追溯工程回答”。

## 7. 文档摄取与解析流水线

文档入库必须走统一流水线，避免“有时 OCR、有时直接切片、有时先问答”的混乱路径。

标准流程为：

```text
classify -> dedupe -> parse_native | parse_ocr -> structure -> chunk -> index -> quality_mark
```

当前实现优先保证入口可用和证据可回链，而不是追求复杂版面理解一次到位。

### 7.1 原生 PDF 路径

有高质量文字层的 PDF 优先使用 PyMuPDF 解析。解析结果需要保留页码、文本块、结构标记、图表/公式/表格资产引用和质量标记。

### 7.2 OCR 路径

扫描 PDF 或低质量文字层页面进入 OCR 分支。OCR 输出不应只是纯文本，而应尽量保留页码、块级结构、bbox、引擎信息、置信度和 review 标记。

推荐页级 OCR 输出结构：

```json
{
  "doc_id": "book_001",
  "page_no": 87,
  "primary_engine": "paddleocr",
  "fallback_used": false,
  "ocr_confidence": 0.93,
  "layout_quality": "medium",
  "raw_text": "...",
  "normalized_text": "...",
  "blocks": [
    {"block_id": "p87_b1", "text": "...", "bbox": [0, 0, 100, 20]},
    {"block_id": "p87_b2", "text": "...", "bbox": [0, 25, 100, 45]}
  ],
  "needs_review": false
}
```

### 7.3 OCR 引擎策略

OCR 子系统采用 **PaddleOCR 主链路 + Tesseract 兜底链路**。

PaddleOCR 作为主链路，原因是它更适合简体中文/英文混合文档、扫描教材、标准页和知识库入库场景。Tesseract 保留为 fallback，不作为主链路，也不在当前阶段做自主训练。

Tesseract 触发条件包括：

- 页面 OCR 置信度低于阈值。
- 页面输出为空或文本明显稀疏。
- 页面存在大量疑似乱码、错行、缺字或断列。
- 页面为关键证据页，例如标准定义页、公式页、结论页。
- 需要对高价值页面做双引擎交叉验证。

当前不建议一开始做多引擎并发、批量吞吐优化、复杂公式 OCR 或图表语义理解。先保证 PaddleOCR 主链路稳定入库，再接入有边界的 Tesseract fallback。

## 8. Chunking 策略

chunking 目标是让内容能被稳定检索、引用和输入模型上下文，而不是简单按固定字符数切开。

Phase-0 约定：

- 目标大小约 600 tokens。
- overlap 约 60 tokens。
- 不应无记录地跨越 section boundary。
- 每个 chunk 必须携带页码锚点。
- 图表、公式、表格应作为结构化资产引用挂载到相关 chunk。
- OCR 置信度、review 页、section 信息应尽量向 chunk 传递。

## 9. 检索设计

振动学场景下，纯向量检索不够，纯关键词检索也不够。Phase-0 检索设计采用混合检索：

```text
query_normalize -> BM25 ∪ dense -> RRF fusion -> optional rerank -> source-priority weighting
```

来源优先级默认固定为：

```text
standard > textbook > review > paper > webpage
```

若问题明确要求最新研究，可提高论文和综述优先级。每个检索 hit 必须包含 `chunk_id`、`doc_id`、`source_type`、`pages`、`score` 和简短 `reason`。如果召回不足，不允许编造 chunk id，应返回 `insufficient`。

## 10. Taxonomy：长期专精资产

如果系统只存文本和 embedding，它只是会搜索文档的问答器。真正让系统专精的是 taxonomy，即长期沉淀的术语、符号、单位和工程语境资产。

最少维护四类 YAML：

- `glossary_zh_en.yaml`
- `symbols.yaml`
- `units.yaml`
- `engineering_context.yaml`

长期原则：领域洞见优先沉淀到 taxonomy，不放进一次性 prompt。

示例：

```yaml
# glossary_zh_en.yaml
term: transmissibility
zh: 传递率
aliases: [传递系数, 响应传递率]
note: 需要区分位移传递率与力传递率
```

```yaml
# symbols.yaml
symbol: omega_n
latex: \omega_n
meaning: undamped natural angular frequency
unit: rad/s
avoid_confusion_with: [\omega_d, \Omega, f_n]
```

```yaml
# engineering_context.yaml
topic: rotor_unbalance
related_topics: [critical_speed, synchronous_response, balancing]
typical_outputs: [振幅, 相位, 临界转速区间]
common_models: [Jeffcott rotor]
```

## 11. 数据模型建议

PostgreSQL 核心表至少包括：

| 表名 | 作用 | 核心字段 |
| --- | --- | --- |
| `documents` | 文档主表 | `id, title, type, source, language, year, authors, file_path, ocr_status, parse_status, version, hash` |
| `document_sections` | 章节层级 | `id, doc_id, parent_id, heading, level, page_start, page_end` |
| `chunks` | 检索基本单元 | `id, doc_id, section_id, page_start, page_end, chunk_type, text, normalized_text, token_count, citation_anchor` |
| `figures_tables` | 图表与图题 | `id, doc_id, page_no, kind, caption, image_path, related_chunk_ids` |
| `terms` | 术语规范表 | `id, canonical_term, zh_name, en_name, aliases, notes, topic` |
| `symbols` | 符号规范表 | `id, canonical_symbol, latex, meaning, unit, notes` |
| `units` | 单位规范表 | `id, quantity, canonical_units, aliases, warning_notes` |
| `citations` | 回答与证据映射 | `answer_id, chunk_id, evidence_type, confidence` |
| `qa_logs` | 问答记录与调试 | `id, query, intent, chosen_skills, retrieved_chunks, final_verdict` |

数据库 schema 的正式来源是 `db/postgres/migrations/001_init.sql`。Python 代码中不写 inline DDL。

## 12. Skill 架构

每个 skill 统一消费 `SkillInput`，返回 `SkillOutput`。schema 以 `src/vibration_agent/schemas.py` 为唯一来源。

```json
{
  "task_id": "...",
  "user_query": "...",
  "context": {},
  "retrieval_results": [],
  "user_mode": "engineering",
  "constraints": {}
}
```

```json
{
  "status": "ok",
  "summary": "...",
  "structured_result": {},
  "citations": [],
  "warnings": [],
  "handoff_recommendation": null
}
```

Phase-0 激活 skill：

```text
TutorOrchestrator
├─ S1 文档摄取与解析
├─ S2 知识库检索
├─ S3 概念解释 / 摘要 / 问答
└─ V4 输出风格整形
```

保留但不激活：

```text
S4 工程问题分析
S5 公式与推导
S6 文献研究检索
S7 模型选择
S8 实验与测量建议
V1 术语/符号/单位规范化
V2 引用与证据核验
V3 回答审稿
```

## 13. 输出模板

默认输出模式是工程模式，而不是教材答案模式。

固定模板为：

```text
结论
工程意义
适用前提
失效条件/常见误区
最简模型/公式
下一步建议
证据
```

空 section 可以省略。V4 只能重排、整形和渲染上游内容，不新增工程结论、假设、公式或建议。

## 14. 多模型协作与项目自有 Skills

项目不绑定 Anthropic-native Skills 或 OpenAI-native tools。Skills 是项目自有资产，模型供应商只是推理或执行后端。

### 14.1 Skill 所有权

项目维护 vendor-neutral skill 层：

```text
agent_skills/
  s1_ingestion/
    SKILL.md
    references/
    scripts/
```

`agent_skills/<skill_id>/SKILL.md` 定义模型可读的行为边界：何时使用、需要哪些输入、允许什么输出、不能做什么、失败时如何处理。确定性实现仍在 `src/vibration_agent/skills/*.py`，并继续使用 `SkillInput` / `SkillOutput` 合约。

### 14.2 路由策略

默认模型路径是 GPT-first：

| 难度 | 默认处理者 | 说明 |
| --- | --- | --- |
| low | GPT | 简单问答、小修改、窄范围检查 |
| medium | GPT | 常规实现、文档、局部设计 |
| high | GPT | 复杂但边界明确的工程任务 |
| extreme | Opus-supervised loop | 架构、数学、安全、schema、持续失败等高风险任务 |

难度路由必须由 stakeholder-defined policy 决定。模型可以给建议，但不能不受限制地把普通任务升级到昂贵的 Opus 路径。

### 14.3 Extreme supervisor loop

```text
用户任务
  -> policy router 判定为 extreme
  -> Claude Opus：上层框架设计 / 任务分解 / 风险定义
  -> GPT：执行实现 / 测试 / 候选答案
  -> Claude Opus：senior supervisor review
  -> 无问题：输出
  -> 有问题且 loop_count < 2：GPT 修正后回到 Opus review
  -> 两轮后仍有问题：Opus 接管或暂停等待人工澄清
```

该控制面升级不改变 Phase-0 领域范围。S1、S2、S3、V2、V4 仍是唯一激活的主链路，V1 是链路外可选规范化层。

## 15. 目录结构约定

```text
Agent/
├─ apps/
│  ├─ api/
│  ├─ cli/
│  ├─ worker/
│  └─ ui/
├─ src/vibration_agent/
│  ├─ schemas.py
│  ├─ config.py
│  ├─ orchestrator/
│  ├─ skills/
│  ├─ ingestion/
│  ├─ retrieval/
│  ├─ knowledge/
│  ├─ storage/
│  ├─ llm/
│  └─ quality/
├─ agent_skills/
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
├─ scripts/
├─ tests/
└─ docs/
```

约定：

- 使用 `src/` layout，包名为 `vibration_agent`。
- `apps.*` 只做入口，不隐藏业务逻辑。
- OCR 放在 `ingestion/ocr/` 下，不做独立顶层能力。
- 新增 deferred skill 必须有自己的文件，不折叠进 S3。

## 16. 开发路线与工期判断

演示级 MVP 可以在 2-4 周内完成；若目标是“明显专精、稳定、优于通用模型直接问答”，更现实的个人可稳定使用一代版周期是 6-10 周，较完整专业版是 3-5 个月。

如果按当前短期目标收缩范围，首个可用里程碑是：打通文件读取与文字提取、基础 chunking 与索引、摘要与问答接口，以及最小可用 CLI 或本地页面入口。

## 17. 风险与真实难点

真正难点不在聊天框或模型接线，而在：

- 扫描 PDF 质量差。
- 公式和图表解析不稳定。
- 专业术语多义。
- 符号和单位冲突。
- 缺乏现场上下文时容易给出伪确定性建议。
- 检索召回不等于答案质量。
- 系统早期过度设计。
- 中文端到端 fixture、跨页多 chunk citation、真实语料回归还需要补强。

## 18. 当前不建议做的事情

为了控制复杂度，当前不建议：

- 一开始追求多 OCR 引擎并发、批量调度和吞吐优化。
- 立刻追求复杂公式 OCR、图表语义理解和全自动结构恢复。
- 把 Tesseract 和 PaddleOCR 做成对等主链路。
- 过早重构整条版面解析链。
- 在 evidence-bound S3 之前引入模型自由综合。
- 在本地个人部署定位未改变前优先投入生产 API 硬化。

## 19. 最终定型建议

当前首发版本应定义为：围绕本地知识库文本提取、结构化切分、检索、摘要与问答的短期可用 Agent，而不是完整专业能力矩阵。

推荐定型为：

- 一个对外统一的 `TutorOrchestrator`。
- Python + FastAPI + PostgreSQL + Qdrant + Redis + PyMuPDF + PaddleOCR + Tesseract fallback。
- 本地证据中台，而不是单纯向量库。
- `query_normalize + BM25 + dense + RRF/rerank` 的混合检索链路。
- Phase-0 主链路只激活 S1、S2、S3、V2、V4；V1 作为可选规范化层接入。
- 默认工程回答模板。
- 文档回答必须带证据标签和置信边界。
- 长期优势通过 taxonomy、案例沉淀和回归测试积累。

## 附录 A：Qdrant payload 建议

Qdrant collection：`chunks`

向量距离：cosine

payload 至少包括：

```json
{
  "chunk_id": "c_001",
  "doc_id": "book_01",
  "source_type": "book",
  "page_start": 134,
  "page_end": 135,
  "chunk_type": "body",
  "topic": "rotor_dynamics"
}
```

## 附录 B：检索输出示例

```json
{
  "normalized_query": "half-power bandwidth damping ratio estimation",
  "intent": "definition",
  "hits": [
    {
      "chunk_id": "c_001",
      "doc_id": "book_01",
      "source_type": "book",
      "pages": [134, 135],
      "score": 0.92,
      "reason": "contains explicit damping ratio estimation method"
    }
  ]
}
```

## 附录 C：工程问题分析输出示例

该 skill 属于 deferred 能力，示例只用于保留接口方向。

```json
{
  "diagnosis_summary": "...",
  "likely_causes": ["...", "..."],
  "assumptions": ["operating speed near resonance", "sensor mounting is reliable"],
  "recommended_next_checks": ["run-up test", "phase measurement"],
  "modeling_level": "lumped|sdof|mdof|fem|experimental",
  "citations": []
}
```

## 附录 D：引用与证据标签

证据标签至少包括：

- `documented`：文档明确支持。
- `inferred`：基于文档内容推断。
- `heuristic`：工程经验或启发式判断。

Phase-0 默认只应稳定使用 documented 证据。inferred 和 heuristic 需要在后续质量层激活后再严格治理。
