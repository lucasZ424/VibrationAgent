# Model Orchestration And Agent-Owned Skills

This document records the upgraded control-plane design for `vibration_agent`.
It complements `docs/architecture.md` and does not change the Phase-0 domain
scope.

## Design Judgment

Restricting the Claude Opus path to `extreme` tasks is reasonable. Opus has a
higher latency and token-cost profile, so routing low, medium, and ordinary high
difficulty tasks through GPT preserves iteration speed. The system should only
pay for Opus when the expected cost of a wrong framework, failed correction loop,
or weak mathematical/engineering review is higher than the model-call cost.

High difficulty alone is not enough to trigger Opus. The routing policy should
separate difficulty from escalation cost.

## Agent-Owned Skills

Skills are owned by this project, not by a model vendor.

```text
agent_skills/
  s1_ingestion/
    SKILL.md
    references/
    scripts/
```

The `agent_skills/` layer is agent-facing. It defines when to use a skill, what
inputs are required, what outputs are allowed, what failure behavior is expected,
and what references the model should load.

The `src/vibration_agent/skills/` layer is runtime-facing. It executes stable
Python code and returns `SkillInput` / `SkillOutput` compatible results.

This separation allows the same skill package to be consumed by GPT, Claude, or a
local orchestrator while preserving deterministic execution underneath.

## Routing Policy

Routing is stakeholder-defined and configurable. A model may recommend a routing
level, but it must not have unrestricted authority to move ordinary work into the
expensive Opus path.

| Difficulty | Default owner | Opus allowed by default |
| --- | --- | --- |
| low | GPT | no |
| medium | GPT | no |
| high | GPT | no |
| extreme | Opus-supervised loop | yes |

## Extreme Supervisor Loop

```text
User task
  -> policy router marks task as extreme
  -> Claude Opus: framework design, decomposition, risk definition
  -> GPT: implementation, tests, candidate answer
  -> Claude Opus: senior supervisor review
  -> if no issues: final answer
  -> if issues and loop_count < 2: GPT correction, then Opus review again
  -> if issues remain after two review loops: Opus takes ownership
```

The two-loop limit is part of the design. If the same class of issue remains
after two GPT correction loops, ownership moves to Opus or the task pauses for
human clarification.

## Baseline Extreme Triggers

- stakeholder explicitly marks the task as extreme
- cross-layer architecture change with long-term compatibility risk
- schema, database, retrieval, or citation-contract change with high blast radius
- rigorous mathematical or engineering reasoning where an incorrect conclusion
  has high downstream cost
- persistent failure after two GPT correction attempts
- senior framework critique is more valuable than fast execution

## Non-Triggers

- ordinary high-complexity work with clear acceptance criteria
- small or medium code changes
- test additions for known behavior
- routine documentation updates
- localized refactors

## Implementation Implication

Add a later control-plane objective before implementing the dual-API runtime:

```text
Obj11.5 - Agent-owned skill registry and model routing design
```

Expected artifacts:

- `agent_skills/<skill_id>/SKILL.md` layout
- difficulty enum and routing policy config
- model registry abstraction for GPT and Opus clients
- supervisor-loop schemas for plan, execution result, review report, and revision
- tests proving low/medium/high do not call Opus by default
