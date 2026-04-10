# Discourse Assignee Automation

Production-ready Python service that:

- every 5 minutes reads solved topics from Discourse Data Explorer SQL;
- unassigns current assignee from solved topics;
- reassigns previously removed assignee when a new non-staff post appears.

State and action history are stored in SQLite on a persistent Docker volume.

## Features

- API-only integration with Discourse and Assign plugin
- configurable Data Explorer query and params
- retry with exponential backoff for 429/502/503 and transport failures
- DRY_RUN mode and production mode
- race-safe updates via topic reread before mutating actions
- SQLite state and action history retention cleanup
- one container / one process with FastAPI health endpoints + scheduler loop
- plain text logs to stdout

## Quick Start

1. Copy env template:

   cp .env.example .env

2. Fill real values in .env:

- DISCOURSE_BASE_URL
- DISCOURSE_API_KEY
- DISCOURSE_API_USERNAME
- DATA_EXPLORER_QUERY_ID
- DATA_EXPLORER_QUERY_PARAMS_JSON

3. Start service:

   docker compose up -d --build

4. Health checks:

- liveness: http://localhost:8080/health/live
- readiness: http://localhost:8080/health/ready

## Local Development

- python 3.12+
- pip install -e .[dev]
- make lint
- make test
- make run

## Environment Variables

See .env.example for full set.

Key parameters:

- DRY_RUN=true|false
- POLL_INTERVAL_SECONDS=300
- BATCH_SIZE=50..100
- SQLITE_PATH=/data/state.db
- HISTORY_RETENTION_DAYS=180
- ASSIGN_UNASSIGN_ENDPOINT and ASSIGN_ASSIGN_ENDPOINT
- ASSIGN_PAYLOAD_TOPIC_KEY and ASSIGN_PAYLOAD_USER_KEY
- ASSIGN_USE_USER_ID=true|false

## Data Explorer SQL

Use your own query id. Suggested SQL:

SELECT DISTINCT ON (t.id)
  t.id AS topic_id,
  CONCAT('https://support.wirenboard.com/t/', t.id) AS topic_link,
  t.title AS topic_title,
  u.username AS assigned_user,
  t.updated_at AS last_updated
FROM topics t
JOIN topic_custom_fields tcf ON t.id = tcf.topic_id
JOIN posts p_acc ON p_acc.id = tcf.value::integer AND p_acc.topic_id = t.id
JOIN post_custom_fields pcf ON pcf.post_id = p_acc.id
JOIN assignments a ON t.id = a.topic_id
JOIN users u ON a.assigned_to_id = u.id
WHERE tcf.name = 'accepted_answer_post_id'
  AND tcf.value ~ '^[0-9]+$'
  AND pcf.name = 'is_accepted_answer'
  AND pcf.value = 'true'
  AND p_acc.deleted_at IS NULL
  AND t.archived = false
  AND t.closed = false
  AND t.updated_at >= NOW() - INTERVAL '5 months'
  AND NOT EXISTS (
    SELECT 1
    FROM posts p2
    WHERE p2.topic_id = t.id
    AND p2.raw LIKE '%эта тема была автоматически закрыта%'
  )
ORDER BY t.id, t.updated_at DESC

## Operational Runbook

### Start / stop

- start: docker compose up -d --build
- stop: docker compose down
- logs: docker compose logs -f discourse-assignee-automation

### Switch DRY_RUN and production

- set DRY_RUN=true for preview mode
- set DRY_RUN=false for real write mode
- restart container after changes

### Verify processing

- check cycle summary in logs (fetched, processed, unassigned, reassigned, skipped, failed)
- check readiness endpoint for sqlite/discourse/data_explorer checks

### State and history

- SQLite DB path: /data/state.db
- persisted in volume: discourse_assignee_state
- history retention cleanup runs each cycle and deletes entries older than HISTORY_RETENTION_DAYS

### Backup / rotate state

- backup volume before major changes
- if needed, snapshot state.db from the volume

## Security Notes

- never commit .env
- do not print API keys in logs
- use least privilege API key in Discourse

## Known Compatibility Note

Assign plugin endpoints can differ by Discourse/plugin version. Configure endpoint paths and payload keys via env:

- ASSIGN_UNASSIGN_ENDPOINT
- ASSIGN_ASSIGN_ENDPOINT
- ASSIGN_PAYLOAD_TOPIC_KEY
- ASSIGN_PAYLOAD_USER_KEY
- ASSIGN_USE_USER_ID
