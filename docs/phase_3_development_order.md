# 三阶段开发顺序

Draft: 2026-06-08

## 三阶段边界

三阶段目标是在二阶段冻结接口之上，把已经落地的确定性脚手架升级为
可用的工程助手。三阶段不改变本地个人部署定位，不新增 Web UI、远程共享
部署、多租户权限或生产级可观测性；重点是让 S3、S4、S5 和 supervisor
从可注入的 deterministic scaffold 变成可试运行、可回放、可预算约束的
真实模型能力。

三阶段主线是：

```text
OpenAI S3/S4/S5 live/replay path
  -> V2 minimal faithfulness hardening
  -> Claude Opus 4.8 supervisor live/replay trial
  -> golden eval
  -> manual live validation
  -> Phase-3 freeze
```

三阶段默认链路仍保持二阶段冻结行为。所有模型能力都必须 default-off；
缺少 API key、预算不足、超时、schema 解析失败、模型拒答、replay fixture
缺失或 provider 异常时，必须降级到二阶段确定性输出并记录 warning，不允许
静默调用 live API。

三阶段不实现：

- S6 文献搜索。
- S7 模型选择。
- S8 实验建议。
- Web UI。
- k8s / 远程共享部署 / 多租户权限。
- 生产级可观测性栈。
- 深度语义蕴含证明。
- LaTeX/MathML 生成和完整符号证明。
- OpenAI embeddings / retrieval 替换，除非三阶段 eval 明确证明 retrieval 是瓶颈。

S6/S7/S8 仍然作为四阶段候选能力。三阶段可以被视为“可用工程助手”的第一版：
先让已有工程链路具备真实模型推理、审稿和修正能力，再进入更广义的
文献、模型选择和实验设计能力。

## 执行模型与风险控制

三阶段保持单个目标粒度执行。每个目标完成后必须：

1. 更新 `docs/phase_3_progress.md`。
2. 在 `docs/issue_log_p3/issues_objN.txt` 记录 review 发现和处理结论。
3. 运行该目标对应的 replay / deterministic fallback / schema 约束测试。
4. 明确是否允许进入下一个目标。

风险控制原则：

1. 所有 live API 路径必须有 replay 路径，CI 禁止 live API 调用。
2. 所有 provider client 必须 lazy import，fast suite 不依赖 OpenAI 或 Anthropic SDK。
3. 所有模型调用必须经过预算门控；成本字段只作为本地估算和自用运行记录，不作为账单事实。
4. 所有模型输出必须结构化。schema parse failure、refusal、unknown replay hash
   都必须 fail loud 并降级，不允许拼接半结构化文本继续运行。
5. 所有 contract 变更遵守二阶段 freeze 规则：先改 `schemas.py`，再记录
   `docs/phase_3_migrations.md`，再更新 fixtures/tests，最后改调用方。
6. V2 hardening 必须早于真实 S3/S4/S5 默认启用；模型输出只有通过 V2 后
   才能进入最终答案。
7. Claude Opus 4.8 supervisor 只作为 extreme / V3-flagged 路径，不参与普通问题。
8. OpenAI embeddings / retrieval 替换不进入默认计划，避免同时改变 retrieval
   和 synthesis，导致质量问题无法归因。

## 排序原则

1. 先建立三阶段记录、迁移和 issue log 基线，避免后续能力开发无审计轨迹。
2. 先建立 provider client、record/replay 和 live-call guard，再开发模型能力。
3. 先建立预算和成本估算，再允许任何 live call。
4. 先用 replay/fake LLM output 压测 V2，再接入真实 S3。
5. 先完成 S3/S4/S5 的 replay 能力，再做 Claude Opus 4.8 supervisor 试运行。
6. 先建立小型 golden eval，再扩展到 manual live validation。
7. 最后冻结三阶段接口，并把 S6/S7/S8 等能力统一进入四阶段规划。

## 目标开发清单

### 0. 固化三阶段执行基线

涉及代码/文档：

- `docs/phase_3_development_order.md`
- `docs/phase_3_progress.md`（新增）
- `docs/phase_3_migrations.md`（新增）
- `docs/issue_log_p3/`（新增）
- `README.md`

功能板块：

- 明确三阶段目标、非目标、风险控制和单目标执行模型。
- 建立三阶段 progress / migrations / issue log 记录位置。
- 明确 CI replay-only、manual live-only、default-off 的执行纪律。

验收标准：

- 文档中能判断哪些能力属于三阶段，哪些能力推迟到四阶段。
- 三阶段所有后续目标都有 progress、migration 和 issue log 的记录入口。
- README 中说明三阶段 live API 只允许本地 manual lane，不进入 CI。

### 1. Provider client 与 record/replay 基线

涉及代码/文档：

- `src/vibration_agent/llm/openai_client.py`（新增）
- `src/vibration_agent/llm/anthropic_client.py`（新增）
- `src/vibration_agent/llm/replay.py`（新增）
- `src/vibration_agent/llm/__init__.py`
- `src/vibration_agent/config.py`
- `configs/llm.yaml`
- `tests/unit/test_llm_replay.py`
- `tests/unit/test_openai_client.py`
- `tests/unit/test_anthropic_client.py`
- `tests/fixtures/llm/`

功能板块：

- 新增 OpenAI client，用于 S3/S4/S5 结构化输出。
- 新增 Anthropic client，用于 Claude latest / Claude Opus 4.8 supervisor
  review / correction。
- 新增 ReplayClient，根据稳定 request hash 读取 captured fixture。
- 新增 RecordingClient，仅在 manual lane 调用 live API 并写入脱敏 fixture。
- 新增 pytest autouse guard，测试环境构造 live client 时直接失败。
- `LlmSettings` 增加 provider、model、temperature、max_tokens、timeout、
  reasoning_effort、text_verbosity、budget、replay_dir、capture_enabled、
  API key env 名称等字段。

验收标准：

- replay hit 返回已捕获 response；replay miss 明确失败，不回退 live call。
- recording 写入 fixture 时不包含 API key。
- 测试证明 OpenAI / Anthropic SDK 均为 lazy import，fast suite 无 SDK 也能运行。
- 测试证明 pytest 中构造 live OpenAI 或 Anthropic client 会失败。
- fixture hash 包含 prompt version、schema version、model、temperature、
  max_tokens 和 request body。

### 2. Token budget 与成本估算

涉及代码/文档：

- `src/vibration_agent/llm/budget.py`（新增）
- `src/vibration_agent/config.py`
- `src/vibration_agent/storage/qa_logs.py`
- `src/vibration_agent/schemas.py`
- `db/postgres/migrations/004_phase3_llm_costs.sql`（按需新增）
- `tests/unit/test_budget.py`
- `tests/unit/test_qa_logs.py`

功能板块：

- 新增 `BudgetGuard`，支持 per-task token、per-session token 和可选 USD ceiling。
- live call 前 reserve budget；超预算返回 deny，调用方降级 deterministic fallback。
- 从 provider usage 读取 input/output tokens，写入 `structured_result.cost` 和
  `qa_logs.token_cost`。
- 成本字段作为本地估算；真实账单不由 Agent 判断。

验收标准：

- 超过 per-task budget 的请求不调用 provider，并返回 budget warning。
- LLM path 运行时 `token_cost` 有估算值；deterministic path 保持 null。
- budget 配置可通过 yaml/env 覆盖，默认沿用 4000/task、30000/session。
- 成本缺失或 provider 未返回 usage 时不会伪造精确成本，只记录 warning。

### 3. V2 LLM 输出安全门预加固

涉及代码/文档：

- `src/vibration_agent/skills/v2_citation_check.py`
- `tests/unit/test_v2_citation_check.py`
- `tests/fixtures/llm/v2_negative_*.json`

功能板块：

- 在真实 S3 默认启用前，用 replay/fake LLM output 压测 V2。
- 对 `synthesis_mode=="llm"` 的 claims 增加数字、单位、符号显著项交叉检查。
- claim 必须引用 visible chunk_id；数字/单位/符号必须能在引用 chunk 中定位。
- deterministic mode 保持二阶段行为，不扩大拦截范围。

验收标准：

- LLM claim 引用不存在 chunk 时被阻断。
- LLM claim 中出现引用 chunk 不支持的数字或单位时被阻断。
- 二阶段 V2 既有测试保持通过。
- strict mode 对 LLM 默认开启，对 deterministic 默认不改变。

### 4. S3 real LLM synthesis

涉及代码/文档：

- `src/vibration_agent/skills/s3_qa_summary.py`
- `prompts/skills/s3_qa_summary.md`
- `agent_skills/s3_qa_summary/SKILL.md`
- `tests/unit/test_s3_llm_synthesis.py`
- `tests/fixtures/llm/s3_*.json`

功能板块：

- `s3_enabled=true` 且 client 可用时，S3 通过 OpenAI 生成结构化输出。
- 输出 schema 至少包含 `answer` 和 `claims[]`；每个 claim 必须携带
  `text`、`chunk_id`、`doc_id`、`pages`、`evidence_type`。
- prompt 限定只能引用 S2 retrieval context 中 visible chunk_id。
- schema parse failure、refusal、timeout、budget deny、empty evidence 均降级。
- S3 输出继续经过 V2，不允许绕过 citation check。

验收标准：

- replay response 引用 visible chunks 时，S3 状态 ok 且通过 V2。
- replay response 引用不可见 chunk 或伪造数字时，V2 阻断并剥离 conclusion。
- `s3_enabled=false` 时输出与二阶段 deterministic regression 保持一致。
- pytest 不发生 live OpenAI 调用。

### 5. S4 real engineering analysis

涉及代码/文档：

- `src/vibration_agent/skills/s4_engineering_analysis.py`
- `prompts/skills/s4_engineering_analysis.md`
- `agent_skills/s4_engineering_analysis/SKILL.md`
- `tests/unit/test_s4_engineering.py`
- `tests/fixtures/llm/s4_*.json`

功能板块：

- `s4_llm_enabled=true` 时，S4 通过 OpenAI 生成工程意义、典型场景、
  失效模式、下一步行动建议。
- 输出必须落入现有 `engineering_meaning`、`premises`、`failure_modes`、
  `next_action` 等结构化字段。
- 所有工程判断必须引用通过 V2 的 claims 或 evidence。
- insufficient / mode mismatch 时保持二阶段 deterministic skip/fallback。

验收标准：

- replay response 能生成更丰富的工程分析，且所有关键判断有 citation 支撑。
- replay response 中伪造阈值或 unsupported numeric 时被 V2 阻断。
- `s4_llm_enabled=false` 时保持二阶段 deterministic 输出。
- pytest 不发生 live OpenAI 调用。

### 6. S5 real formula derivation 与 cycle-check 加固

涉及代码/文档：

- `src/vibration_agent/skills/s5_formula_derivation.py`
- `prompts/skills/s5_formula_derivation.md`
- `agent_skills/s5_formula_derivation/SKILL.md`
- `tests/unit/test_s5_derivation.py`
- `tests/fixtures/llm/s5_*.json`

功能板块：

- `s5_llm_enabled=true` 时，S5 通过 OpenAI 生成结构化 premise -> steps -> conclusion。
- derivation step 必须标记为 `evidence` 或 `axiomatic`。
- evidence step 必须能回连 citation；axiomatic step 必须显式说明适用条件。
- 补足二阶段 Obj15 carryforward：self-loop-only validator 升级为 DAG /
  topological cycle check。
- LaTeX/MathML 生成和完整符号证明仍 deferred。

验收标准：

- replay 多步推导能通过 V2 axiomatic/evidence handling。
- 2-node cycle 被拒绝。
- insufficient evidence 和 mode mismatch 保持二阶段 skip/fallback。
- `s5_llm_enabled=false` 时保持 deterministic 输出。

### 7. Claude latest / Claude Opus 4.8 supervisor 试运行与 correction executor

涉及代码/文档：

- `src/vibration_agent/agent/supervisor.py`
- `src/vibration_agent/llm/anthropic_client.py`
- `prompts/orchestrator.md`
- `tests/unit/test_supervisor_loop.py`
- `tests/fixtures/llm/supervisor_*.json`
- `scripts/llm_capture.py`

功能板块：

- 将 supervisor review client 接入 Anthropic Claude latest model；初始试运行
  目标为 Claude Opus 4.8。
- 实现真实 `GPT_CORRECTION` executor：根据 reviewer report 改写 candidate，
  而不是重复审查原 candidate。
- 保持 bounded loop，最大 2 次 correction。
- 仅 extreme / V3-flagged 任务触发；普通 query 不触发 supervisor live/replay。
- 无 API key、预算不足、provider 异常、replay miss 时降级为二阶段 fallback。

可行性评估：

- 可行。二阶段已经有 supervisor seam、review report、invocation logging 和
  fail-safe fallback；三阶段只需要补 provider client、record/replay、
  correction executor 和 manual live gate。
- 主要风险不是接入难度，而是输出一致性和成本；必须依赖结构化 review schema、
  replay fixture、BudgetGuard 和 extreme-only trigger 限制范围。
- Claude supervisor model 应保存在配置中，不写死在业务代码；实现时按
  Anthropic 官方当前 model id / latest alias 解析。

验收标准：

- replay review -> reject -> correct -> approve 路径能产生改进后的 candidate。
- budget deny / exception / replay miss 时 supervisor_status 进入 fallback。
- normal query 测试证明不会触发 Anthropic client。
- supervisor_status、supervisor_invocations、supervisor_action、token_cost 均被记录。
- manual live probe 在配置 API key 和预算后可以完成一次 Claude latest /
  Claude Opus 4.8 supervisor 试运行并写入脱敏 fixture。

### 8. Golden-output eval 最小集与 replay regression gate

涉及代码/文档：

- `tests/eval/`（新增）
- `scripts/llm_eval.py`（新增）
- `.github/workflows/test.yml`
- `tests/fixtures/llm/eval_*.json`

功能板块：

- 先建立 3-5 个小型 golden cases，再随 S3/S4/S5/supervisor 扩展。
- 最小集覆盖中文工程问答、英文工程问答、伪造数字 negative case、
  unsupported citation negative case、extreme supervisor case。
- nightly 使用 replay fixture 跑 eval，不调用 live API。
- 输出 faithfulness scorecard，作为 artifact 保存。

验收标准：

- eval replay set 全部通过。
- 故意 hallucinated fixture 会被 eval 捕获。
- scorecard 包含 citation faithfulness、unsupported numerics、scope/status、
  reviewer_notes presence。
- nightly CI 只运行 replay，不需要 API key。

### 9. Manual live validation 与 capture lane

涉及代码/文档：

- `scripts/manual_e2e.py`
- `scripts/llm_capture.py`（新增）
- `README.md`
- `docs/phase_3_progress.md`

功能板块：

- 提供本地手动 live call 入口，用于 OpenAI S3/S4/S5 和 Claude latest /
  Claude Opus 4.8 supervisor。
- live call 必须显式配置 API key、budget 和 capture 输出目录。
- capture 结果写入脱敏 replay fixture，供后续 CI / eval 使用。
- manual lane 输出 token usage 和本地成本估算。

验收标准：

- 无 API key 时走 replay 或 deterministic fallback，不报未处理异常。
- 有 API key 且 budget 允许时，可以完成一次真实 live probe。
- capture fixture 不包含 API key、长原文或敏感路径。
- 文档记录完整 PowerShell 命令，便于人工复跑。

### 10. Phase-3 interface freeze 与 Phase-4 planning

涉及代码/文档：

- `docs/phase_3_interface_freeze.md`（新增）
- `docs/phase_3_deferred_and_polish_audit.md`（新增）
- `docs/phase_3_migrations.md`
- `docs/phase_3_progress.md`
- `README.md`
- `docs/architecture.md`
- `src/vibration_agent/schemas.py`（按需）

功能板块：

- 冻结三阶段 LLM client contracts、structured output schemas、budget config、
  replay fixture layout、manual live lane 和 supervisor correction 行为。
- 汇总三阶段 accepted residual risks。
- 将 S6/S7/S8、Web UI、部署/可观测性、deep entailment、OpenAI embeddings、
  LaTeX/MathML、symbolic proof 等统一列为 Phase-4 candidates。

验收标准：

- 三阶段所有 schema/contract 变更在 migrations 中可追溯。
- README 和 architecture 指向三阶段 freeze。
- full non-large suite、replay eval 和 manual command 结果均记录在 progress。
- 文档能明确判断后续变更是否破坏三阶段冻结接口。

## 验证策略

- Fast CI：二阶段 deterministic suite + replay-only LLM tests；禁止 live API。
- Nightly：full suite + replay eval scorecard；禁止 live API。
- Local manual：`scripts/manual_e2e.py` / `scripts/llm_capture.py` 才允许 live API。
- Per-objective gate：每个目标必须跑对应 replay test、fallback regression、
  schema test，并写入 `docs/issue_log_p3/issues_objN.txt`。

## 跨目标风险与缓解

- 幻觉 citation / fabricated number：由 Obj3 V2 hardening 和 Obj8 negative eval 捕获。
- 成本膨胀：由 Obj2 BudgetGuard 和 manual-only live lane 限制。
- CI 非确定性：由 Obj1 replay harness 和 live-call guard 限制。
- prompt drift：fixture hash 绑定 prompt version / schema version / model settings。
- schema churn：遵守 schemas-first 和 `docs/phase_3_migrations.md`。
- supervisor 过度触发：仅 extreme / V3-flagged，普通 query 测试禁止调用。

## 已确认的决策

1. OpenAI S3/S4/S5 默认使用 OpenAI 最新高能力模型，配置为 high profile：
   `reasoning_effort=high`、`text_verbosity=high`。模型名写入配置，不写死
   业务代码；实现时按 OpenAI 官方当前 recommended/latest model 解析。
2. Claude supervisor 默认使用 Anthropic 最新 model；初始试运行目标保留
   Claude Opus 4.8。模型名写入配置，不写死业务代码；实现时按 Anthropic
   官方当前 model id / latest alias 解析。
3. 默认 token budget 维持 4000/task、30000/session；如 live probe 证明
   high profile 经常被预算拒绝，再通过配置调整，而不是在业务代码中放宽。
4. OpenAI embeddings / retrieval 本阶段保持 deferred，除非三阶段 eval 明确
   证明 retrieval 是瓶颈。

第 4 点的具体含义：

- 三阶段优先验证 generation/reasoning 链路：S3 生成、S4 工程分析、S5 推导、
  supervisor 审稿修正。retrieval lane 继续使用二阶段冻结的
  sentence-transformers/Qdrant/token-feature fallback，不同时替换 embedding provider。
- 这样做是为了保持问题可归因。如果同时更换 retrieval 和 synthesis，答案质量
  变好或变差时很难判断是召回变化、chunk 排序变化、prompt 变化，还是模型
  推理变化导致。
- 只有当 Obj8 golden eval 或 manual live validation 显示“模型有能力回答，
  但 S2 持续没有召回正确证据”时，才把 OpenAI embeddings / retrieval
  作为三阶段追加目标或四阶段前置目标。
- 触发条件应是可观测的：例如 top-k 证据缺失、正确 chunk 未进入候选集、
  citation faithfulness 通过但 recall score 低、或同一问题在手动提供正确
  chunk 后能稳定回答。
- 一旦触发，不应直接混入 S3/S4/S5 目标，而应单独拆为 retrieval objective：
  新增 OpenAI embedding client/replay、embedding schema migration、Qdrant
  dimension migration、retrieval regression/eval，再决定是否替换默认 dense lane。
