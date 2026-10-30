# agent-tool-gateway

A secure tool gateway for AI agents: the single choke point through which
every agent tool call passes, so safety policy is enforced in one place
instead of scattered across every agent.

## The enterprise problem

When agents gain tools, each new tool is a new blast radius: an agent can
call the wrong tool, a tenant can reach another tenant's capability, a
retried request can double-execute a side effect, and nobody can later
prove what was called, by whom, and why. Production agent platforms need
the same discipline as an API gateway — versioned contracts, authorization,
approval for dangerous operations, rate limits, idempotency, and a
tamper-evident audit trail — before agents are allowed near real tools.

## What it does

- **Versioned tool registry** — tools register with a name, version,
  JSON-schema input/output contracts, required scopes, and a risk tier.
  `latest` resolves to the most recently registered version.
- **Fail-closed authorization** — a call is denied unless the agent holds
  every scope the tool requires *and* the tenant's allow-list permits
  them. Unknown tenants, unknown tools, and missing scopes all deny.
- **Approval gates** — HIGH/CRITICAL tools (e.g. `data_export`) raise
  `ApprovalRequired` with an approval id; a human approves it, and the
  approval is one-shot and bound to the exact arguments.
- **Per-tool rate limits** — token buckets keyed by (tool, agent, tenant).
- **Timeouts** — each tool declares a timeout; executors run in a worker
  thread and a slow tool yields `ToolTimeout` instead of hanging the agent.
- **Idempotency keys** — replaying a key with identical arguments returns
  the cached result at zero cost; replaying it with different arguments
  raises `IdempotencyConflict` instead of double-executing.
- **Hash-chained audit log** — every outcome (including denials) is
  appended with a SHA-256 chain; `audit.verify()` detects any tampering.
- **Cost/latency accounting** — per-tool, per-agent, and per-tenant totals.
- **Optional FastAPI surface** — `src/agent_tool_gateway/api.py` exposes
  tool listing, invocation, approval, and audit verification. The core
  gateway is stdlib-only; API tests auto-skip when FastAPI is absent.

All executors are deterministic mocks (calculator, echo, weather lookup,
extractive summarizer, in-memory KV store, data export, slow echo) with
synthetic data and no network access, so the gateway's safety behavior can
be exercised end to end. A production deployment swaps an executor for a
real client behind the same `(arguments) -> output dict` signature.

## Architecture overview

```
Agent -> ToolGateway.execute(request)
          -> ToolRegistry.resolve(name, version)
          -> Authorizer (agent scopes + tenant allow-list, fail-closed)
          -> schema.validate(arguments)
          -> idempotency store (replay / conflict)
          -> approval gate (HIGH/CRITICAL need a live, one-shot approval)
          -> RateLimiter (token bucket per tool/agent/tenant)
          -> executor with timeout -> schema.validate(output)
          -> CostLedger + hash-chained AuditLog
```

See [docs/architecture.md](docs/architecture.md) for the full design,
including the approval lifecycle and the audit chain construction.

## How to run

```bash
pip install -r requirements.txt   # only needed for the optional API surface
python examples/run_demo.py       # end-to-end demo, stdlib only
pytest -q                         # test suite (API tests skip w/o FastAPI)
```

The demo shows an allowed call, a fail-closed denial, the approval flow
for a high-risk export, an idempotent replay, audit-chain verification,
and the cost ledger summary.

## Key design decisions and trade-offs

- **Fail-closed by default.** Deny is the zero-effort path: anything
  unrecognized (tenant, tool, scope) denies. This trades a little
  onboarding friction for never silently permitting a call.
- **Authorization before validation.** A caller that cannot use a tool
  learns nothing about its schema from error messages.
- **Approvals bound to argument hashes, one-shot.** Approving "export 3
  rows" cannot be replayed to export 100 rows, and cannot be reused.
- **Thread-based timeouts, not signals.** Signals don't work outside the
  main thread and can't interrupt most blocking calls anyway; a worker
  thread with `Future.result(timeout=...)` is portable, at the cost of a
  thread per call (fine for a gateway; pool it in production).
- **Audit-before-trust, not audit-after.** Denials are logged too, so a
  probing agent leaves a trail, not a gap.
- **Hash chain, not a database.** The chain gives tamper evidence with
  zero infrastructure; production should persist entries to append-only
  storage and anchor hashes externally on a schedule.
- **In-memory state.** Registry, buckets, approvals, idempotency, and the
  ledger are process-local by design for this reference build; a
  multi-replica deployment needs shared stores (Redis for buckets and
  idempotency, a DB for approvals and audit) — the interfaces are small
  and swappable.

## What it demonstrates

Gateway architecture for agentic systems: contract-first tool design,
defense-in-depth authorization, human-in-the-loop gates for risky tools,
idempotency as a correctness property, tamper-evident auditing, and
cost observability — all testable without any external service.
