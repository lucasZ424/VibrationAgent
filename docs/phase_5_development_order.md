# 五阶段开发顺序

Draft: 2026-06-29
Review update: 2026-06-30
Status: APPROVED BASELINE - OBJ0 COMPLETE

## 五阶段定位

四阶段（含 R1–R3 本地迭代）已正式关闭并冻结（`docs/phase_4_progress.md`
Obj0–18）。R1–R3 用真实语料和真实问题暴露出一批**预期以外的 gap**。五阶段的
目标就是**系统性 close 这批 gap**，而不是新增产品面。

五阶段严格保持 **local-first / 单用户**，只有一个工作桶：

- **本地可靠性 + RAG 质量**（本阶段主体）：真实问题评测、检索质量、证据选择、
  答案合成、评分校准、语料与术语质量、后端可靠性；

共享、远程、公开和多用户部署无限期 defer，不是五阶段候选、目标或 entry gate。
只有用户先显式修订 `docs/vibration_agent_design.md`，才能在新的阶段规划中重新讨论；
五阶段内不得通过 objective 或 review finding 激活。

五阶段不默认改变四阶段冻结的兼容基线（默认链 `S2 -> S3 -> 可选 S4/S5 -> V2 ->
V4 -> 可选 V3/supervisor`）。任何 schema / retrieval / embedding / UI / provider
变化先记 `docs/phase_5_migrations.md` 再改调用方。

## post-P4 迭代暴露的 gap（五阶段的真实输入）

这些是 R1–R3 实跑出来的、有证据的问题，构成 Phase 5 entry gate 所需的
local-iteration 入场证据：

1. **检索对真实语料根本失效**：四阶段默认 embedding 是英文单语
   `all-MiniLM-L6-v2`，召不回中文为主的语料（64 个临界转速结果段落全在库里、
   parity 4436=4436，但中英文 query 的 ANN top-50 一个都召不回）。R3 反应式换成
   `paraphrase-multilingual-MiniLM-L12-v2` 才修复 → 需**形式化为受支持默认 + eval
   gate + 可复现 reindex 工具**。
2. **没有真实问题评测基线**：R1–R3 每一处改动都靠临场脚本验证，没有
   scorecard。RAG 计划的 Phase-0（`tests/fixtures/rag_qa/questions.json` +
   `scripts/rag_qa_eval.py`）从未落地 → **一切改动无法被门控**。
3. **答案评分是展示字段而非 gate，且口径会失真**：退化路径曾整段丢失评分（R3
   修过 `_early_return`）；跨语言 + 证据标签下 `question_coverage`/`readability`
   可能假低，而关键词重复的非回答也已复现 `score=1.0`（R3 只修正了部分词面口径，
   未做标签校准）。需要**人工 usable/unusable 标签校准**，并把 V2 faithfulness
   升为**硬门**而非无权重展示。
4. **S3 是纯抽取式合成**：可读性受限；对语义检索回的“词法不同但语义相关”的证据
   提不出 claim（临界转速结果门控曾因此判 insufficient）→ **受控 LLM 合成 lane**
   候选。
5. **检索架构受限**：BM25 被限制在 ANN 候选集内，缺少独立 lexical/ANN 召回度量、
   证据选择、邻接段落扩展与重排。
6. **语料 / 术语质量**：通用文件名（`document_*`）、OCR 乱码、chunk 不带
   `source_filename`（靠 `source_path` basename 兜底）、双语别名表只有 12 个族。
7. **后端可靠性 / 操作工效**：Qdrant `timeout=2s` 导致批量 reindex 被掐断
   （WinError 10053，已用长超时+分批临时绕过）；PG `qa_logs` 在 Postgres 未起时
   每次查询卡满 timeout；改后端代码需手动重启 operator；静态 JS 缓存（已加版本
   号 + no-store）。

## 设计决策（写 Obj1 代码前固化）

1. **评测先行**：先建真实问题 scorecard 并锁定 post-R3 基线，再动任何
   检索 / 合成 / 评分。无基线不改（沿用四阶段“先 eval 后改 retrieval”原则）。
2. **多语言 embedding 成为受支持默认**：reindex 必须先记 migration（model /
   dimension / 距离 / collection），再执行；维度变化才重建 collection；每次
   reindex 校验 PG:Qdrant parity。
3. **检索升级先独立衡量** lexical 与 ANN 召回，再决定融合或替换，沿用 Obj2/Obj4
   replacement gate（recall 不降且修复 ≥1 个真实 miss 才放行）。
4. **评分校准到人工标签**；V2 faithfulness 升为**硬门**（阻断不忠实答案），不再是
   无权重展示字段。
5. **任何 LLM 合成 / 重排** 一律 default-off + replay-first + 预算 / provider-model-
   usage-cost trace + V2 不降；CI 不构造 live provider、不依赖外网。
6. **不在无隔离评估下同时替换 retrieval 和 synthesis**，避免质量无法归因。
7. **远程 / 共享无限期 defer**：五阶段不保留远程 candidate、entry gate 或决策目标，
   不实现身份授权、租户隔离、公网入口、远程密钥、分布式限流或多用户审计。

## 标准开发文件

五阶段沿用前序阶段的统一文件职责：

1. `docs/phase_5_scope.md`：阶段边界、非目标、entry/exit gate。
2. `docs/phase_5_development_order.md`：目标顺序、依赖和验收规则。
3. `docs/phase_5_progress.md`：每个 Obj 的实现、验证、风险和放行状态。
4. `docs/phase_5_migrations.md`：schema、retrieval、provider、配置和 UI contract 迁移。
5. `docs/issue_log_p5/`：用户维护的 review artifact。

`phase_5_progress.md` 中每个目标统一使用以下字段，不增加自定义状态格式：

```text
## ObjN - Name
Goal:
Scope:
Definition of Done:
Dependencies:
Status: planned | in_progress | blocked | complete
```

## 目标开发清单

### 0. 五阶段基线与治理

涉及代码/文档：

- `docs/phase_5_scope.md`
- `docs/phase_5_development_order.md`
- `docs/phase_5_progress.md`
- `docs/phase_5_migrations.md`
- `docs/issue_log_p5/`
- `docs/vibration_agent_design.md`
- `docs/architecture.md`
- `README.md`

功能板块：

- 固化 Phase 5 的本地单用户 RAG 可靠性边界和 Obj0–Obj10 执行顺序。
- 登记 Phase-4 R3 起始基线：多语言 ANN、评分 heuristic、answer-first UI、模型预算。
- 建立 scope、development order、progress、migrations 四类 canonical 文档职责。
- 将共享、远程、公开和多用户能力设为无限期 defer，移除 entry gate 和候选目标。
- 规定 issue log 由用户维护，implementation agent 不主动生成或修改。

验收标准：

- 四个 canonical Phase-5 文档存在，互相引用路径有效，Obj 编号一致。
- `phase_5_progress.md` 的 Obj0–Obj10 均包含 `Goal / Scope / Definition of Done /
  Dependencies / Status`。
- 核心设计、architecture、README 和 Phase-5 文档对部署边界没有冲突。
- `phase_5_migrations.md` 明确 migration-first、replay-first、V2 hard gate 和 parity 纪律。
- 本目标只改文档，不改变 runtime、schema、数据库、provider 或 API 行为。

依赖与放行条件：

- 依赖：Phase 4 已正式关闭。
- 用户 review 并批准 Obj0 后，才允许 Obj1 建立评测基线。

### 1. 真实问题评测台与 post-R3 基线

涉及代码/文档：

- `tests/fixtures/rag_qa/questions.json`（新增）
- `scripts/rag_qa_eval.py`（新增）
- `tests/eval/test_rag_qa_eval.py`（新增）
- `tests/fixtures/retrieval/`
- `docs/phase_5_progress.md`
- `docs/phase_5_migrations.md`（仅在评测 contract 形成公共依赖时）

功能板块：

- 建立定义、机理、比较、诊断、流程、标准和公式七类真实工程问题。
- 每类至少包含中文和英文样例，并记录 corpus snapshot、期望 doc/page/chunk、关键事实、
  完整性 rubric 和允许的 evidence boundary。
- 运行真实 S2→S3→V2→V4 链，记录 retrieval hits、答案、citations、V2 状态和耗时。
- 报告 recall@k、答案完整率、V2 faithfulness、句子完整率和 miss category。
- 将 miss 分成 retrieval、ranking、cross-doc、synthesis、terminology、corpus-quality。
- 固化 post-R3 baseline，后续目标使用同一 fixture 和 corpus version 比较。

验收标准：

- fixture 至少覆盖 7 类意图 × 2 种语言，且每个 case 有稳定 `case_id` 和人工 rubric。
- runner 可离线、确定性运行，不构造 live provider，不需要 API key 或外部网络。
- scorecard 同时输出 per-case 结果和 aggregate 指标，至少包含 recall@5、recall@10、
  completeness rate、V2 faithfulness rate、latency 和 miss counts。
- 同一 corpus/config 连续运行两次，确定性字段结果一致。
- baseline 报告记录 corpus 标识、embedding model/dimension、retrieval config 和 Git commit。
- dominant miss category 被量化；Obj2–Obj6 的具体 scope 必须引用这些数据，不凭猜测扩展。

依赖与放行条件：

- 依赖：Obj0。
- baseline 和 fixture 经 review 后，才允许 Obj2–Obj8 修改评分、检索、合成或 corpus。

### 2. 答案评分校准与 V2 硬门

涉及代码/文档：

- `src/vibration_agent/orchestrator/tutor.py`
- `src/vibration_agent/skills/v2_citation_check.py`
- `src/vibration_agent/schemas.py`（如结构变化）
- `tests/unit/test_tutor_orchestrator.py`
- `tests/unit/test_v2_citation_check.py`
- `tests/fixtures/rag_qa/questions.json`
- `tests/fixtures/eval/v2_calibration/`
- `scripts/rag_qa_eval.py`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 为 Obj1 问题集增加人工 `usable / unusable` 标签和判定理由。
- 将 question coverage 改为问题意图/槽位覆盖，而不是简单关键词出现率。
- 将 evidence relevance 绑定到被引用 chunk 的真实 retrieval score/rank，不使用文档置信度替代。
- 按问题类型定义 completeness rubric，避免“存在 conclusion/citation”自证完整。
- 保留 readability 独立指标，但不把行尾标点等同于答案可用性。
- V2 faithfulness 作为硬门：不忠实或未核验答案不能获得通过级总分。
- 明确评分仅用于诊断、warning 还是 acceptance gate，并记录 threshold 选择依据。

验收标准：

- 已复现的关键词循环非回答不能再获得通过级评分。
- `faithfulness_status != ok` 时，总体结果不能显示为质量通过。
- 人工可用与不可用 case 都有 regression；报告包含 confusion matrix 或等价分类统计。
- threshold 由 Obj1 标签集校准并在 progress 中批准，不在实现前硬编码猜测值。
- V2 现有 positive/negative calibration 无 false-allow 回归，unsupported numeric gate 不下降。
- early-return、跨语言、无 citation、低 retrieval score 和完整工程回答均有测试。

依赖与放行条件：

- 依赖：Obj1。
- 评分/V2 gate 通过校准 review 后，才作为 Obj3–Obj6 的验收量尺。

### 3. 多语言检索形式化与可复现 reindex

涉及代码/文档：

- `configs/embeddings.yaml`
- `src/vibration_agent/retrieval/embeddings.py`
- `src/vibration_agent/storage/ingestion.py`
- `src/vibration_agent/storage/qdrant.py`
- `src/vibration_agent/storage/qdrant_client.py`
- `scripts/` 下的 reindex 工具（新增或整理）
- `tests/unit/test_embeddings.py`
- `tests/unit/test_qdrant.py`
- `tests/integration/` 下的 storage/reindex tests
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 将 `paraphrase-multilingual-MiniLM-L12-v2`、384 维和 cosine distance 固化为受支持基线。
- 提供显式、可恢复、可分批、带进度和错误汇总的 corpus reindex 命令。
- 区分同维模型覆盖写入与维度变化后的 collection recreate，禁止静默混用向量空间。
- Qdrant payload 保留 embedding model/version 和 source metadata。
- reindex 前后核对 Postgres embeddable chunks、Qdrant points 和按 source type 计数。
- 在 Obj1 双语问题上记录 cross-lingual ANN recall 与冷启动 latency。

验收标准：

- reindex 工具支持 dry-run、batch size、timeout、resume 或幂等重跑，并有单元测试。
- 中断后重跑不会重复累积 point；相同 chunk id 仍稳定覆盖同一 UUID。
- 完成后 `Qdrant points == Postgres embeddable_chunks`，source-type 分布一致。
- Qdrant payload 中的模型名、版本和 vector dimension 与查询端配置一致。
- 记录独立 ANN recall@10、双语 pair recall 和 latency，作为 Obj4 的 ANN lane baseline；
  不将 ANN-only 分数与 post-R3 hybrid 分数作直接 pass/fail 比较。
- post-reindex 完整 hybrid scorecard 的 recall@10 不得低于同 fixture/corpus 的
  post-R3 hybrid baseline；该检查只证明 runtime no-regression。
- 任何后续“提升”声明必须高于该 ANN baseline，并修复至少一个已标注 miss。
- embedding/Qdrant 不可用时 fallback 可见，不允许把 token-feature fallback 报成 ANN。

依赖与放行条件：

- 依赖：Obj1、Obj2。
- migration 必须先于 reindex；parity、recall 和 rollback 记录齐全后放行 Obj4。

### 4. 独立 lexical/ANN 双 lane、双语扩展与融合

涉及代码/文档：

- `src/vibration_agent/retrieval/bm25.py`
- `src/vibration_agent/retrieval/dense.py`
- `src/vibration_agent/retrieval/hybrid.py`
- `src/vibration_agent/retrieval/query_normalize.py`
- `configs/retrieval.yaml`
- `scripts/retrieval_eval.py`
- `scripts/rag_qa_eval.py`
- `tests/unit/test_s2_retrieval_skill.py`
- `tests/eval/test_retrieval_eval.py`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 让 lexical 与 ANN 从独立 corpus/index 召回，BM25 不再只处理 ANN top-N 候选。
- 分别记录 lane hits、rank、raw score、normalized contribution、latency 和 fallback。
- 基于 taxonomy 做可审计的中英术语扩展，不使用不可追溯的自由 query rewrite。
- 使用 RRF 或经 Obj1 数据批准的融合方式；source priority 仅作为稳定 tie-breaker。
- 明确 lexical backend 选择及其索引/刷新契约，避免 query-time load-all payload 成为长期实现。

验收标准：

- eval 可分别运行 lexical-only、ANN-only、hybrid 三种模式并输出独立 recall@5/@10。
- lexical lane 的候选集合不受 ANN top-N 限制，并有测试锁定该行为。
- hybrid recall@10 不低于两个单 lane 中较优者，且至少修复一个 Obj1 标注 retrieval miss
  才允许替换默认路径。
- 任何已有通过 case 不得变成 missing evidence；V2 faithfulness 不下降。
- retrieval output 明确报告 lanes、retrieval source、fallback 和每 lane contribution。
- 双语扩展只来自版本化 taxonomy，并对错误扩展或歧义 term 有 negative cases。

依赖与放行条件：

- 依赖：Obj1、Obj3；Obj2 gate 用于质量比较。
- replacement gate 未通过时保持旧路径或 feature flag default-off，不得强制推广。

### 5. 证据选择、邻接段落扩展与重排

涉及代码/文档：

- `src/vibration_agent/skills/s2_retrieval.py`
- `src/vibration_agent/skills/s3_qa_summary.py`
- `src/vibration_agent/retrieval/rerank.py`
- `src/vibration_agent/knowledge/evidence.py`
- `configs/retrieval.yaml`
- `tests/unit/test_s2_retrieval_skill.py`
- `tests/unit/test_s3_qa_summary_skill.py`
- `scripts/rag_qa_eval.py`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 在 S3 前按 query intent、lane agreement、source/page 和重复内容选择证据子集。
- 对同一文档内相邻 chunk 做有界扩展，用于恢复跨 chunk 的完整句和因果/结果段落。
- 去重重复页眉、摘要、目录、OCR fragment 和近重复 passage。
- 定义 evidence token budget，防止 top-k 或邻接扩展无限放大 prompt。
- 确定性重排优先；模型 reranker 必须独立 default-off、replay-first 并单独比较。

验收标准：

- 邻接扩展只在同一 doc 的可验证相邻位置发生，不能跨文档拼接伪上下文。
- selector 输出保留原始 chunk id/page/source 和 selection reason，可被 V2 追溯。
- 送入 S3 的 evidence 数量和 token estimate 有硬上限，超限有可见 warning/fallback。
- Obj1 completeness rate 严格高于 Obj4 baseline，V2 faithfulness 不下降。
- boundary-fragment、重复证据、cross-doc 问题和无邻接块情况均有 regression。
- 可选 reranker 只有在 scorecard 改善且 latency 在批准预算内时才允许启用。

依赖与放行条件：

- 依赖：Obj1、Obj4。
- selector/expansion 独立通过后才放行 Obj6，不与 LLM synthesis 同时开发或测量。

### 6. 受控 GPT synthesis 与 Opus supervisor

涉及代码/文档：

- `apps/api/main.py`
- `src/vibration_agent/llm/openai_client.py`
- `src/vibration_agent/llm/anthropic_client.py`
- `src/vibration_agent/llm/budget.py`
- `src/vibration_agent/llm/replay.py`
- `src/vibration_agent/skills/s3_qa_summary.py`
- `src/vibration_agent/agent/supervisor.py`
- `scripts/llm_capture.py`
- `scripts/manual_e2e.py`
- `tests/fixtures/llm/`
- provider、S3 和 supervisor 单元测试
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- Obj6A：构造受控 GPT S3 synthesis client，接入 API composition，但保持 default-off。
- Obj6A：固定 prompt/schema version、evidence allowlist、预算、usage/cost 和 replay capture。
- Obj6B：独立验证 Opus review/correction，修复 malformed correction schema fallback。
- 为 GPT 和 Opus 分别维护 replay fixture、scorecard、fallback 和 live manual command。
- 所有 model claims 继续经过 V2 hard gate；deterministic extraction 是故障 fallback。
- 只有 6A、6B 分别通过后，才评估组合链，避免把 supervisor 改善归因给 synthesis。

验收标准：

- 默认 API 和 CI 不构造 live client；无 key、live disabled、budget deny、timeout、refusal、
  schema error 和 replay miss 都 fail loud 并可见降级。
- 6A replay 在 Obj1 hard cases 上提升 completeness/readability，V2 faithfulness 不下降。
- 6B 的 reject→correct→approve replay 完成，correction 必须含 `answer` 或
  `structured_result`，不再因该契约 ValidationError fallback。
- provider/model/prompt/schema/request hash/token usage/cost/supervisor invocation 全部可追踪。
- manual live GPT 与 Opus 各至少完成一次验收，并记录实际 status、usage、cost 和 residual risk。
- 两个 lane 仍为 default-off；推广默认值需要单独 migration 和 scorecard 决策。

依赖与放行条件：

- 依赖：Obj1、Obj2、Obj5。
- 6A 未完成不得开始 6B；两者未独立通过不得宣称组合链工程可用。

### 7. 语料与 taxonomy 质量 pass

涉及代码/文档：

- `src/vibration_agent/ingestion/`
- `src/vibration_agent/storage/ingestion.py`
- `src/vibration_agent/storage/qdrant.py`
- `taxonomy/terms_zh_en.yaml`
- `taxonomy/symbols.yaml`
- `taxonomy/units.yaml`
- corpus/reindex/ingestion scripts
- ingestion、taxonomy、citation 和 retrieval tests
- `scripts/rag_qa_eval.py`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 让正式 chunk payload 直接携带 `source_filename`、`source_title` 和稳定 source path。
- 处理影响检索/引用的 `document_*` 通用名、OCR mojibake、页眉页脚和 fragment。
- 从 Obj1 miss 扩充术语、符号、单位、同义词和双语 alias family。
- 对每次 OCR/chunk/taxonomy 变化建立 versioned corpus snapshot 和可重现 ingestion 记录。
- 语料 mutation 与 Obj3–Obj6 串行隔离，变化后重跑完整 Obj1 scorecard。
- shrinking corpus 或 chunk rename 会留下 Qdrant orphan point；Obj7 必须显式 recreate
  collection，并使用新 fingerprint/checkpoint，不能跨 corpus mutation resume。

验收标准：

- 新入库 chunk 的 source filename/title 覆盖率达到 100%；fallback 仅兼容历史数据。
- 被 Obj1 标记的 mojibake/generic-name case 全部修复，并形成永久 regression。
- taxonomy 新条目均能追溯到真实 miss，含 canonical term、aliases、语言和歧义说明。
- ingestion 可重复执行；完成后 PG:Qdrant parity 和 source-type 分布检查通过。
- corpus 缩减或 chunk id 变化时使用显式 collection recreate；旧 checkpoint 必须失效。
- corpus mutation 前后 scorecard 分开保存，不把 corpus 改善混算为 retrieval/synthesis 改善。
- Obj1 已通过 case 不回归；如发生 chunk id 变化，fixture migration 明确记录映射或替换理由。

依赖与放行条件：

- 依赖：Obj1、Obj6。
- 不与 Obj3–Obj6 并行；新 corpus baseline 经 review 后才放行 Obj8。

### 8. 后端可靠性与 operator 工效

涉及代码/文档：

- `scripts/start_operator.py`
- reindex/ingestion scripts
- `src/vibration_agent/storage/qdrant_client.py`
- `src/vibration_agent/storage/qa_logs.py`
- `apps/api/main.py`
- `apps/ui/`
- `configs/api.yaml`
- `tests/unit/test_start_operator_script.py`
- API、storage、diagnostics 和 operator tests
- `docs/operator_ui.md`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

功能板块：

- 固化 Qdrant bulk timeout、batching、retry、resume 和错误汇总，不再依赖临时命令绕过。
- PG `qa_logs` 在依赖关闭或失败时快速降级，避免每次问答重复等待完整 connect timeout。
- 统一以 `scripts/start_operator.py` 为服务生命周期入口，明确 restart/reload/cache contract。
- 评估并替换或明确限制 Obj4 的全 payload 进程内 lexical cache；reindex 后必须刷新
  lexical payload cache 与 corpus standard catalog，不能继续服务旧语料边界。
- `/health`、`/diagnostics` 和 operator 展示 retrieval source、embedding model、store 状态和 fallback。
- 保持本地单用户边界，不新增远程管理、共享账号或公网部署能力。

验收标准：

- bulk reindex 在代表性全 corpus 上完成；临时网络失败按有界策略 retry/resume，不重复 point。
- Postgres 不可用时回答仍返回，warning 可见；同一进程后续请求不重复承担完整连接超时。
- 官方启动、restart、stop、端口占用和 stale process 均有脚本测试。
- 重启后 `/operator` 与 versioned JS/CSS 返回当前内容，无旧 UI cache 问题。
- diagnostics 明确区分 configured/enabled/reachable，并显示 active embedding model 与 retrieval source。
- lexical backend 有代表性语料规模下的内存/延迟记录；支持的 restart 流程后不存在旧
  payload cache 或旧 `taxonomy/corpus_standards.yaml`。
- 可靠性改动不改变答案 authority、chain order 或 V2 hard gate。

依赖与放行条件：

- 依赖：Obj3、Obj7。
- full local workflow 和 failure-path tests 通过后，才允许 Obj9 冻结后端接口。

### 9. 本地可靠性 backend/eval freeze

涉及代码/文档：

- `docs/phase_5_backend_interface_freeze.md`（新增）
- `docs/phase_5_scope.md`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`
- Obj1 scorecard 与 calibration reports
- `README.md`
- `docs/architecture.md`

功能板块：

- 冻结 retrieval lanes、融合、evidence selection、评分/V2 gate、LLM lane 和 fallback contract。
- 锁定 corpus version、embedding model、retrieval config 和 Obj1 regression baseline。
- 汇总 Obj2–Obj8 的默认值、feature flags、migration、rollback 和 residual risk。
- 明确哪些 live/model 能力仍 default-off，哪些确定性能力已成为支持基线。

验收标准：

- Obj2–Obj8 的 contract change 均能在 migrations 和 tests 中追溯。
- approved real-question scorecard、V2 calibration、retrieval lane eval 和 full suite 结果有记录。
- backend freeze 文档能判断后续 UI/文档变更是否破坏检索、评分、provider 或答案 authority。
- 无未分类的 local-reliability contract drift；未完成项明确 defer，不以“计划中”冒充完成。
- remote/shared/public/multi-user scope 未进入 backend freeze。

依赖与放行条件：

- 依赖：Obj2–Obj8 全部完成。
- backend/eval freeze 经 review 后，才允许 Obj10 最终冻结。

### 10. 五阶段最终接口冻结

涉及代码/文档：

- `docs/phase_5_interface_freeze.md`（新增）
- `docs/phase_5_backend_interface_freeze.md`
- `docs/phase_5_scope.md`
- `docs/phase_5_development_order.md`
- `docs/phase_5_progress.md`
- `docs/phase_5_migrations.md`
- `README.md`
- `docs/architecture.md`

功能板块：

- 汇总 Obj0–Obj9 已完成能力、冻结接口、评测门、默认值、rollback 和 residual risk。
- 冻结本地单用户 RAG answer-reliability 产品边界和 operator/API surface。
- 明确后续变更必须进入 successor migration/freeze，不再追加 Phase-5 feature objective。
- 验证无限期 defer 的 remote/shared/public/multi-user 范围没有进入实现或 backlog gate。

验收标准：

- full deterministic/replay suite、approved Obj1 scorecard、V2 calibration、retrieval eval、
  corpus parity 和必要 manual live commands 全部有最终记录。
- final freeze 明确引用 backend freeze，并列出 UI/observability 是否改变后端 contract。
- README、architecture、scope、progress 和 migrations 指向同一 Phase-5 frozen baseline。
- 所有 accepted residual risk 有 owner/后续边界；没有未说明的 skipped gate。
- Phase 5 在 progress 中标记 complete/closed，工作树和 release/commit 范围可审计。
- remote/shared/public/multi-user 能力仍无限期 defer，且不存在可自动激活的 entry gate。

依赖与放行条件：

- 依赖：Obj9。
- 本目标完成即关闭 Phase 5；任何新能力必须进入新的阶段规划。

## 排序原则

1. **Obj1 评测台是硬前置**，阻塞其后一切——measurement before change。
2. **Obj2 评分 + V2 硬门紧随**，作为 Obj3–6 全程使用的量尺；检索 / 合成变化后回校。
3. **先隔离检索召回（Obj3–4）再做证据选择 / 合成（Obj5–6）**，保证质量可归因；
   不在无隔离评估下同时替换 retrieval 与 synthesis。
4. **Obj7 语料 / 术语**独立执行，不与 Obj3–6 并行；任何重灌、OCR 修复或 chunk
   变化后都重跑 Obj1 全量 scorecard，避免 corpus drift 破坏归因。
5. **Obj8 后端工效**晚于核心检索 / 评分契约；UI / 工效不得成为隐藏 contract drift
   的来源。
6. **Obj9 后端 / 评测冻结**后执行 **Obj10 最终接口冻结**，不再追加部署方向目标。

## 执行模型与风险控制

沿用四阶段纪律（`docs/phase_4_development_order.md`）：

1. 所有新增 live / network 能力 default-off，且有 replay 或 deterministic fallback。
2. 所有 provider / embedding / rerank / rendering client 必须 lazy import 或
   runtime-discovered；fast suite 不依赖可选 SDK、外部命令或网络服务。
3. 模型输出仍走结构化 schema 与 V2/V4 路径，不绕过 citation check；V2 为硬门。
4. Retrieval 改动先有 recall/eval 数据再替换默认路径；embedding model / Qdrant
   维度 / chunk metadata 改动先记 migration 再 reindex，并校验 parity。
5. LLM 合成 / 重排为独立 default-off、replay-first 目标，带预算与 trace；GPT
   synthesis 与 Opus supervisor 先过各自 gate，再评估组合链。
6. 每个被修复的真实 miss 变成永久标注回归项（项目长期纪律）。
7. issue log 是用户 review artifact；实现 agent 不主动生成 / 编辑，除非用户显式要求。
8. 远程 / 共享 / 公开 / 多用户能力无限期 defer，不得进入五阶段 contract 或 eval gate。
9. 大规模 corpus、reindex、full eval 的运行权限交回实现 agent；agent 可在判断为必要时
   主动执行，并必须把 stdout/stderr/summary 写入 `run_logs/` 以便 error trace。manual live
   仍受显式 live/capture flag、provider key、预算和网络审批约束，但不再因为“由用户运行”
   这条流程纪律而默认暂停。
10. 若某项验证结果决定下一步实现方案或 threshold，该验证即为硬前置：实现 agent 先运行
    并审核 `run_logs/` 结果，只有结果失败、歧义、成本/网络权限受限或用户显式要求复核时
    才暂停；不得在未审核结果前提前开发下游生产 contract。
11. PowerShell 验证命令读取 JSON 时必须使用 `Get-Content -Raw -Encoding UTF8`；大型 JSON
    优先用 Python `json.load(..., encoding="utf-8")` 提取关键字段，不依赖系统默认代码页。

## 验证策略

- Fast CI：只运行 deterministic/replay tests；禁止 live provider、外部网络和真实 corpus reindex。
- Eval gate：Obj1 scorecard 是 Obj2–Obj8 的共同量尺；每个目标保存 before/after 报告。
- Focused tests：每个目标先运行受影响模块、schema、fallback 和 failure-path tests。
- Prerequisite checkpoint：当评测输出决定后续设计时，agent 先运行或生成必要验证并写入
  `run_logs/`，随后审核结果；审核完成前不得修改下游生产 contract。
- Full regression：目标放行前运行 full non-large suite、V2 calibration、retrieval eval 和
  `rag_qa_eval`；任何 skipped/deselected case 必须解释。
- Storage integration：涉及 ingestion/reindex 时验证 Postgres/Qdrant roundtrip、幂等和 parity；
  服务不可用时只能 clean skip 或 fail loud，不能伪报通过。
- Manual live：仅通过显式命令运行 GPT/Opus；记录 provider/model/status/usage/cost/
  residual risk。manual live 结果不替代 replay regression，但 Obj6 的 GPT/Opus manual
  live 验收仍是该 objective 的验收证据之一。
- Corpus mutation：Obj7 每次变化都生成新的 corpus snapshot 和完整 scorecard，不覆盖旧基线。
- Documentation gate：每个 contract/config/default 变化先更新 migrations，再更新 progress 和 freeze。

## 跨目标风险与缓解

- **小样本过拟合**：问题集按 intent、语言和 source type 分层；修复的新 miss 永久加入回归集。
- **corpus drift 破坏归因**：Obj7 与 Obj3–Obj6 串行隔离，任何 mutation 后重新建立 baseline。
- **评分 Goodhart 化**：保留人工 usable/unusable 标签和 adversarial cases，不以单一 composite 放行。
- **检索分数不可比**：lexical/ANN 先独立评测，融合只使用有定义的 rank/normalization contract。
- **邻接扩展污染证据**：只允许同 doc 可验证邻接，保留原始 provenance 和 token hard limit。
- **LLM 非确定性与成本**：default-off、replay-first、预算门、schema validation 和 deterministic fallback。
- **Supervisor 假闭环**：review 与 correction 分开验收；schema fallback 不能算 approved。
- **freeze 过度声明**：fixture scorecard 只证明覆盖集，不等于无监督工程真值；residual risk 必须显式。
- **部署范围漂移**：remote/shared/public/multi-user 无限期 defer，任何目标不得顺手引入相关 contract。

## 已确认的设计决策

1. Phase 5 只解决本地单用户 RAG answer reliability，不扩展产品部署面。
2. Obj1 measurement baseline 先于评分、检索、合成和 corpus 改动。
3. Obj2 将人工可用性与 V2 faithfulness 变成后续目标的共同 gate。
4. Obj3–Obj4 先解决并隔离 retrieval，再由 Obj5 改 evidence hand-off，Obj6 才接 model synthesis。
5. GPT synthesis 与 Opus supervisor 使用 Obj6A/6B 两个独立 gate。
6. Obj7 corpus mutation 不与 Obj3–Obj6 并行，变化后必须重跑完整 scorecard。
7. Obj9 先冻结 backend/eval，Obj10 再冻结最终 interface。
8. 所有 live 能力保持 default-off，CI 永不构造 live provider。
9. 共享、远程、公开和多用户能力无限期 defer，没有 Phase-5 entry gate。
