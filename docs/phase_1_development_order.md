# 一阶段开发顺序

## 一阶段边界

一阶段目标是完成 Phase-0 的 Agent 最小闭环：S1 文档摄取、S2 知识库检索、S3 概念解释/摘要/问答、V4 输出风格整理。

本阶段只实现可被工程使用的基础能力，不实现 S4 工程分析、S5 公式推导、S6 文献搜索、S7 模型选择、S8 实验建议、V1 术语规范化、V2 引用检查、V3 审稿器。后续能力只保留注册名称或占位，不进入主链路。

## 目标开发清单

### 1. 固化一阶段边界

涉及代码/文档：
- `docs/phase_1_development_order.md`
- `docs/architecture.md`
- `README.md`
- `src/vibration_agent/skills/`

功能板块：
- 明确 Phase-0 只交付 S1、S2、S3、V4。
- 明确临时脚本与正式 Agent 模块的关系。
- 明确 deferred skills 只占位，不参与运行链路。

验收标准：
- 文档中能清楚判断哪些能力属于一阶段，哪些能力禁止提前实现。
- 所有入口说明都指向一阶段链路，不再默认使用临时 Markdown 导出。
- 新增模块没有把 S4/S5/S6/S7/S8 或 V1/V2/V3 混入 S3。

### 2. 固化数据与接口契约

涉及代码/文档：
- `src/vibration_agent/schemas.py`
- `docs/architecture.md`
- `db/postgres/migrations/001_init.sql`
- `db/qdrant/collections.md`

功能板块：
- 定义 `SkillInput`、`SkillOutput`、`Citation`。
- 定义文档、页面、块、图表、公式、表格、检索结果的数据模型。
- 定义一阶段 JSON/JSONL 文件导出结构。

验收标准：
- 所有 skill 只通过 `SkillInput` 输入、`SkillOutput` 输出。
- citation 必须包含 `chunk_id`、`doc_id`、`pages`、`evidence_type`、`confidence`。
- 文件导出字段能映射到 Postgres/Qdrant 所需字段。

### 3. 建立项目配置与运行入口

涉及代码/文档：
- `src/vibration_agent/config.py`
- `configs/app.yaml`
- `configs/ingestion.yaml`
- `configs/retrieval.yaml`
- `.env.example`
- `apps/cli/main.py`
- `apps/api/main.py`

功能板块：
- 统一读取路径、模型、OCR、数据库、向量库、缓存配置。
- 提供 CLI 和 API 入口的共享配置加载逻辑。
- 避免在业务代码中硬编码路径和参数。

验收标准：
- CLI/API/脚本可以使用同一套配置对象。
- 默认配置能在本地无数据库模式下跑通文件级摄取。
- 缺少必要配置时给出明确错误，不静默失败。

### 4. 完成文档输入层

涉及代码/文档：
- `src/vibration_agent/ingestion/classify.py`
- `src/vibration_agent/ingestion/pipeline.py`
- `scripts/ingest_folder.py`
- `data/raw/`

功能板块：
- 扫描输入目录。
- 识别 PDF、图片、已有文本层 PDF。
- 生成稳定 `doc_id`。
- 判断 native PDF 与扫描 PDF。

验收标准：
- `data/raw/book` 下 PDF 能被发现并生成稳定 `doc_id`。
- 同一文件重复运行不会生成不同 `doc_id`。
- 输入分类结果包含文件路径、文件类型、页数、处理策略。

### 5. 完成页面级 OCR 与解析层

涉及代码/文档：
- `src/vibration_agent/ingestion/pymupdf_parser.py`
- `src/vibration_agent/ingestion/ocr/router.py`
- `src/vibration_agent/ingestion/ocr/paddle_engine.py`
- `src/vibration_agent/ingestion/ocr/tesseract_engine.py`
- `scripts/ocr_raw_books_with_paddle.py`（迁移参考）

功能板块：
- native PDF 使用 PyMuPDF 提取文本。
- 扫描 PDF 使用 PaddleOCR。
- Tesseract 只作为低置信度、空结果、关键页 fallback。
- 输出 page-level JSONL。

验收标准：
- 每页输出包含 `doc_id`、`page_no`、`primary_engine`、`fallback_used`、`ocr_confidence`、`layout_quality`、`raw_text`、`normalized_text`、`blocks`、`needs_review`。
- OCR 结果可断点续跑。
- 低置信度页面被标记，不被当作高可信证据。

### 6. 完成版面对象识别层

涉及代码/文档：
- `src/vibration_agent/ingestion/pipeline.py`
- `src/vibration_agent/ingestion/chunking.py`
- `src/vibration_agent/schemas.py`
- `data/ocr/`
- `data/extracted/`

功能板块：
- 识别正文块、标题块、图、表、公式区域。
- 为图表公式生成资产引用。
- 保留页面锚点和 bbox。

验收标准：
- 页面 JSON 中能区分正文、标题、图、表、公式等对象类型。
- 图表公式不强行写入正文文本，而是作为资产引用挂接到页面/块。
- 每个非文本对象至少包含 `asset_id`、`page_no`、`bbox`、`asset_path`、`object_type`。

### 7. 完成正文、公式、图、表的统一资产模型

涉及代码/文档：
- `src/vibration_agent/schemas.py`
- `src/vibration_agent/knowledge/evidence.py`
- `data/extracted/`
- `data/exports/`

功能板块：
- 将正文文本、公式截图、图像截图、表格结构统一为可引用资产。
- chunk 可引用多个资产。
- 后续检索可以返回文本证据与视觉资产证据。

验收标准：
- chunk 中可以挂载 `assets[]`。
- 资产引用不依赖 Markdown。
- 同一页多个图/表/公式能被分别编号。

### 8. 完成切块策略

涉及代码/文档：
- `src/vibration_agent/ingestion/chunking.py`
- `src/vibration_agent/schemas.py`
- `configs/ingestion.yaml`
- `data/chunks/`

功能板块：
- 按章节、页码、段落进行切块。
- 默认约 600-800 token，保留 overlap。
- 不跨章节硬切；如必须跨越，记录边界。
- 保留 citation anchor。

验收标准：
- 每个 chunk 有 `chunk_id`、`doc_id`、`page_start`、`page_end`、`chunk_type`、`topic`、`token_estimate`、`text`、`assets`。
- chunk 不丢页码。
- 重复运行同一文档时 chunk id 稳定。

### 9. 完成文件级结构化导出

涉及代码/文档：
- `src/vibration_agent/ingestion/pipeline.py`
- `scripts/ingest_folder.py`
- `data/ocr/`
- `data/chunks/`
- `data/exports/`

功能板块：
- 输出 `pages.jsonl`。
- 输出 `chunks.jsonl`。
- 输出 `api_context.json` 或后续等价结构化上下文包。
- 输出 `manifest.json`。

验收标准：
- 不再生成 Markdown 中间文件作为主链路产物。
- `manifest.json` 能完整追踪输入、输出、页数、chunk 数、需复核页。
- 结构化文件能直接被后续 S1/S2 使用。

### 10. 完成数据库与向量库写入准备

涉及代码/文档：
- `db/postgres/migrations/001_init.sql`
- `db/qdrant/collections.md`
- `src/vibration_agent/storage/postgres.py`
- `src/vibration_agent/storage/qdrant.py`
- `src/vibration_agent/storage/redis_cache.py`

功能板块：
- Postgres 写入 documents、sections、chunks、figures_tables、terms、symbols、units、citations。
- Qdrant 写入 chunk embedding 与 payload。
- Redis 只做缓存，不做长期事实源。

验收标准：
- Python 中没有 inline DDL。
- 写入层可以 dry-run。
- 文件级导出字段与数据库字段一致。

### 11. 完成 S1 文档摄取技能

涉及代码/文档：
- `src/vibration_agent/skills/base.py`
- `src/vibration_agent/skills/s1_ingestion.py`
- `src/vibration_agent/ingestion/pipeline.py`
- `prompts/skills/s1_ingestion.md`

功能板块：
- 将输入文档转换为 page、asset、chunk、manifest。
- 支持扫描 PDF 和 native PDF。
- 返回摄取状态与质量警告。

验收标准：
- S1 输入输出符合 `SkillInput` / `SkillOutput`。
- 成功时返回 doc_id、chunk_count、输出路径。
- 失败时返回 fail 或 insufficient，不抛出无解释异常给上层。

### 12. 完成 S2 混合检索技能

涉及代码/文档：
- `src/vibration_agent/skills/s2_retrieval.py`
- `src/vibration_agent/retrieval/query_normalize.py`
- `src/vibration_agent/retrieval/bm25.py`
- `src/vibration_agent/retrieval/dense.py`
- `src/vibration_agent/retrieval/hybrid.py`
- `src/vibration_agent/retrieval/rerank.py`
- `prompts/skills/s2_retrieval.md`

功能板块：
- 查询归一化。
- BM25 与 dense 检索。
- RRF 融合。
- 按来源类型加权。
- 返回带 reason 的 hits。

验收标准：
- 返回结构符合 RetrievalOutput。
- 每个 hit 有 `chunk_id`、`doc_id`、`source_type`、`pages`、`score`、`reason`。
- 弱召回时返回 insufficient，不编造 chunk id。

### 13. 完成 S3 问答与摘要技能

涉及代码/文档：
- `src/vibration_agent/skills/s3_qa_summary.py`
- `src/vibration_agent/knowledge/evidence.py`
- `prompts/skills/s3_qa_summary.md`

功能板块：
- 支持 `whole_doc_summary`。
- 支持 `section_summary`。
- 支持 `qa`。
- 所有非平凡结论绑定 citation。

验收标准：
- 没有检索证据时回答 insufficient。
- 不使用模型世界知识填补文档缺口。
- 输出语言跟随主要资料语言。

### 14. 完成 V4 输出风格整理

涉及代码/文档：
- `src/vibration_agent/skills/v4_style.py`
- `prompts/skills/v4_style.md`
- `prompts/templates/engineering_answer.md`

功能板块：
- 将 S3 输出整理为工程模板。
- 保留证据区。
- 空段落自动省略。

验收标准：
- 默认输出顺序为：结论、工程意义、适用前提、失效条件/常见误区、最简模型/公式、下一步建议、证据。
- 不为了填模板而生成空话。
- citation 不丢失。

### 15. 完成 Tutor-Orchestrator 最小闭环

涉及代码/文档：
- `src/vibration_agent/orchestrator/tutor.py`
- `src/vibration_agent/skills/base.py`
- `src/vibration_agent/schemas.py`
- `prompts/orchestrator.md`

功能板块：
- 接收用户问题。
- 判断是否在振动/旋转机械/信号分析/标准范围内。
- 执行 S2 -> S3 -> V4。
- 暂不自动调用 S4/S5 等 deferred skills。

验收标准：
- 范围外问题返回 out-of-scope。
- 范围内问题经过检索后回答。
- 没有证据时返回 insufficient。

### 16. 完成 CLI 最小运行链路

涉及代码/文档：
- `apps/cli/main.py`
- `scripts/ingest_folder.py`
- `README.md`

功能板块：
- CLI 摄取文档。
- CLI 查询知识库。
- CLI 输出结构化结果。

验收标准：
- 可以通过命令行摄取 `data/raw/book`。
- 可以通过命令行对已摄取文档提问。
- CLI 返回状态码有明确语义。

### 17. 完成 API 最小调用链路

涉及代码/文档：
- `apps/api/main.py`
- `src/vibration_agent/orchestrator/tutor.py`
- `src/vibration_agent/schemas.py`

功能板块：
- FastAPI 暴露 health check。
- 暴露 ingestion 入口。
- 暴露 query 入口。

验收标准：
- `/health` 返回运行状态。
- API 请求和响应使用 Pydantic schema。
- 错误响应包含可定位原因。

### 18. 完成测试夹具与回归样例

涉及代码/文档：
- `tests/fixtures/`
- `tests/unit/`
- `tests/integration/`
- `pyproject.toml`

功能板块：
- 小型 PDF fixture。
- OCR 输出 fixture。
- chunk 输出 fixture。
- 检索 fixture。

验收标准：
- 单元测试覆盖 schema、chunking、query normalize、evidence。
- 集成测试覆盖 S1 -> S2 -> S3 -> V4。
- 测试不依赖整本大书才能运行。

### 19. 完成端到端验证

涉及代码/文档：
- `apps/cli/main.py`
- `apps/api/main.py`
- `scripts/ingest_folder.py`
- `tests/integration/`
- `data/exports/`

功能板块：
- 从 raw PDF 摄取到 chunk。
- 从 chunk 写入检索层。
- 从用户问题到工程模板回答。

验收标准：
- 一条真实振动问题可以返回带 citation 的工程回答。
- 一条资料缺口问题返回 insufficient。
- 一条范围外问题返回 out-of-scope。

### 20. 冻结一阶段接口，进入下一阶段规划

涉及代码/文档：
- `docs/architecture.md`
- `docs/phase_1_development_order.md`
- `src/vibration_agent/schemas.py`
- `README.md`

功能板块：
- 冻结一阶段 schema。
- 冻结目录约定。
- 记录已知缺口。
- 为二阶段设计保留接口。

验收标准：
- 一阶段接口变更必须先改 `schemas.py`。
- 文档中列出二阶段候选能力，但不改变一阶段实现范围。
- 主链路稳定为 ingestion -> retrieval -> QA/summary -> style。

## 推荐实现顺序

1. `docs/phase_1_development_order.md`
2. `src/vibration_agent/schemas.py`
3. `src/vibration_agent/config.py`
4. `configs/app.yaml`
5. `configs/ingestion.yaml`
6. `configs/retrieval.yaml`
7. `src/vibration_agent/skills/base.py`
8. `src/vibration_agent/ingestion/classify.py`
9. `src/vibration_agent/ingestion/pymupdf_parser.py`
10. `src/vibration_agent/ingestion/ocr/router.py`
11. `src/vibration_agent/ingestion/ocr/paddle_engine.py`
12. `src/vibration_agent/ingestion/ocr/tesseract_engine.py`
13. `src/vibration_agent/ingestion/pipeline.py`
14. `src/vibration_agent/ingestion/chunking.py`
15. `src/vibration_agent/knowledge/evidence.py`
16. `src/vibration_agent/storage/postgres.py`
17. `src/vibration_agent/storage/qdrant.py`
18. `src/vibration_agent/storage/redis_cache.py`
19. `src/vibration_agent/retrieval/query_normalize.py`
20. `src/vibration_agent/retrieval/bm25.py`
21. `src/vibration_agent/retrieval/dense.py`
22. `src/vibration_agent/retrieval/hybrid.py`
23. `src/vibration_agent/retrieval/rerank.py`
24. `src/vibration_agent/skills/s1_ingestion.py`
25. `src/vibration_agent/skills/s2_retrieval.py`
26. `src/vibration_agent/skills/s3_qa_summary.py`
27. `src/vibration_agent/skills/v4_style.py`
28. `src/vibration_agent/orchestrator/tutor.py`
29. `apps/cli/main.py`
30. `apps/api/main.py`
31. `apps/worker/main.py`
32. `scripts/ingest_folder.py`
33. `tests/unit/`
34. `tests/integration/`
35. `docs/architecture.md`

---

## 一阶段冻结结果

Obj20 完成后，一阶段接口冻结为 Phase-1 Interface Freeze 后的 Phase-0 最小闭环：`S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style`。

冻结依据：
- `src/vibration_agent/schemas.py` 是一阶段接口唯一来源。
- `docs/phase_1_interface_freeze.md` 记录冻结接口、入口、产物和 Phase2 候选范围。
- `docs/phase_1_deferred_and_polish_audit.md` 记录 deferred/polish 分类，明确哪些不阻塞 Phase1 完成。
- 主链路不调用 S4-S8 或 V1-V3。
- 默认测试夹具不依赖整本大书，完整回归由 `pytest tests -q` 验证。
