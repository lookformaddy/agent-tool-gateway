# Architecture

## Components

| Module | Responsibility |
| --- | --- |
| `registry.py` | Append-only (name, version) -> `ToolDefinition` map; `latest` resolution |
| `schema.py` | Minimal stdlib JSON-Schema validation for tool contracts |
| `authz.py` | Fail-closed scope checks: agent scopes AND tenant allow-list |
| `rate_limit.py` | Token buckets keyed by (tool, agent, tenant) |
| `gateway.py` | Execution pipeline, approval lifecycle, idempotency store |
| `audit.py` | Hash-chained append-only log with `verify()` |
| `accounting.py` | Cost/latency aggregation per tool, agent, tenant |
| `executors.py` | Deterministic mock executors (no network, synthetic data) |
| `api.py` | Optional FastAPI surface (absent FastAPI -> import-time guard) |
| `definitions.py` | Default catalog: 7 tools across LOW/MEDIUM/HIGH risk |

## Execution pipeline

```
resolve -> authorize -> validate args -> idempotency -> approval gate
-> rate limit -> execute (timeout) -> validate output -> ledger + audit
```

Any step may raise a typed `GatewayError`; the gateway catches it,
appends a `denied`/`error` audit entry, and re-raises. No failure mode
falls through to execution.

## Approval lifecycle

```
execute(HIGH tool, no approval) -> ApprovalRequired(approval_id)
approve(approval_id, approver)   -> status: pending -> approved
execute(..., approval_id)        -> approval consumed (one-shot) -> runs
reject(approval_id, approver)    -> status: rejected; later use re-raises
```

Approvals are bound to (agent, tool, argument hash). Changing the
arguments, the agent, or reusing a consumed approval all fail closed.

## Audit chain

```
entry_hash[i] = SHA256(prev_hash + canonical_json(entry fields))
prev_hash[0]  = 64 x "0" (genesis)
```

Verification recomputes every hash in order. Editing, deleting, or
reordering any entry breaks the chain from that point on. Canonical JSON
uses sorted keys and tight separators so hashes are reproducible.

## Idempotency

The store maps `idempotency_key -> (arguments_hash, result)`. A replay
with the same hash returns the stored result marked `cached=True` at
zero cost and without re-executing (and without consuming rate-limit
budget, since the check precedes the limiter). A replay with a different
hash raises `IdempotencyConflict`.

## Rate limiting

Token bucket per (tool, agent, tenant): capacity = the tool's
`rate_limit_per_minute`, refill = capacity/60 per second. Buckets are
created lazily on first use. Denials do not consume tokens, but the
denial itself is audited.

## Scaling notes

For a multi-replica deployment, replace the in-memory stores behind
narrow seams: buckets and idempotency in Redis (atomic Lua scripts for
check-and-set), approvals and audit in a database with an append-only
table, and periodic external anchoring of the latest audit hash
(e.g. to object storage) so even a compromised database cannot rewrite
history undetected.

## Diagram (text)

```
                +------------------+
  agent ------> | ToolGateway      |
                |  registry        |
                |  authorizer      |----> deny (fail-closed)
                |  approval store  |----> ApprovalRequired
                |  rate limiter    |----> RateLimited
                |  idempotency     |----> cached / conflict
                |  executor pool   |----> ToolTimeout
                |  ledger + audit  |
                +------------------+
```
