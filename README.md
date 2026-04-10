# Discourse Assignee Automation

Production-ready Python service that automatically unassigns support staff from solved Discourse topics, ensuring tickets flow to new issues. When customers reply to solved topics, staff are automatically reassigned if needed.

## How It Works

**Every 5 minutes the service:**

1. **Fetches assigned & solved topics** using Discourse Search API:
   - Public topics: `in:assigned status:solved after:2023-11-01`
   - Private messages: `in:assigned in:messages` (no solved filter for PMs)

2. **Unassigns resolved cases** from their current assignee

3. **Tracks state in SQLite** — remembers who was unassigned from which topic

4. **Auto-reassigns on new customer replies** — when non-staff posts appear, automatically reassigns the original assignee to bring the topic back into their queue

**Supports:**
- Public topics (via Discourse Search API with `status:solved` filter)
- Private message conversations (via `in:assigned in:messages` search)
- Flexible Assign plugin configurations (configurable endpoint paths, payload keys)
- Dry-run mode for safe testing before production deployment
- Exponential backoff retry logic for rate limits and transient errors
- SQLite state/action history with automatic cleanup (default 180 days)

## Features

- API-only integration with Discourse Search and Assign plugin (no SQL queries)
- Two data sources: public solved topics + private message conversations
- Race-safe updates via topic reread before making assignment changes
- FastAPI with async processing + built-in health checks + scheduled 5-min cycles
- SQLite for durable state and audit trail of all actions
- Configurable Assign plugin endpoints and payload schema
- Exponential backoff retry with 429/502/503 handling
- DRY_RUN mode for safe testing + production mode for real writes
- Plain text structured logging to stdout (JSON-compatible)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/wb-aleksandr-khlebnikov/auto_unassign_solved_topics.git
cd auto_unassign_solved_topics
```

### 2. Configure environment

Copy template and edit:
```bash
cp .env.example .env
```

Required values:
- **DISCOURSE_BASE_URL** — your Discourse instance URL (e.g., `https://support.example.com`)
- **DISCOURSE_API_KEY** — API key from /admin/api/keys (system user recommended)
- **DISCOURSE_API_USERNAME** — usually `system`
- **DRY_RUN=true** — start in test mode (no actual changes)

Optional (sensible defaults provided):
- **SEARCH_AFTER_DATE** — topics older than this are ignored (default: 2023-11-01)
- **POLL_INTERVAL_SECONDS** — cycle frequency in seconds (default: 300)

### 3. Start the service

```bash
# Build and start
docker compose up -d --build

# Verify health
curl http://localhost:8080/health/live  # should return 200

# Check logs
docker compose logs -f discourse-assignee-automation
```

Expected first log output:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### 4. Run in dry-run mode first

Watch the logs for 5 minutes to see what would be unassigned:
```bash
docker compose logs discourse-assignee-automation | grep cycle_summary
```

### 5. Switch to production (real writes)

Edit `.env`:
```bash
DRY_RUN=false
```

Restart:
```bash
docker compose up -d
```

Verify the next cycle actually unassigns (check logs for `"unassigned": > 0`).

## Local Development

### Prerequisites

- Python 3.12+
- Git
- Virtual environment (venv or conda)

### Setup

1. Clone and enter:
   ```bash
   git clone https://github.com/wb-aleksandr-khlebnikov/auto_unassign_solved_topics.git
   cd auto_unassign_solved_topics
   ```

2. Create virtualenv:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # on Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```

### Development Commands

```bash
# Run tests
pytest -q

# Run tests with coverage
pytest --cov=app tests/

# Format code
ruff format .

# Lint code
ruff check --fix .

# Run service locally (requires .env with real credentials)
python -m app.main
# or: make run

# Check all (lint + test)
make lint test
```

### Project Structure

```
app/
├── main.py              # FastAPI app + lifespan
├── api/health.py        # /health/live, /health/ready endpoints
├── clients/
│   ├── http.py          # async HTTP client with retry logic
│   ├── discourse.py      # Discourse Search + topic JSON API
│   ├── search.py        # SearchClient: public + PM topics
│   └── assign.py        # Assign plugin: unassign/assign
├── models/
│   └── domain.py        # TopicSnapshot, AssignmentInfo
├── services/
│   ├── processor.py      # main cycle logic
│   └── health.py        # health check service
├── state/
│   └── repository.py    # SQLite CRUD for topics & actions
├── scheduler/
│   └── runner.py        # async cycle scheduler (5-min interval)
└── config/
    └── settings.py      # pydantic settings, env vars

tests/
├── test_processor.py         # happy path: unassign solved topics
├── test_processor_unsolved.py # unsolved topic skipped
├── test_health.py            # health check logic
└── test_repository.py        # SQLite state ops
```

## Environment Variables

See .env.example for full set.

Key configuration:

- **DRY_RUN=true|false** — preview mode (no actual unassigns/reassigns)
- **POLL_INTERVAL_SECONDS=300** — cycle frequency (5 minutes)
- **SEARCH_AFTER_DATE=2023-11-01** — date filter for public topic search
- **BATCH_SIZE=50..100** — topics processed per cycle
- **SQLITE_PATH=/data/state.db** — state database location
- **HISTORY_RETENTION_DAYS=180** — auto-cleanup old action records

Assign plugin configuration:
- **ASSIGN_PAYLOAD_TOPIC_KEY=target_id** — key name for topic ID in API payload
- **ASSIGN_PAYLOAD_USER_KEY=username** — key name for user identifier in API payload
- **ASSIGN_UNASSIGN_ENDPOINT=/assign/unassign** — PUT endpoint to remove assignment
- **ASSIGN_ASSIGN_ENDPOINT=/assign/assign** — PUT endpoint to add assignment
- **ASSIGN_USE_USER_ID=false** — if true, use user_id instead of username

## Discourse Search Queries

### Public Topics
Fetches assigned & solved topics after SEARCH_AFTER_DATE:
```
GET /search.json?q=in:assigned%20status:solved%20after:2023-11-01
```

Returns only public topics with accepted answers. Pagination handled automatically (max 20 pages × 50 per page).

### Private Messages
Fetches all assigned private message conversations (Discourse doesn't support `status:solved` filter for PMs):
```
GET /search.json?q=in:assigned%20in:messages
```

Returns PM topics; each is checked individually for `accepted_answer` field to determine if solved.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for:
- detailed component breakdown
- request/response flow diagrams
- state machine for unassign/reassign lifecycle
- persistence model
- testing strategy

## Operational Runbook

### Starting & Stopping

```bash
# Start service with build
docker compose up -d --build

# View logs in real-time
docker compose logs -f discourse-assignee-automation

# Stop service
docker compose down
```

### DRY_RUN: Testing vs. Production

1. **Test mode** (safe preview):
   ```bash
   DRY_RUN=true docker compose up -d
   ```
   Logs show what would be unassigned/reassigned without making changes.

2. **Production mode** (actual writes):
   ```bash
   # Edit .env
   DRY_RUN=false
   
   # Restart container
   docker compose up -d
   ```

After DRY_RUN change, use `docker compose up -d` (not restart) to reload .env.

### Verify Processing Status

Check logs for cycle summary:
```bash
docker compose logs discourse-assignee-automation | grep cycle_summary
```

Expected output:
```
cycle_summary {'total_fetched': 50, 'processed': 50, 'unassigned': 5, 'reassigned': 2, 'skipped': 43, 'failed': 0, 'duration_seconds': 45.123}
```

Health check endpoints:
```bash
curl http://localhost:8080/health/live    # Is service alive?
curl http://localhost:8080/health/ready   # Is it ready to process? (checks Discourse API + SQLite)
```

### State and History

- **SQLite database**: `/data/state.db` (persisted in Docker volume)
- **Volume name**: `discourse_assignee_state`
- **Action history**: all assign/unassign/skip/error actions are recorded
- **Auto-cleanup**: runs each cycle; deletes action records older than HISTORY_RETENTION_DAYS

To inspect the database:
```bash
docker compose exec discourse-assignee-automation python3 -c \
  "import sqlite3; db = sqlite3.connect('/data/state.db'); \
   print(db.execute('SELECT COUNT(*) FROM action_history').fetchone())"
```

### Backup before Changes

Before major operational changes, snapshot the state volume:
```bash
# List volumes
docker volume ls | grep assignee

# Backup state database
docker cp discourse_assignee_automation:/data/state.db ./state.db.backup
```

## Troubleshooting

### Service won't start / crashes on startup

- Check logs: `docker compose logs discourse-assignee-automation`
- Verify environment variables in .env (especially API_KEY, BASE_URL)
- Test Discourse reachability from the container:
  ```bash
  docker compose exec discourse-assignee-automation \
    curl -H "Api-Key: <your-key>" https://your-discourse.com/site.json
  ```

### Cycle fails with 429 (rate limited)

- Discourse API enforces rate limits
- Service retries with exponential backoff (default: up to 5 retries, max 20s wait)
- If frequent: increase POLL_INTERVAL_SECONDS or BATCH_SIZE

### State database grows very large

- Increase HISTORY_RETENTION_DAYS to reduce cleanup frequency
- Or manually delete old records (backup first!)
- Cleanup runs after each cycle

### Topics not being found

- Check if SEARCH_AFTER_DATE is set correctly (default: 2023-11-01)
- Verify Discourse Search API is accessible
- Check logs for search query errors

## Security Notes

- **Never commit .env** (contains API_KEY)
- **Never log API keys** (code uses masking in logs)
- **Use least-privilege API key** in Discourse (e.g., system user, minimal scope)
- **Rotate key periodically** if shared or exposed
- **.env file permissions**: should be readable only by the app (Docker handles this)

## Contributing

### Workflow

1. **Create a branch** for your feature:
   \\\ash
   git checkout -b feature/your-feature-name
   # or: feature/ticket-123_description
   # or: tmp/your-github-username/description
   \\\

2. **Make changes** and test locally:
   \\\ash
   # Edit files, then:
   pytest -q
   ruff check . && ruff format .
   \\\

3. **Commit with clear messages** (English, imperative mood):
   \\\ash
   git add path/to/file
   git commit -m "Add PM search support"
   git push origin feature/your-feature-name
   \\\

4. **Open Pull Request** on GitHub:
   - Link any related issues
   - Describe what changed and why
   - Ensure CI checks pass

### Guidelines

- **No force pushes** to open PRs or shared branches
- **File moves**: do in a separate commit before edits
- **History**: keep commits atomic and semantic
- **Tests**: add test coverage for new code
- **Docs**: update README/ARCHITECTURE if behavior changes

## License

See LICENSE file in repo (if applicable).

## Support

Issues and questions: [GitHub Issues](https://github.com/wb-aleksandr-khlebnikov/auto_unassign_solved_topics/issues)
