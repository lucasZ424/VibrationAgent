# Phase 4 Symbolic Proof / CAS Feasibility Spike

Updated: 2026-06-17

## Decision

Do not add a mandatory CAS or symbolic proof dependency in Phase 4.

The useful production shape is a narrow, optional, default-off algebra checker
for S5 derivation steps. It should be a separate production objective only after
the project has a labeled derivation-equivalence eval set. Until then, S5 should
keep its current contract:

- cite visible evidence for documented formula steps;
- allow explicitly marked `axiomatic` algebra steps;
- pass through V2 before V4;
- keep Obj11 `FormulaRender` as rendering metadata, not proof metadata.

## Why Not In Obj12

Obj12 is a feasibility spike. Adding a CAS now would blur three contracts that
Phase 4 deliberately separated:

- Obj5 V2 evidence support checks whether claims are supported by visible
  evidence.
- Obj11 formula rendering checks whether formula markup can be represented or
  safely degraded to plain text.
- Symbolic proof would check whether algebraic transformations are equivalent
  under declared assumptions.

Those are different assertions. A CAS checker can help the third one, but it
cannot replace V2 evidence support or Obj11 rendering validation.

## Domain Fit And Current Evidence

The narrow scalar-algebra subset is only a minority fit for the vibration
corpus this assistant is built around. High-value vibration derivations often
involve transfer functions, differential equations, modal matrices,
eigenvalues, damping assumptions, approximations, or unit-bearing physical
models. Those are exactly the cases this spike keeps out of scope for a first
checker.

Current repository evidence is also small. The committed S5 replay fixtures are
three JSON files:

- `s5_visible_multistep_response.json`: 3 derivation steps, 2 `axiomatic`;
- `s5_fabricated_step_number_response.json`: 2 derivation steps, 1
  `axiomatic`;
- `s5_cycle_response.json`: 2 derivation steps, 1 `axiomatic`.

That is 7 fixture steps total, with 4 `axiomatic` steps. The deterministic S5
fallback is also a fixed two-step pattern: one cited evidence step plus one
generic axiomatic rearrangement step. These fixtures are enough to test S5/V2
handling, but they are not a corpus-wide demand signal for CAS. They mostly use
simple scalar stiffness examples, so they do not prove that a symbolic checker
would carry meaningful value on real vibration derivations.

This weakens the business case for production CAS now: the checker would be
most reliable on the easiest subset and least applicable to the domain-heavy
derivations where users would expect the most help.

## Candidate Approaches

### A. No CAS, Keep Current S5

This is the current default and remains the safest Phase-4 backend freeze
baseline.

Pros:

- no dependency, parser, sandbox, or runtime cost;
- deterministic CI remains unchanged;
- S5 stays evidence-bound and V2/V4-compatible;
- no false confidence from a partial symbolic checker.

Cons:

- cannot automatically verify algebraic equivalence;
- must trust S5's structural step validation plus V2's evidence guard;
- more review burden for multi-step derivations.

Recommended for Phase 4 default.

### B. Optional SymPy-Based Narrow Algebra Checker

This is the only production direction that looks worth considering later.

Shape:

- optional dependency only, for example a future `symbolic` extra;
- default-off setting, never required for CI or ordinary local use;
- explicit S5 checker stage that annotates derivation steps, not a replacement
  for S5;
- deterministic replay/eval first, before routing or answer-authority changes.

Supported formula classes should be narrow:

- scalar algebraic equalities;
- variable isolation and simple rearrangements, such as `F = k*x` to `x = F/k`;
- polynomial/rational expression equivalence after declared nonzero
  assumptions;
- simple substitutions where all symbols come from cited evidence or declared
  axiomatic assumptions.

Unsupported classes should remain out of scope unless a later objective expands
the eval set:

- differential equations and transfer functions with implicit domains;
- matrix, tensor, modal, or eigenvalue derivations;
- inequalities, approximations, limits, and asymptotic statements;
- unit conversions and dimensional analysis unless units are separately parsed
  and checked;
- numeric parameter estimation;
- arbitrary LaTeX parsing;
- proof of engineering truth, physical validity, or applicability.

Dependency and implementation cost:

- SymPy itself is local and offline, but cross-version canonical forms and
  `simplify()` / `equals()` inconclusive results can vary. A production checker
  must treat inconclusive results as `not_verified` or `unsupported`, not as
  proof.
- LaTeX parsing often introduces extra parser dependencies and broader failure
  modes.
- String-to-expression parsing must be constrained to a safe expression subset;
  arbitrary Python evaluation is not acceptable.
- Every accepted transformation needs explicit assumptions, especially nonzero
  denominators and real/positive domains.
- Every check needs a timeout or complexity bound so pathological expressions
  cannot hang S5.
- False positives are more expensive than false negatives: an incorrect proof
  label could make an unsupported derivation look authoritative.

### C. Model-Backed Entailment Or Proof Review

This is not suitable as the Obj12 production recommendation.

Pros:

- handles more natural-language derivation steps;
- can explain uncertainty.

Cons:

- conflicts with deterministic/replay CI unless fully default-off and fixture
  backed;
- does not produce formal proof;
- can overstate correctness;
- duplicates risks already accepted for model-backed S5.

If pursued, it should be a separate replay-first reviewer, not a CAS checker.

### D. External CAS Services

Do not use for the local-first backend baseline.

Examples include hosted Wolfram-style services or remote notebooks.

Problems:

- network dependency;
- credential and cost management;
- replay/capture burden;
- hard-to-freeze API semantics;
- poor fit for single-user local-first operation.

## Proposed Production Contract If Pursued Later

A future production objective should add a structured field similar to:

```json
{
  "symbolic_check": {
    "schema_version": "p4.symbolic_check.v1",
    "status": "verified|not_verified|unsupported|checker_unavailable",
    "checker": "sympy_narrow_algebra",
    "checked_step_ids": ["step_2"],
    "unsupported_step_ids": [],
    "assumptions": ["k != 0"],
    "warnings": []
  }
}
```

Rules:

- `verified` may only mean algebraic equivalence under listed assumptions.
- `not_verified` must not delete the derivation by itself; V2 still decides
  evidence support, and S5/V4 must retain plain-text fallback.
- `unsupported` is expected for formulas outside the checker subset.
- `checker_unavailable` must degrade to current S5 behavior.
- Checker execution must have a timeout or complexity bound. Timeout and
  complexity exits must produce `checker_unavailable` or `unsupported`, not a
  partial `verified`.
- No final answer should say "proved" unless the field is `verified` and the
  answer states the assumptions.

## Eval Gate Before Production

Before adding production code, create a labeled derivation eval set with at
least these case families:

- valid scalar rearrangement;
- valid rearrangement requiring a nonzero assumption;
- invalid rearrangement with same symbols;
- unsupported differential equation;
- unsupported matrix/eigenvalue expression;
- ambiguous notation that should fall back;
- malformed expression that should fail loud;
- unit-bearing formula where symbolic equivalence alone is insufficient.

Minimum production gate:

- no false `verified` labels on invalid or unsupported cases;
- every `verified` case records assumptions;
- checker unavailable path produces the same S5/V2/V4 behavior as today;
- full non-large CI does not require the optional symbolic dependency.

## Fallback Behavior

Fallback should preserve the current Phase-4 answer path:

1. S5 emits premise, steps, conclusion, assets, and `formula_renders`.
2. V2 checks cited evidence and filters unsupported content.
3. V4 renders the plain-text answer.
4. If symbolic checking is absent, unavailable, unsupported, or inconclusive,
   the answer remains evidence-bound but not formally proved.

This makes symbolic checking additive. It must not become an implicit authority
expansion path.

## Recommendation

Defer production CAS integration.

Create a future objective only if there is an event-driven signal that users
actually need automatic algebraic equivalence checking for S5. Suitable triggers
would be:

- repeated reviewer burden on multi-step derivations where the only open
  question is scalar algebraic equivalence;
- user-reported algebra errors that V2 evidence support and S5 structural
  checks cannot catch;
- a labeled derivation eval set showing enough scalar rearrangement cases to
  justify the dependency and maintenance cost.

That future objective should start with the eval gate above, then implement
approach B as an optional, default-off SymPy narrow algebra checker. Full proof,
arbitrary LaTeX parsing, external CAS services, and model-backed proof claims
should remain out of scope for the Phase-4 backend freeze.
