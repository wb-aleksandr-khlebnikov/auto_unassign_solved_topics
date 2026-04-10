# Architecture

## Context

Service automates assignee lifecycle for solved Discourse topics.

Inputs:

- solved topic list from Data Explorer query
- topic/post metadata from Discourse API

Outputs:

- unassign and assign commands via Assign plugin API
- action history and state in SQLite
- operational logs in stdout

## High-Level Design

Single Python process:

- FastAPI app for health endpoints
- in-process async scheduler loop for periodic cycle execution
- shared API clients with retry/backoff
- SQLite state repository (persistent volume)

## Components

- app/config: pydantic-settings config, env parsing
- app/clients: API integrations (Data Explorer, Discourse, Assign)
- app/services/processor.py: business workflow and safety checks
- app/state/repository.py: persistent state and action history
- app/services/health.py + app/api/health.py: liveness/readiness checks
- app/scheduler/runner.py: periodic execution and graceful shutdown

## Data Model

topic_state table:

- topic_id (PK)
- last_unassigned_user_id, last_unassigned_username
- last_action
- last_seen_post_id
- last_unassigned_at, last_reassigned_at, updated_at

action_history table:

- topic_id
- action (unassigned/reassigned/skipped/failed)
- status (success/noop/error/dry-run)
- reason
- assignee refs, post_id, timestamp

## Cycle Flow

1. Fetch solved topics from Data Explorer.
2. Deduplicate and process in configured batch size.
3. For each topic:
   - reread topic state before mutation;
   - skip if closed/archived or no assignment;
   - unassign current assignee (or log dry-run);
   - persist removed assignee and last_seen_post_id.
4. Reassign pass for topics with pending unassigned state:
   - find posts newer than saved last_seen_post_id;
   - trigger only on non-staff post;
   - reread topic before assign to avoid races;
   - assign previous assignee back.
5. Cleanup history older than retention period.
6. Log cycle summary.

## Race Handling

- topic reread before unassign and reassign
- skip when assignment changed by user between fetch and mutate
- preserve action history for forensic analysis

## Reliability

- retries for transport and 429/502/503
- per-topic error isolation: one topic failure does not break cycle
- health readiness checks sqlite + discourse + data explorer

## Deploy Model

- one container, one process
- persistent docker volume for SQLite
- restart policy unless-stopped
