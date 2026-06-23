# R2: critical-speed answer quality guard

Date: 2026-06-23

## Problem

The operator question `旋转机械到达临界转速后会发生什么？` produced a fluent but
unusable answer. Retrieval found a GB/T definition chunk for resonant/critical
speed, and deterministic S3/S4 converted that definition into an answer even
though the user asked for the engineering outcome.

## Root Cause

- The active `data/chunks` corpus currently contains only one standard, one Orbit
  60 datasheet, and one Vold-Kalman order-analysis paper. It does not contain a
  general rotor-dynamics passage saying that vibration response/amplitude is
  amplified near critical speed.
- BM25 indexed Chinese single-character tokens, so broad matches such as
  `旋/转/机/械` added noise.
- Critical-speed outcome questions expanded only to definition aliases, not
  response/outcome terms.
- S3 accepted definition-only evidence for an outcome question.

## Change

- CJK BM25 tokenization no longer emits single-character tokens for multi-char
  Chinese segments; it keeps 2/3/4-grams so terms such as `临界转速` remain
  searchable.
- Critical-speed outcome queries add response/amplitude expansion terms.
- S3 deterministic QA rejects definition-only evidence for critical-speed
  outcome questions. It now requires evidence containing outcome markers such as
  response, amplitude, amplification, `响应`, `振幅`, `幅值`, `放大`, or `增大`.

## Verification

- Added regression tests for CJK token noise, critical-speed outcome expansion,
  definition-only rejection, and response-evidence preference.
- The real operator query now returns `insufficient` with the warning:
  `Retrieved evidence does not contain critical-speed outcome evidence.`
- Full pytest suite: 500 passed.

## Remaining Work

This guard prevents misleading answers, but it does not create missing knowledge.
To answer the operator question directly, ingest a rotor-dynamics textbook/manual
section covering critical-speed passage, resonance response, amplitude
amplification, damping, and safe run-up/coast-down behavior.
