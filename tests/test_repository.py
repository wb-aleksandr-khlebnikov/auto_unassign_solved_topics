from datetime import UTC, datetime

from app.db.base import build_engine, build_session_factory
from app.models.domain import ActionRecord
from app.state.repository import StateRepository


def test_state_repository_roundtrip(tmp_path):
    db_path = tmp_path / "state.db"
    engine = build_engine(str(db_path))
    session_factory = build_session_factory(engine)
    repo = StateRepository(session_factory)
    repo.init_schema(engine)

    repo.upsert_unassigned_state(
        topic_id=42,
        assignee_user_id=101,
        assignee_username="alex",
        last_seen_post_id=900,
    )

    state = repo.get_topic_state(42)
    assert state is not None
    assert state.last_unassigned_username == "alex"
    assert state.last_seen_post_id == 900

    repo.append_action(
        ActionRecord(
            topic_id=42,
            action="unassigned",
            status="success",
            reason=None,
            assignee_user_id=101,
            assignee_username="alex",
            actor_user_id=None,
            post_id=None,
            timestamp=datetime.now(UTC),
        )
    )

    deleted = repo.cleanup_history(retention_days=0)
    assert deleted >= 0
