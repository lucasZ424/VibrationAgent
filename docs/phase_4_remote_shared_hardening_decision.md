# Phase 4 Remote/Shared Hardening Decision

Date: 2026-06-18

## Decision

Remote/shared hardening is deferred. Phase 4 remains a local-first,
single-user product baseline.

This objective does not implement multi-user authorization, durable shared rate
limits, remote metrics, public deployment, k8s, shared secrets management, or
remote persistence hardening. Those are Phase-5 candidates only if product
positioning explicitly changes from local personal deployment to shared,
remote, or public access.

## Current Baseline

The supported deployment model is:

- one trusted engineering user;
- trusted local files under the configured workspace;
- localhost CLI/API/operator UI;
- private local knowledge base and ignored local secrets in `.env`;
- deterministic/replay CI with live providers default-off.

Existing API controls are local single-user controls: an optional API token and
an in-process rate limiter can be enabled for localhost/operator use. Obj16
defers multi-user identity/authorization and durable distributed rate limiting;
it does not remove or weaken those existing local controls.

Obj15 added local-first observability. Its `/health` and default
`/diagnostics` surfaces are offline and redacted. Explicit
`/diagnostics?probe_dependencies=true` remains an operator-only local probe for
configured Postgres/Qdrant reachability.

## Deferred Scope

The following are not implemented in Phase 4:

- multi-user identity or authorization policy;
- tenant isolation for documents, chunks, logs, cache, or model outputs;
- durable distributed rate limits;
- remote/shared metrics, tracing, log shipping, or alerting;
- public ingress, TLS termination, reverse-proxy deployment, k8s, or container
  hardening;
- remote secret storage, rotation, or provider-key management;
- audit trails for multiple users or administrative actions.

## Revisit Gate

Remote/shared hardening can move from deferred to implementation only after a
new objective records all of these decisions:

- target deployment: private LAN, shared team server, public API, or SaaS;
- identity provider and authorization model;
- tenant/data isolation boundary;
- secrets and provider-key ownership;
- durable storage and rate-limit backend;
- logging/metrics retention and redaction policy;
- security test plan and rollback path.

Until that gate is satisfied, local-first defaults remain binding and no normal
runtime path should assume remote/shared safety.

## Verification

Obj16 is documentation-only. It changes no runtime schema, API behavior,
provider path, retrieval path, chain order, CI workflow, or default deployment
settings.
