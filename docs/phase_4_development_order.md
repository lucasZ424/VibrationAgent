# 四阶段开发顺序

Draft: 2026-06-12
Review update: 2026-06-15

## 四阶段边界

四阶段目标是在三阶段冻结接口之上，把已经具备真实模型推理、replay、预算门控和
manual live lane 的本地工程助手，扩展为更完整的振动工程研究、检索、推导和操作工作流。
四阶段不默认改变三阶段冻结的兼容基线：

```text
S2 -> S3 -> optional S4/S5 -> V2 -> V4 -> optional V3/supervisor
```

四阶段可以新增技能、检索能力、渲染能力和操作界面，但必须保留三阶段默认路径的可复现性。
除非某个目标显式记录迁移并通过验收，否则：

- live provider 调用继续 default-off，只能通过 manual/replay gate 进入。
- CI 继续使用 deterministic / replay 路径，不依赖 API key 或外部网络服务。
- 三阶段冻结的 schema、structured result、provider request、replay fixture、manual lane 和
  supervisor contract 仍然是兼容基线。
- 任何 schema、API response、chain order、retrieval contract、fixture layout、
  prompt schema、UI/API contract 或 provider request 变化，都必须记录在
  `docs/phase_4_migrations.md`。

四阶段不默认实现公开 SaaS、多租户权限、远程共享部署或生产级可观测性。它们可以作为后置可选目标，
但不能削弱本地个人部署、确定性回放和人工可审计能力。

四阶段也不允许在没有隔离评估的情况下同时替换 retrieval 和 synthesis。检索升级必须先独立衡量召回、
排序和证据缺失，再决定是否影响 S3/S4/S5 的质量评估。

## Review 后的设计决策

2026-06-15 review 后，四阶段在写 Obj1 代码前固化以下决策：

1. Obj5 选择 deterministic V2 hardening 路径：paraphrase、unit、range、sign、symbol
   support 仍由确定性规则和标注集校准。model-backed entailment 不属于 Obj5；若未来需要，
   必须作为新的 default-off、replay-first 目标单独设计。
2. Obj1 必须产出数值化 gate 所需标签：V2 positive/negative calibration set、retrieval
   recall targets、unsupported-answer regression cases。Obj4 和 Obj5 不再用纯定性判断放行。
3. Obj6 的 manual live external search 源先命名为 Semantic Scholar Graph API，arXiv API
   作为 arXiv-only secondary source。两者都必须 manual-only、default-off，并有 replay
   fixture 与 redaction 规则。
4. Obj10 的 rendered DOCX backend 先命名为 headless LibreOffice (`soffice`)。缺失该工具时
   保留三阶段 logical-page fallback；CI 不要求安装 LibreOffice。
5. 新增 S6/S7/S8 routing activation gate。若该目标未通过，S6/S7/S8 只作为显式调用的
   default-off skills 存在，不宣称普通查询可自动使用它们。
6. 新增 backend interface freeze。后端检索、V2、S6/S7/S8、rendering 和 CAS spike 可先冻结，
   不被 UI 或 remote hardening 的风险绑住。
7. 原 deployment/observability 目标拆分为 local-first essentials 和 remote/shared hardening
   decision。后者默认 deferred，除非出现明确远程部署决策。

## 执行模型与风险控制

四阶段继续保持单目标粒度执行。每个目标完成后必须：

1. 更新 `docs/phase_4_progress.md`。
2. 如有 contract / schema / replay / retrieval / UI / provider 变化，更新
   `docs/phase_4_migrations.md`。
3. 由用户 review 后，在 `docs/issue_log_p4/issues_objN.txt` 记录发现和处理结论。
4. 运行该目标对应的 replay / deterministic fallback / schema / regression 测试。
5. 明确是否允许进入下一个目标。

Issue log 是用户 review artifact。实现 agent 不应主动生成或编辑 issue log，除非用户显式要求。

风险控制原则：

1. 所有新增 live 或 network 能力必须 default-off，并有 replay 或 deterministic fallback。
2. 所有 provider / search / embedding / rendering client 必须 lazy import 或 runtime-discovered；
   fast suite 不依赖可选 SDK、外部命令或网络服务。
3. 所有模型输出仍必须经过结构化 schema 和 V2/V4 兼容路径，不允许绕过 citation check。
4. Retrieval 改动必须先有 recall/eval 数据，再考虑替换默认检索路径。
5. Qdrant 维度、embedding model 或 chunk metadata 改动必须先记录 migration，再 reindex。
6. 新技能 S6/S7/S8 必须先作为 default-off skill 接入，不能直接进入普通问答主链。
7. LaTeX/MathML、symbolic proof、DOCX rendered pagination 都是独立 contract，不作为
   S5 或 ingestion 的顺手格式化改动。
8. UI 和部署能力必须晚于后端 contract 与 eval gate；UI 不应成为隐藏 contract drift 的来源。

## 排序原则

1. 先建立四阶段记录、迁移和 issue-log 基线，避免后续扩展无审计轨迹。
2. 先扩展 replay eval、V2 calibration labels、retrieval targets 和 large-corpus baseline，
   再改变 retrieval 或新增高权限模型技能。
3. 先隔离 retrieval 召回问题，再评估 embedding/Qdrant 替换，避免 synthesis 质量无法归因。
4. 先加强 deterministic V2 evidence support，再扩大答案权限。
5. 先以 replay/default-off 方式接入 S6/S7/S8，再通过独立 routing activation gate 决定
   是否进入普通用户流。
6. 先冻结公式渲染、资产锚定和页面定位 contract，再做 UI 展示。
7. 后端能力先做 backend freeze；Web UI 和 local-first observability 后置。
8. remote/shared hardening 只在明确部署决策后进入实施，否则记录为 deferred。

## 目标开发清单

### 0. 固化四阶段执行基线

涉及代码/文档：

- `docs/phase_4_development_order.md`
- `docs/phase_4_progress.md`
- `docs/phase_4_migrations.md`
- `docs/issue_log_p4/`
- `README.md`
- `docs/architecture.md`

功能板块：

- 明确四阶段目标、非目标、风险控制和单目标执行模型。
- 建立四阶段 progress / migrations / issue log 记录位置。
- 明确三阶段冻结接口仍是四阶段兼容基线。
- 吸收 2026-06-15 review 的五类 load-bearing 修正。

验收标准：

- 文档中能判断哪些能力属于四阶段，哪些能力仍然后置。
- 四阶段所有后续目标都有 progress、migration 和 issue-log 的记录入口。
- README 和 architecture 指向四阶段规划，但不改变三阶段冻结 runtime 行为。
- Obj1 代码开始前，Obj5 路径、数值化 gates、外部依赖、routing activation、backend freeze
  和 local/remote hardening 边界已经写清楚。

### 1. Broader replay eval、V2 calibration 与 large-corpus baseline

涉及代码/文档：

- `scripts/llm_eval.py`
- `tests/fixtures/llm/eval_*.json`
- `tests/fixtures/eval/v2_calibration/`（新增）
- `tests/fixtures/retrieval/targets.json`（新增）
- `tests/eval/test_llm_eval.py`
- `scripts/bench_large_corpus.py`
- `docs/phase_4_progress.md`

功能板块：

- 把三阶段 Obj8 的最小 golden eval 扩展为更广的 replay eval 集。
- 覆盖中文/英文工程问答、公式推导、unsupported units、supervisor、retrieval miss 等场景。
- 建立 V2 positive/negative calibration set，用于后续衡量 false negative 和 over-block。
- 建立 retrieval recall target labels，至少记录 query、expected chunk/doc/page、required top-k。
- 提供 operator-run large-corpus baseline，用于真实语料上的性能和质量基线。
- large-corpus 不进入 fast CI，不需要 live API。

验收标准：

- replay eval 输出 per-case pass/fail 和 aggregate scorecard。
- 至少一个故意 unsupported answer 会被 regression 捕获。
- V2 calibration set 同时包含 supported paraphrase、unit/range/sign variants 和 unsupported
  claims，并能输出 precision/recall 或等价 confusion summary。
- retrieval targets 能被 Obj2 直接消费，并至少定义 `top_k_recall@5` 与 `top_k_recall@10`。
- large-corpus 命令可人工运行，并明确排除在默认 fast tests 之外。
- 运行不需要 API key。

### 2. Retrieval recall audit 与数据集

涉及代码/文档：

- `tests/fixtures/retrieval/`
- `scripts/retrieval_eval.py`（新增）
- `src/vibration_agent/retrieval/`
- `docs/phase_4_progress.md`

功能板块：

- 使用 Obj1 的 retrieval labels 建立小型 recall audit set。
- 对代表性振动问题统计正确 chunk 是否进入 top-k。
- 报告中分离 retrieval failure 与 synthesis failure。

验收标准：

- retrieval eval 可离线运行，不触发 live provider。
- 报告包含 top-k recall、missing evidence cases 和 per-query diagnostics。
- 现有 token-feature / dense fallback 仍可用。
- Obj4 replacement gate 至少有一个明确阈值，例如当前方案在关键 query 上
  `top_k_recall@10` 低于目标阈值，或 manual review 标记的 missing evidence case 达到
  文档定义的数量。

### 3. Optional embedding provider upgrade

涉及代码/文档：

- `src/vibration_agent/retrieval/embeddings.py`
- `configs/embeddings.yaml`
- `src/vibration_agent/schemas.py`（如 schema 变化）
- `tests/unit/test_embeddings.py`
- `docs/phase_4_migrations.md`

功能板块：

- 在显式配置后新增可选 embedding provider，例如本地 sentence-transformers 或 OpenAI embeddings。
- provider 缺失、不可用、超预算或网络失败时，降级到冻结的 retrieval fallback。
- 存储 embedding model、dimension、provider、version metadata。

验收标准：

- provider load failure 有 warning 并降级，不破坏默认问答。
- 测试覆盖 batch embedding、cache hit、metadata 和 fallback。
- embedding dimension 改动先记录 migration，再进入 Qdrant schema / reindex。

### 4. Qdrant reindex 与 retrieval replacement gate

涉及代码/文档：

- `src/vibration_agent/storage/qdrant.py`
- `src/vibration_agent/retrieval/dense.py`
- `src/vibration_agent/retrieval/hybrid.py`
- `tests/integration/test_qdrant_roundtrip.py`
- `docs/phase_4_migrations.md`

功能板块：

- 只有在 Obj2/Obj3 证明 recall gap 且存在 embedding candidate 后，才执行 Qdrant reindex。
- Qdrant 不可用时保留现有 fallback retrieval。
- hybrid retrieval 报告 dense/sparse contribution，便于归因。

验收标准：

- Qdrant 不可用时 integration tests clean skip。
- Qdrant failure 不破坏 CLI/API answer flow。
- replacement 只有在 Obj2 定义的 recall gate 改善达到阈值时才能启用；否则记录明确的
  non-replacement 决策。
- 报告必须区分 BM25/token、dense、hybrid contribution，避免把 synthesis 改善误算为 retrieval 改善。

### 5. Deterministic V2 evidence support hardening

涉及代码/文档：

- `src/vibration_agent/skills/v2_citation_check.py`
- `tests/unit/test_v2_citation_check.py`
- `tests/fixtures/eval/v2_calibration/`
- `docs/phase_4_migrations.md`

功能板块：

- 在确定性范围内把 V2 从 string-based significant-item check 扩展到更强的证据支持判断。
- 加入 paraphrase、unit variants、ranges、signs 和常见振动符号校准案例。
- 对无法绑定证据的 model claims 继续 fail-closed。
- 不引入 model-backed entailment checker；该能力如需进入，必须另立 default-off replay objective。

验收标准：

- 在 Obj1 V2 calibration set 上减少 false negative，同时 precision 不低于文档定义阈值。
- 对现有有效 replay eval 不明显 over-block；over-block 数量必须在 scorecard 中显式列出。
- 新 structured result 字段如有增加，必须记录 migration。
- 三阶段 deterministic baseline 测试保持通过。

### 6. S6 literature search prototype

涉及代码/文档：

- `src/vibration_agent/skills/s6_literature_search.py`（新增）
- `agent_skills/s6_literature_search/SKILL.md`（新增）
- `prompts/skills/s6_literature_search.md`（新增）
- `tests/unit/test_s6_literature_search.py`（新增）
- `tests/fixtures/literature/`（新增）
- `docs/phase_4_migrations.md`

功能板块：

- 新增 S6，作为 default-off 的文献检索与 citation capture 技能。
- replay fixture 是规范输入；manual live source 先限定为 Semantic Scholar Graph API，arXiv API
  作为 arXiv-only secondary source。
- live external search 必须经过显式 manual gate，不进入 CI。
- S6 产出的 claims 不能绕过 V2/V4 citation 约束进入最终答案。

验收标准：

- S6 可从 replay fixture 返回结构化 literature candidates，至少包含 title、authors/year、
  venue/source、doi/arxiv_id/url、abstract/snippet、retrieval_source 和 evidence anchors。
- live/network 缺失时 clean fallback。
- replay/capture redaction 覆盖 API key、bearer token、local path 和 long raw abstract/text。
- 普通 chain routing 默认不调用 S6。

### 7. S7 model selection prototype

涉及代码/文档：

- `src/vibration_agent/skills/s7_model_selection.py`（新增）
- `agent_skills/s7_model_selection/SKILL.md`（新增）
- `prompts/skills/s7_model_selection.md`（新增）
- `tests/unit/test_s7_model_selection.py`（新增）

功能板块：

- 基于现有证据、约束和不确定性，为振动问题推荐分析模型或建模路线。
- 输出是 advisory，不执行建模 pipeline。
- 每个推荐必须区分证据支持、假设和限制。

验收标准：

- 输出结构化，并引用支撑每个 model recommendation 的 evidence 或 assumption。
- 证据不足时返回明确 limitation。
- CI 不发生 live provider call。

### 8. S8 experiment advice prototype

涉及代码/文档：

- `src/vibration_agent/skills/s8_experiment_advice.py`（新增）
- `agent_skills/s8_experiment_advice/SKILL.md`（新增）
- `prompts/skills/s8_experiment_advice.md`（新增）
- `tests/unit/test_s8_experiment_advice.py`（新增）

功能板块：

- 针对振动诊断生成 evidence-bound 的测量、传感器布置、验证和安全边界建议。
- 区分 confirmed facts、assumptions、required measurements 和 safety/limits。
- 不输出证据不支持的数值阈值。

验收标准：

- 输出结构化，且安全/限制信息明确。
- unsupported numeric thresholds 被 V2 阻断或由技能主动省略。
- 技能保持 default-off，直到 routing 显式扩展。

### 9. S6/S7/S8 routing activation gate

涉及代码/文档：

- `src/vibration_agent/orchestrator/tutor.py`
- `src/vibration_agent/agent/routing.py`
- `src/vibration_agent/config.py`
- `tests/unit/test_routing.py`
- `tests/integration/test_tutor_orchestrator.py`
- `docs/phase_4_migrations.md`

功能板块：

- 为 S6/S7/S8 建立显式 routing activation 决策点。
- 默认仍不自动调用新技能；只有在配置、用户模式或明确 query intent 满足文档化规则时，才允许进入
  controlled routed lane。
- 如果 eval 或 V2/V4 gate 不足，则记录 Phase-5 deferral，而不是隐式宣称普通查询已 fully functional。

验收标准：

- routing policy 文档化，且每个可触发路径都有 deterministic/replay 测试。
- 未启用 routing flag 时，三阶段默认问答链路完全不变。
- 启用后，新技能输出仍进入 V2/V4-bound 兼容路径，或返回显式 handoff/limitation。
- 若不启用，progress 中必须明确记录 S6/S7/S8 仍为 explicit-call-only。

### 10. Rendered DOCX pagination 与 rich asset anchoring

涉及代码/文档：

- `src/vibration_agent/ingestion/docx_parser.py`
- `src/vibration_agent/ingestion/assets.py`
- `src/vibration_agent/schemas.py`（如 schema 变化）
- `tests/unit/test_docx_parser.py`
- `docs/phase_4_migrations.md`

功能板块：

- 将 DOCX 从逻辑 page 1 逐步升级到 rendered 或 layout-derived anchors。
- rendering backend 先限定为 headless LibreOffice (`soffice`) docx-to-pdf；缺失时保留三阶段逻辑分页 fallback。
- 加强 figure/table/formula asset anchoring，支撑 citation 和答案展示。
- 缺少 layout 信息时保留三阶段逻辑分页 fallback。

验收标准：

- 现有 DOCX/PDF ingestion contract 向后兼容。
- 新 asset/page 字段为 optional，并记录 migration。
- 测试覆盖 missing LibreOffice、missing layout data 与 fallback。
- CI 不要求安装 LibreOffice；rendered lane 必须可 skip 或 fixture replay。

### 11. LaTeX/MathML rendering contract

涉及代码/文档：

- `src/vibration_agent/skills/s5_formula_derivation.py`
- `src/vibration_agent/skills/v4_style.py`
- `src/vibration_agent/schemas.py`（如公式资产结构化）
- `tests/unit/test_s5_derivation.py`
- `tests/unit/test_v4_style_skill.py`

功能板块：

- 建立稳定的公式渲染表示，不把它等同于 symbolic proof。
- CLI/API 客户端继续保留 plain-text fallback。
- 无效公式 markup fail loud，并降级为 plain text。

验收标准：

- 公式输出可渲染或省略，且不破坏 citations。
- invalid markup 有测试覆盖。
- 新 structured formula 字段记录 migration。

### 12. Symbolic proof / CAS feasibility spike

涉及代码/文档：

- `docs/phase_4_symbolic_proof_spike.md`（新增）
- `tests/unit/test_s5_derivation.py`（按需）

功能板块：

- 评估轻量 symbolic checker 或 CAS 是否值得用于 S5。
- 明确支持的公式类别、不支持场景、依赖成本和 fallback 行为。
- 该目标默认是 spike，不直接引入 mandatory CAS dependency。

验收标准：

- spike 文档能支持是否进入 production objective 的决策。
- 没有单独目标前，不新增强制 CAS 依赖。

### 13. Backend interface freeze

涉及代码/文档：

- `docs/phase_4_backend_interface_freeze.md`（新增）
- `docs/phase_4_deferred_and_polish_audit.md`（新增或更新）
- `docs/phase_4_migrations.md`
- `docs/phase_4_progress.md`
- `README.md`
- `docs/architecture.md`

功能板块：

- 冻结 Obj1-Obj12 已完成的后端 contract、eval gates、retrieval gates、S6/S7/S8 状态、
  V2 hardening 边界、rendering contract 和 CAS spike 结论。
- 明确哪些能力已经进入普通 routing，哪些仍是 explicit-call-only 或 Phase-5 deferred。
- 允许后端在 UI/local observability 前形成稳定基线。

验收标准：

- 所有后端 contract change 都能在 migrations 中追溯。
- full non-large suite、replay eval、retrieval eval 和相关 focused tests 有记录。
- 文档能判断后续 UI 或 observability 变更是否破坏后端冻结接口。

### 14. Web UI read-only operator surface

涉及代码/文档：

- `apps/ui/`（按需）
- `apps/api/main.py`
- `README.md`
- `tests/` UI/API smoke tests（按需）

功能板块：

- 新增 local-first、read-only 操作界面，用于提问、查看 citations、chain steps、warnings、
  supervisor status 和 cost metadata。
- 管理功能、多用户权限和远程部署不进入该目标。

验收标准：

- UI 不需要 live provider keys。
- citation、warnings、supervisor status 和 cost metadata 可见。
- UI 依赖的 API contract 先记录 migration。

### 15. Local-first observability essentials

涉及代码/文档：

- `configs/`
- `apps/api/`
- `.github/workflows/`
- `docs/`

功能板块：

- 为本地个人部署增加结构化日志、health probe、redaction tests 和基本 operator diagnostics。
- 保留 localhost 默认易用性。
- logs 不泄露 API key、prompt secrets、long raw text 或本地绝对路径。

验收标准：

- local deterministic tests 和 manual workflows 默认不变。
- health probe 不要求外部网络、数据库或 live provider。
- observability 字段有脱敏测试或审查。

### 16. Remote/shared hardening decision

涉及代码/文档：

- `docs/phase_4_deferred_and_polish_audit.md`
- `docs/phase_5_scope.md`（如需要）
- `apps/api/`（只有明确实施时）
- `configs/`（只有明确实施时）

功能板块：

- 对 authz、durable rate limiting、remote/shared metrics、多用户部署做实施或 defer 决策。
- 默认记录为 deferred，除非 stakeholder 明确改变 local-first 产品定位。
- 若实施，必须先写 API/security migration，再更新 runtime。

验收标准：

- 文档明确 remote/shared hardening 是 implemented、deferred 还是 Phase-5 candidate。
- 若 deferred，不改变本地默认行为。
- 若 implemented，hardened mode 必须 opt-in，且有 redaction/security tests。

### 17. Phase-4 final interface freeze

涉及代码/文档：

- `docs/phase_4_interface_freeze.md`（新增）
- `docs/phase_4_deferred_and_polish_audit.md`
- `docs/phase_4_backend_interface_freeze.md`
- `docs/phase_4_migrations.md`
- `docs/phase_4_progress.md`
- `README.md`
- `docs/architecture.md`

功能板块：

- 冻结四阶段已完成 contract。
- 汇总 accepted residual risks 和 Phase-5 candidate backlog。
- 验证 full non-large suite、replay eval、retrieval eval 和相关 manual commands。

验收标准：

- 所有四阶段 contract change 都能在 migrations 中追溯。
- README 和 architecture 指向四阶段 freeze。
- 文档能判断未来变更是否破坏四阶段冻结接口。
- final freeze 明确引用 backend freeze，并说明 UI/observability 是否改变后端接口。

## 验证策略

- Fast CI：deterministic / replay tests only；禁止 live API。
- Nightly：full non-large suite、replay eval、retrieval eval 和 artifact scorecards。
- Local manual：live provider、large-corpus、external-search 和 rendered DOCX 只通过显式 operator command。
- Per-objective gate：每个目标必须运行 touched skill/contract 的 focused tests，以及必要的附近兼容测试。
- Numeric gates：Obj1 必须提供 Obj4/Obj5 使用的 labeled targets；后续目标不得用纯定性口径替代。

## 跨目标风险与缓解

- Retrieval 与 synthesis 同时变化会掩盖归因：保持独立目标和独立 eval。
- 更强 V2 checks 可能 over-block 合法工程转述：用 Obj1 calibration set 的 positive/negative cases 校准。
- Model-backed entailment 会改变 CI 与 replay 边界：不放入 Obj5，必须另立 default-off objective。
- S6/S7/S8 可能过快扩大答案权限：默认关闭，先有 citations、schema、eval 和 routing activation gate。
- UI/deployment 可能制造隐式 contract drift：后置，并要求 API migration 先行。
- Live API 与 external search 会带来非确定性、成本和 redaction 风险：继续使用 replay gate、budget guard
  和 manual-only lane。
- Rendered DOCX 依赖外部工具：LibreOffice 缺失时 fail loud 并回落到 logical-page fallback。

## 已确认的决策

1. 四阶段从三阶段冻结接口出发，不直接重写三阶段默认链路。
2. Issue log 由用户 review 后写入，默认不由实现 agent 生成。
3. `docs/issue_log_p4/` 目录由 `.gitignore` 排除，不作为版本跟踪对象。
4. Retrieval/embedding 升级必须先有 recall audit，再做 provider 或 Qdrant 替换。
5. S6/S7/S8 均作为 default-off prototype 进入，不能在没有 eval、V2/V4 约束和 routing gate 前进入普通链路。
6. Obj5 采用 deterministic evidence-support hardening；model-backed entailment 留给单独目标。
7. Semantic Scholar Graph API、arXiv API 和 LibreOffice 都是 optional/manual dependencies，不进入 fast CI 前提。
8. Backend freeze 早于 UI/local observability/final freeze。
9. Remote/shared hardening 默认 deferred，除非产品定位明确从 local-first 改变。
