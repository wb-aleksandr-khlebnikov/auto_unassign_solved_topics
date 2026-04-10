from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.base import Base
from app.db.models import ActionHistory, TopicState
from app.models.domain import ActionRecord


class StateRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def init_schema(self, engine) -> None:
        Base.metadata.create_all(bind=engine)

    def ping(self) -> None:
        with self._session_factory() as session:
            session.execute(select(1))

    def get_topic_state(self, topic_id: int) -> TopicState | None:
        with self._session_factory() as session:
            return session.get(TopicState, topic_id)

    def list_topics_with_pending_reassign(self) -> Sequence[TopicState]:
        with self._session_factory() as session:
            stmt = select(TopicState).where(
                TopicState.last_unassigned_username.is_not(None),
                TopicState.last_action == "unassigned",
            )
            return list(session.execute(stmt).scalars().all())

    def upsert_unassigned_state(
        self,
        topic_id: int,
        assignee_user_id: int | None,
        assignee_username: str | None,
        last_seen_post_id: int,
    ) -> None:
        with self._session_factory() as session:
            state = session.get(TopicState, topic_id)
            now = datetime.now(UTC)
            if state is None:
                state = TopicState(topic_id=topic_id)
                session.add(state)
            state.last_unassigned_user_id = assignee_user_id
            state.last_unassigned_username = assignee_username
            state.last_action = "unassigned"
            state.last_seen_post_id = last_seen_post_id
            state.last_unassigned_at = now
            state.updated_at = now
            session.commit()

    def mark_reassigned(self, topic_id: int) -> None:
        with self._session_factory() as session:
            state = session.get(TopicState, topic_id)
            now = datetime.now(UTC)
            if state is None:
                state = TopicState(topic_id=topic_id)
                session.add(state)
            state.last_action = "reassigned"
            state.last_reassigned_at = now
            state.last_unassigned_user_id = None
            state.last_unassigned_username = None
            state.updated_at = now
            session.commit()

    def mark_skipped(self, topic_id: int, last_seen_post_id: int | None = None) -> None:
        with self._session_factory() as session:
            state = session.get(TopicState, topic_id)
            now = datetime.now(UTC)
            if state is None:
                state = TopicState(topic_id=topic_id)
                session.add(state)
            state.last_action = "skipped"
            if last_seen_post_id is not None:
                state.last_seen_post_id = last_seen_post_id
            state.updated_at = now
            session.commit()

    def update_last_seen_post(self, topic_id: int, last_seen_post_id: int) -> None:
        with self._session_factory() as session:
            state = session.get(TopicState, topic_id)
            if state is None:
                return
            state.last_seen_post_id = last_seen_post_id
            state.updated_at = datetime.now(UTC)
            session.commit()

    def append_action(self, action: ActionRecord) -> None:
        with self._session_factory() as session:
            row = ActionHistory(
                topic_id=action.topic_id,
                action=action.action,
                status=action.status,
                reason=action.reason,
                assignee_user_id=action.assignee_user_id,
                assignee_username=action.assignee_username,
                actor_user_id=action.actor_user_id,
                post_id=action.post_id,
                created_at=action.timestamp,
            )
            session.add(row)
            session.commit()

    def cleanup_history(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with self._session_factory() as session:
            rows = session.query(ActionHistory).filter(ActionHistory.created_at < cutoff).delete()
            session.commit()
            return int(rows)
