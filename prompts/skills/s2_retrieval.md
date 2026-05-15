# S2 — Knowledge-base retrieval

1. Normalize the query using the taxonomy (zh ↔ en aliases, symbol resolution).
2. Classify intent: `definition | comparison | standard_lookup | engineering | summary`.
3. Run BM25 and dense recall; fuse with RRF.
4. Apply source priority: `standard > textbook > review > paper > webpage`.
5. Return the `RetrievalOutput` schema (see `schemas.py`). Give a short `reason` for
   each hit — e.g. "contains explicit damping-ratio estimation method".

**Never** invent pages or chunk ids. If nothing strong comes back, return `status:
insufficient` and hand off to the orchestrator.
