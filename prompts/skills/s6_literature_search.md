# S6 Literature Search Prompt Contract

S6 captures literature candidates for vibration engineering questions.

Return structured candidates only. Do not synthesize final answers.

Each candidate must include:

- `title`
- `authors`
- `year`
- `venue` or `source`
- `doi`, `arxiv_id`, or `url`
- `abstract` or `snippet`
- `retrieval_source`
- `evidence_anchors`

Live sources are manual-only:

- Semantic Scholar Graph API is the primary source.
- arXiv API is the arXiv-only secondary source.

Before storing or promoting captured data, redact API keys, bearer tokens,
local paths, and long raw text.
