# ADR 0001: Single Process Scheduler + Health API with SQLite State

## Status

Accepted

## Date

2026-04-10

## Decision

Use a single Python process running FastAPI plus an in-process async scheduler loop. Persist state/history in SQLite mounted via Docker volume.

## Rationale

- simple deployment and operations
- no external queue/DB dependency for first production rollout
- clear failure domain and easy backup/restore of state
- health endpoints can expose dependency checks and scheduler status

## Consequences

Positive:

- low operational complexity
- deterministic state persistence
- easy local and CI execution

Tradeoffs:

- SQLite is single-node local storage, not multi-replica shared state
- scheduler interval accuracy depends on process health

Mitigations:

- persistent volume and backups
- restart policy and readiness checks
- action history for audit/recovery
