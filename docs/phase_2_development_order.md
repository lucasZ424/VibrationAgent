# 二阶段开发顺序

## 二阶段边界

二阶段目标是在一阶段冻结接口之上，激活语义检索、持久化、模型驱动综合与质量层，覆盖 S4、S5、V1、V2、V3 五个 deferred skill，并将 Phase-0 的确定性管线扩展为可上线的工程级运行链路。

二阶段不实现：S6 文献搜索、S7 模型选择、S8 实验建议（统一推迟到三阶段）、Web 前端、k8s 部署、多租户、可观察性栈。后续能力只保留注册名称或占位，不进入二阶段主链路。

二阶段不破坏一阶段冻结接口。所有 `schemas.py` 中已冻结契约的变更必须先在 `src/vibration_agent/schemas.py` 起手，并按 `docs/phase_2_migrations.md` 中的 canonical schema-change checklist 记录迁移说明、更新 fixtures/tests、再改下游调用方。新增字段优先以 optional 形式追加；废弃字段需在二阶段冻结时统一处理。

## 执行模型与风险控制

二阶段保持一个连续阶段，不再拆分为 Phase-2A/2B/2C。执行粒度固定为单个 Obj：每个 Obj 独立定义成功标准、完成实现、跑对应验证，并在进入下一个 Obj 前做评估。评估未通过时，不继续推进后续目标。

风险控制原则：

1. 不跨 Obj 批量合并能力。尤其是 embeddings、Qdrant、Postgres、LLM S3、V2、S4、S5，必须逐项落地、逐项验证。
2. 所有外部依赖能力必须保留一阶段降级路径。缺少模型、Qdrant、Postgres、在线 LLM 或 Opus 时，fast suite 和本地基础问答仍可运行。
3. 高风险能力默认通过 feature flag 或显式配置启用。未完成配套校验前，不替换一阶段默认确定性链路。
4. S3 LLM 综合与 V2 引用核对视为强耦合交付面。可以分 Obj 实现，但 S3 LLM 默认启用前必须已有 V2 或等价引用拦截保护。
5. 每个 Obj 完成后更新 `docs/phase_2_progress.md`，记录已验证命令、残留风险、是否允许进入下一 Obj。

## 排序原则

1. 先补一阶段遗留的回归基线（双语、跨页、元数据），让后续真实数据通路有可验证的样本。
2. 再做数据层（embeddings → Qdrant → Postgres → qa_logs），让综合层落到真实检索而不是确定性 fallback。
3. 再做综合层（S3 LLM 综合 → V2 引用核对 → V1 规范化 → V3 审稿），按"先生成、再校验、再润色"次序，避免把校验机制写在生成器之后。
4. 再做工程能力（Opus supervisor、S4、S5），这些都依赖前述综合 + 校验机制。
5. 最后做生产化加固与 CI 门控，避免在不稳定运行链路上过早建 CI。
6. 收尾冻结，进入三阶段规划。

## 目标开发清单

### 1. 固化二阶段边界

涉及代码/文档：
- `docs/phase_2_development_order.md`
- `docs/architecture.md`
- `docs/phase_1_interface_freeze.md`
- `README.md`

功能板块：
- 明确二阶段交付的 deferred skills 范围（V1、V2、V3、S4、S5）。
- 明确推迟到三阶段的能力（S6、S7、S8、Web、k8s、多租户）。
- 明确 `schemas.py` 的接口变更流程在二阶段保持有效。

验收标准：
- 文档可判断哪些能力属于二阶段、哪些禁止在二阶段实现。
- README 与 architecture 指向二阶段开发计划，不再默认主链路停留在 Phase-0。
- 任何对一阶段冻结契约的扩展都按"先改 schemas.py → 更新迁移说明 → 改调用方"流程进行。

### 2. 双语 fixture 与多页/跨 chunk 回归样例

涉及代码/文档：
- `tests/fixtures/raw/`
- `tests/fixtures/ocr/`
- `tests/fixtures/chunks/`
- `tests/fixtures/retrieval/`
- `tests/integration/test_phase0_fixture_chain.py`
- `tests/integration/test_obj19_end_to_end.py`

功能板块：
- 增加中文小型 PDF fixture 与对应 OCR/chunk/retrieval 样本。
- 增加跨页 chunk fixture（≥2 页，验证 `page_boundary_crossed` 与 `pages` 聚合）。
- 增加 zh 端到端问答验证（in-scope、insufficient、out-of-scope）。

验收标准：
- `pytest -m integration` 同时覆盖中文与英文端到端链路。
- 多页 fixture 至少触发一次 `page_start != page_end` 的 chunk。
- zh 路径在 V4 `language` 字段返回 `zh`，输出包含 `## 结论` 与 `## 证据`。

### 3. 文献元数据与段落父子链接补全

涉及代码/文档：
- `src/vibration_agent/schemas.py`
- `src/vibration_agent/ingestion/bibliography.py`（新增）
- `src/vibration_agent/ingestion/section_hierarchy.py`（新增）
- `src/vibration_agent/ingestion/chunking.py`
- `tests/unit/test_bibliography.py`（新增）
- `tests/unit/test_section_hierarchy.py`（新增）

功能板块：
- 从 PDF 元数据与首页文本抽取 `documents.year`、`documents.authors`、`documents.publisher`。
- 段落 / 章节层级 parent linking，在 chunk metadata 中暴露 `section_parent_keys[]`。
- 将上述字段以 optional 追加到 `MemoryChunk.metadata`，不改动既有字段语义。

验收标准：
- 一阶段冻结契约不破坏，新增字段在缺失时回退为空 / null。
- 单元测试覆盖 PDF metadata 抽取、首页推断、section parent 链接。
- 引文模板 `citation_anchor` 在有 author/year 时优先使用 "Author (Year), p. N"，无则回退一阶段格式。

### 4. DOCX 摄取能力

涉及代码/文档：
- `src/vibration_agent/ingestion/docx_parser.py`（新增）
- `src/vibration_agent/ingestion/classify.py`
- `src/vibration_agent/ingestion/pipeline.py`
- `tests/fixtures/raw/small_vibration_zh.docx`（新增）
- `tests/unit/test_docx_parser.py`（新增）

功能板块：
- DOCX 文档分类与解析，输出与 PDF 同构的 `OcrPage` 行。
- 段落、标题、表格、嵌入图片的资产抽取（沿用现有 `DocumentAsset`）。
- 文件锁、损坏文档、空文档的错误路径返回 `insufficient`。

验收标准：
- `pytest tests` 包含 DOCX 摄取单元 + 一条 zh DOCX 端到端验证。
- DOCX 与 PDF 经过 `chunk_documents` 后产出格式一致的 `chunks.jsonl`。
- 异常 DOCX 不会让 CLI/API 抛 traceback，统一返回结构化错误。

### 5. 真实 embedding 生成层

涉及代码/文档：
- `src/vibration_agent/retrieval/embeddings.py`
- `configs/embeddings.yaml`（新增）
- `tests/unit/test_embeddings.py`

功能板块：
- 接入一个可离线运行的 embedding 模型（sentence-transformers 或 bge-small 级别），可通过 config 切换。
- 提供 `embed_texts(texts, *, batch_size)` 与 chunk-level 缓存（避免重复嵌入）。
- 将 `dense.py` 中的确定性 fallback 改为：本地模型为主，token-feature 为冷启动降级。

验收标准：
- 嵌入维度、模型名、版本写入 `EmbeddingRecord` schema 字段（新增，optional）。
- 模型加载失败时 `dense.py` 降级到一阶段确定性逻辑并标 `warnings`。
- 单元测试覆盖批量嵌入、缓存命中、降级路径。

### 6. Qdrant 写入与读取链路

涉及代码/文档：
- `src/vibration_agent/storage/qdrant.py`
- `src/vibration_agent/storage/qdrant_client.py`（新增）
- `src/vibration_agent/retrieval/dense.py`
- `src/vibration_agent/retrieval/hybrid.py`
- `tests/integration/test_qdrant_roundtrip.py`（新增）

功能板块：
- Qdrant collection 初始化、upsert、search 接口落地（保留一阶段 dry-run plan 作为 fallback）。
- `dense.py` 在 Qdrant 在线时调用真实语义检索，否则降级。
- `hybrid.py` RRF 融合保持不变，仅替换底层 dense source。

验收标准：
- 集成测试需 Qdrant 实例（docker-compose / `pytest.importorskip("qdrant_client")`），缺失时 skip。
- 任何 Qdrant 操作失败不阻塞 CLI/API：dense lane 降级到一阶段 token-feature 逻辑并记录 `warnings`；只有所有检索通道均无可用证据时才返回 `insufficient`。
- 一阶段不依赖 Qdrant 的回归套件仍然通过（fast suite 不要求 Qdrant）。

### 7. Postgres 实时写入与 qa_logs 持久化

涉及代码/文档：
- `src/vibration_agent/storage/postgres.py`
- `src/vibration_agent/storage/postgres_client.py`（新增）
- `src/vibration_agent/storage/qa_logs.py`（新增）
- `db/migrations/`（新增）
- `tests/integration/test_postgres_roundtrip.py`（新增）

功能板块：
- documents、chunks、assets、qa_logs 表的迁移文件与 upsert/read 接口。
- Tutor-Orchestrator 每次 `handle_query` 落 `qa_logs` 一行（question、citations、status、timing、token cost）。
- 离线运行时（无 Postgres）skip 持久化，主链路不受影响。

验收标准：
- 迁移脚本可重放（idempotent），与一阶段 storage/mappings.py 的 schema 对齐。
- `pytest.importorskip("psycopg")` 守卫集成测试。
- `qa_logs` 写入是可选 side effect；写入失败只产生 warning，不改变 Tutor-Orchestrator 的主返回状态。
- qa_logs 不持久 API key 或长文本原文，只保留可定位的引用与摘要。

### 8. 大语料冷启动与回归基线

涉及代码/文档：
- `tests/integration/test_large_corpus.py`（新增）
- `scripts/bench_large_corpus.py`（新增）
- `docs/phase_2_progress.md`

功能板块：
- 用 Bently 全书或等量语料跑一次端到端摄取 → 嵌入 → 持久化 → 查询。
- 记录耗时、token cost、chunk count、retrieval recall on a 20-question 抽测集。
- 把抽测集结果写入 `docs/phase_2_progress.md`，作为后续优化的对照基线。

验收标准：
- 默认 fast suite 不跑这一项（mark `slow` 或 `large_corpus`）。
- 回归命令在 README "Testing" 节出现，单独入口而非 default。
- 抽测集回答均带 citation；无 citation 的回答统计单独列出。

### 9. LLM-backed S3 evidence-bound synthesis

涉及代码/文档：
- `src/vibration_agent/skills/s3_qa_summary.py`
- `src/vibration_agent/agent/routing.py`
- `src/vibration_agent/agent/model_registry.py`
- `prompts/skills/s3_qa_summary.md`
- `tests/unit/test_s3_llm_synthesis.py`（新增）

功能板块：
- S3 在 evidence 足够时改为 LLM 生成结论 + 证据引用，evidence 不足时保留一阶段确定性 fallback。
- Prompt 强制要求每条 claim 必须带 `[chunk_id]` 引用；缺失视为 hallucination 由下游 V2 拦截。
- 一阶段 routing 已在 GPT 优先 / Opus 仅 extreme 升级；S3 默认走 GPT。

验收标准：
- V2 或等价引用拦截未完成前，LLM-backed S3 只能通过 feature flag 手动启用，不能替换默认 S3 路径。
- 无 evidence 时不调用 LLM，直接返回 `insufficient`。
- LLM 失败 / timeout / quota 用 `warnings` 记录并降级到一阶段确定性逻辑。
- 单元测试通过 mock 客户端覆盖 ok / insufficient / fail / timeout 四条路径。

### 10. V2 引用核对（citation check）

涉及代码/文档：
- `src/vibration_agent/skills/v2_citation_check.py`
- `src/vibration_agent/orchestrator/tutor.py`
- `prompts/skills/v2_citation_check.md`
- `tests/unit/test_v2_citation_check.py`（新增）

功能板块：
- 在 S3 → V4 之间插入 V2：解析答案中的 `[chunk_id]` 引用，比对 retrieval 结果集；不存在或与原文不符的 claim 标 `unsupported_claims`。
- V2 returns `insufficient` 时把 `unsupported_claims` 写入 SkillOutput.warnings 并阻断 V4 的"结论"段落，只保留"证据"段落。
- 主链路扩展为 `S2 → S3 → V2 → V4`，但 V2 不被算作"新链路"——在冻结文档中标注为质量层。

验收标准：
- V2 至少覆盖引用存在性、chunk 可见性、无引用 claim 拦截、明显词面不匹配拦截；语义蕴含级核对不作为二阶段强制验收。
- V2 拦截率 ≥ 90% 的人为构造伪引用（单元测试样本）。
- 端到端：在 S3 故意 mock 出未引用的 claim 时，最终答案中不会出现该 claim。
- V2 失败本身不让主链路 fail，降级到 `warnings` + 透传 S3 原答案。

### 11. V1 术语/符号/单位规范化

涉及代码/文档：
- `src/vibration_agent/skills/v1_term_symbol_unit_normalizer.py`
- `taxonomy/terms_zh_en.yaml`（新增）
- `taxonomy/units.yaml`（新增）
- `tests/unit/test_v1_normalizer.py`（新增）

功能板块：
- 维护 zh/en 术语别名表与 SI 单位映射，归一化 chunk text 与最终答案中的表述。
- 在 S3 输入侧（chunk text）与 V4 输出侧（最终答案）两处调用，避免双语混用。
- 单位换算只做 SI 内归一化，不做工程单位换算（留 Phase-3）。

验收标准：
- 单元测试覆盖术语映射、缺失术语穿透、单位归一化。
- V1 的输入侧规范化和输出侧渲染可以共用词表，但必须保持两个调用点可独立关闭，避免隐式改写 evidence 原文。
- V1 改写不破坏 citation 锚点（`[chunk_id]` 必须保留）。
- 关闭 V1 时（feature flag）主链路依然通过——V1 不是必经节点。

### 12. V3 审稿器（reviewer）

涉及代码/文档：
- `src/vibration_agent/skills/v3_reviewer.py`
- `prompts/skills/v3_reviewer.md`
- `src/vibration_agent/orchestrator/tutor.py`
- `tests/unit/test_v3_reviewer.py`（新增）

功能板块：
- V4 输出后调用 V3：检查"结论 / 证据 / 限制"三段完整性、是否回避原问题、是否过度声称。
- V3 returns `insufficient` 时把 reviewer comments 写入 `SkillOutput.structured_result.reviewer_notes`，但不阻断答案返回。
- V3 仅由 `extreme` 难度查询启用；普通查询默认 skip 以节省 token。

验收标准：
- 单元测试：构造"结论缺失"、"答非所问"、"过度声称"三类样本，V3 都标出。
- 主链路扩展为 `S2 → S3 → V2 → V4 → V3`，文档明确 V3 仅 advisory，不阻断。
- V3 失败不影响最终答案返回。

### 13. Opus supervisor 执行回路

涉及代码/文档：
- `src/vibration_agent/agent/supervisor.py`
- `src/vibration_agent/agent/routing.py`
- `src/vibration_agent/orchestrator/tutor.py`
- `tests/unit/test_supervisor_loop.py`（新增）

功能板块：
- 一阶段已有 routing / model_registry / supervisor 骨架，二阶段补全真实执行回路。
- supervisor 仅在 `extreme` 难度查询或 V3 标 reviewer fail 时接管，循环上限 2 圈。
- supervisor 失败时降级到一阶段确定性结果，标 `supervisor_status` 字段。

验收标准：
- 普通查询不调用 Opus，路由可在 `apps.api.main` 日志中验证。
- supervisor 接管的查询在 `qa_logs` 中可识别（新增 `supervisor_invocations` 字段）。
- 单元测试覆盖：未触发、触发后成功、触发后失败三路径。

### 14. S4 工程分析

涉及代码/文档：
- `src/vibration_agent/skills/s4_engineering_analysis.py`
- `agent_skills/s4_engineering_analysis/SKILL.md`
- `prompts/skills/s4_engineering_analysis.md`
- `tests/unit/test_s4_engineering.py`（新增）

功能板块：
- S4 在 S3 之后、V2 之前可选插入：基于 evidence 给出工程分析（不仅是定义，还包括影响、典型场景、对策）。
- 仅在用户 `user_mode == "engineering"` 且 evidence 充足时启用；否则 skip。
- 输出强制走 V2 校验，避免编造工程数据。

验收标准：
- S4 输出的所有具体数值/参数必须可在 evidence 中找到出处，否则 V2 应拦截。
- 单元测试覆盖：evidence 充足、evidence 不足、user_mode 不匹配三种路径。
- 默认 fast suite 不调用 LLM，使用 mock 验证 routing。

### 15. S5 公式推导

涉及代码/文档：
- `src/vibration_agent/skills/s5_formula_derivation.py`
- `agent_skills/s5_formula_derivation/SKILL.md`
- `prompts/skills/s5_formula_derivation.md`
- `tests/unit/test_s5_derivation.py`（新增）

功能板块：
- S5 仅在 `user_mode == "derivation"` 时启用，输出格式为"前提 → 步骤 → 结论"。
- 每个步骤必须引用一条 evidence chunk 或公认数学结论（后者标 `axiomatic`）。
- LaTeX / MathML 输出沿用一阶段 V4 模板的资产引用机制。

验收标准：
- S5 输出在缺少 evidence 时返回 `insufficient`，不允许"凭经验"。
- 单元测试覆盖：完整推导链、缺步骤、循环引用三类异常。
- V2 必须能识别 S5 输出中的 `axiomatic` 步骤并放行，不能误判为伪引用。

### 16. API 生产化加固

涉及代码/文档：
- `apps/api/main.py`
- `apps/api/middleware/`（新增）
- `apps/api/auth.py`（新增）
- `configs/api.yaml`
- `tests/unit/test_api_hardening.py`（新增）

功能板块：
- `ApiIngestionRequest.path` 加 workspace 白名单校验，拒绝 traversal。
- API token / API key 认证中间件（开关可配置，默认开启 prod、关闭 dev）。
- CORS、rate limiting、`/health` 加 Postgres + Qdrant 探活。
- `ApiHealthResponse.status` 扩展为 `ok | degraded | fail`。

验收标准：
- 路径白名单校验优先于认证/CORS/rate limiting 落地；除非产品定位从本地个人部署变为共享/远程访问，否则认证/CORS/rate limiting 不得阻塞检索与引用质量目标。
- 单元测试覆盖：无 token、错 token、对 token、路径越权、降级 health。
- localhost 默认行为不变（开关默认关闭以保持 dev 体验）。
- 一阶段冻结的 API 字段不破坏；新增字段全部 optional。

### 17. CI 工作流与回归门

涉及代码/文档：
- `.github/workflows/test.yml`（新增）
- `Makefile`
- `README.md`
- `pyproject.toml`

功能板块：
- CI 拉起 PR / push 时执行 `pytest -m "not integration"`（fast）。
- nightly 工作流执行 `pytest tests -q` 全套 + 大语料抽测集（obj 8）。
- 失败时 PR 阻断；nightly 失败只发邮件，不阻断 main。

验收标准：
- main 分支 push 后 5 分钟内出 fast 结果。
- nightly 大语料任务的输出保存为 artifact（不进 git）。
- README 的 Testing 节同时说明 local 与 CI 两路。

### 18. 端到端二阶段验证

涉及代码/文档：
- `tests/integration/test_phase2_end_to_end.py`（新增）
- `tests/fixtures/`
- `docs/phase_2_progress.md`

功能板块：
- 一条 zh 真实振动问题，evidence 来自 PDF + DOCX 各一份，验证 S2 → S3 → V2 → V4 → V3 全链路。
- 一条触发 supervisor 的 `extreme` 难度问题，验证 Opus 接管 + 降级。
- 一条故意触发 V2 拦截的伪引用问题，验证拦截后答案剥离结论段。

验收标准：
- 三条 E2E 全部通过且断言到 citation、status、scope、reviewer_notes。
- E2E 不依赖在线 LLM（mock 客户端）以保证 CI 可重放。
- 真实 LLM 路径用一条手动验证脚本（`scripts/manual_e2e.py`）覆盖，不进 CI。

### 19. 二阶段接口冻结与三阶段规划

涉及代码/文档：
- `docs/phase_2_interface_freeze.md`（新增）
- `docs/phase_2_deferred_and_polish_audit.md`（新增）
- `docs/phase_1_interface_freeze.md`
- `src/vibration_agent/schemas.py`
- `docs/architecture.md`
- `README.md`

功能板块：
- 冻结二阶段新增 schema（embeddings、qa_logs、V2 unsupported_claims、V3 reviewer_notes、API 加固字段）。
- 冻结二阶段主链路 `S2 → S3 → V2 → V4 → V3`、Opus supervisor 入口、Qdrant/Postgres 写入路径。
- 记录二阶段已知缺口（S6 / S7 / S8、Web UI、k8s、多租户、可观察性）。
- 列出三阶段候选能力但不改变二阶段实现范围。

验收标准：
- 二阶段接口变更必须先改 `schemas.py`，并在 freeze 文档中追加迁移说明。
- 文档中三阶段候选能力清晰，不与二阶段已实现能力重复。
- 主链路稳定为 ingestion → retrieval → S3 综合 → V2 校验 → V4 风格 → V3 审稿。

## 推荐实现顺序

1. `docs/phase_2_development_order.md`
2. `tests/fixtures/raw/`（zh PDF、zh DOCX、多页 fixture）
3. `tests/fixtures/ocr/`、`tests/fixtures/chunks/`、`tests/fixtures/retrieval/`
4. `tests/integration/test_phase0_fixture_chain.py`、`tests/integration/test_obj19_end_to_end.py`
5. `src/vibration_agent/schemas.py`
6. `src/vibration_agent/ingestion/bibliography.py`
7. `src/vibration_agent/ingestion/section_hierarchy.py`
8. `src/vibration_agent/ingestion/docx_parser.py`
9. `src/vibration_agent/ingestion/classify.py`
10. `src/vibration_agent/ingestion/pipeline.py`
11. `src/vibration_agent/retrieval/embeddings.py`
12. `configs/embeddings.yaml`
13. `src/vibration_agent/retrieval/dense.py`
14. `src/vibration_agent/storage/qdrant_client.py`
15. `src/vibration_agent/storage/qdrant.py`
16. `src/vibration_agent/retrieval/hybrid.py`
17. `db/migrations/`
18. `src/vibration_agent/storage/postgres_client.py`
19. `src/vibration_agent/storage/postgres.py`
20. `src/vibration_agent/storage/qa_logs.py`
21. `scripts/bench_large_corpus.py`
22. `tests/integration/test_large_corpus.py`
23. `src/vibration_agent/skills/s3_qa_summary.py`
24. `src/vibration_agent/agent/routing.py`
25. `src/vibration_agent/agent/model_registry.py`
26. `src/vibration_agent/skills/v2_citation_check.py`
27. `src/vibration_agent/orchestrator/tutor.py`
28. `src/vibration_agent/skills/v1_term_symbol_unit_normalizer.py`
29. `taxonomy/terms_zh_en.yaml`、`taxonomy/units.yaml`
30. `src/vibration_agent/skills/v3_reviewer.py`
31. `src/vibration_agent/agent/supervisor.py`
32. `src/vibration_agent/skills/s4_engineering_analysis.py`
33. `agent_skills/s4_engineering_analysis/SKILL.md`
34. `src/vibration_agent/skills/s5_formula_derivation.py`
35. `agent_skills/s5_formula_derivation/SKILL.md`
36. `apps/api/main.py`、`apps/api/middleware/`、`apps/api/auth.py`
37. `configs/api.yaml`
38. `.github/workflows/test.yml`
39. `tests/integration/test_phase2_end_to_end.py`
40. `scripts/manual_e2e.py`
41. `docs/phase_2_interface_freeze.md`
42. `docs/phase_2_deferred_and_polish_audit.md`
43. `docs/phase_2_progress.md`
44. `docs/architecture.md`

## 二阶段冻结结果占位

待 Obj19 完成后写入：
- 二阶段冻结链路：`S2 retrieval → S3 LLM synthesis → V2 citation check → V4 style → V3 reviewer (advisory)`，Opus supervisor 在 `extreme` 难度时接管。
- 冻结依据指向 `docs/phase_2_interface_freeze.md` 与 `docs/phase_2_deferred_and_polish_audit.md`。
- 一阶段冻结的 frozen 契约保持不变；二阶段新增字段以 optional 追加。
- 三阶段候选范围（S6 / S7 / S8、Web UI、k8s、多租户、可观察性）单独列在二阶段冻结文档中，不进入二阶段实现清单。
