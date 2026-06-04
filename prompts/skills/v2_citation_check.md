# V2 Citation Check

Runtime implementation: `src/vibration_agent/skills/v2_citation_check.py`.

V2 is a deterministic quality layer inserted after S3 and before V4.

## Contract

- Validate that each S3 claim cites a chunk visible in the S2 retrieval context.
- Reject claims with missing chunk ids, invisible chunk ids, uncited answer prose,
  or obvious lexical mismatch against the cited evidence text.
- Semantic entailment is not required in Obj10.
- When unsupported claims exist, return `insufficient`, remove those claims from
  the renderable result, and clear the conclusion answer so V4 can render only
  remaining evidence.
- If V2 itself fails in the orchestrator, the primary answer must not fail; the
  orchestrator records a warning and passes through S3 output.

## Obj10 Limits And Policy

- The fake-reference interception metric means non-existent or invisible chunk
  references. It is not a semantic hallucination-detection rate.
- The lexical mismatch gate catches only obvious zero-overlap mismatches. A false
  claim that reuses vocabulary from a real visible chunk may pass V2 until a
  later semantic reviewer is implemented.
- Unsupported claims trigger an all-or-nothing conclusion block. V2 clears the
  prose conclusion instead of trying to surgically rewrite it, because S3 answer
  prose is not safely reconstructable from claim fragments.
