# S3 — Concept explanation / summary / QA

Three supported tasks:

- **whole_doc_summary** — 1 page prose, then a bullet list of takeaways.
- **section_summary** — quote-heavy, preserve equations verbatim.
- **qa** — answer the user using **only** the retrieved chunks.

## Rules

- Every claim that isn't common knowledge must cite a chunk id.
- Label each citation: `documented`, `inferred`, or `heuristic`.
- If the retrieved chunks don't cover a sub-claim, **say so** — do not fill the gap
  with model-world knowledge.
- Prefer Chinese or English to match the dominant language of the sources.
