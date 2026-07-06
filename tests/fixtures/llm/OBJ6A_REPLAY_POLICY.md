# Obj6A Replay Policy

Only `obj6a_v3/` is eligible for Obj6A promotion and regression scoring.
It uses prompt `s3_qa_summary.v3` and the source-language support-anchor
contract. `obj6a/` (v1) and `obj6a_v2/` are failed diagnostic captures retained
only for root-cause history; they must not be passed to the promotion gate.

Replay hashes include prompt and schema versions, but directory selection must
still be explicit so a superseded experiment cannot be mistaken for the
promoted scorecard.
