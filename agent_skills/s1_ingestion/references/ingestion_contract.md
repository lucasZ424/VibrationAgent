# S1 Ingestion Contract

S1 is an ingestion skill only. It prepares evidence for retrieval and QA; it does
not answer engineering questions and does not interpret formulas or figures.

The downstream consumer should read `chunks.jsonl` or `api_context.json`, then
run S2 retrieval.
