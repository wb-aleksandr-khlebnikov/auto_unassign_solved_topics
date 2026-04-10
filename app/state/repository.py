from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.db.base import Base
from app.db.models import ActionHistory, TopicState
from app.models.domain import ActionRecord
from sqlalchemy.ext.asyncio import AsyncEngine


class StateRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def init_schema(self, engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ping(self) -> None:
        async with self._session_factory() as session:
            await session.execute(select(1))

    async def get_topic_state(self, topic_id: int) -> TopicState | None:
        async with self._session_factory() as session:
            return await session.get(TopicState, topic_id)

    async def list_topics_with_pending_reassign(self) -> Sequence[TopicState]:
        async with self._session_factory() as session:
            stmt = select(TopicState).where(
                TopicState.last_unassigned_username.is_not(None),
                TopicState.last_action == "unassigned",
            )
            return list((await session.execute(stmt)).scalars().all())

    async def upsert_unassigned_state(
        self,
        topic_id: int,
        assignee_user_id: int | None,
        assignee_username: str | None,
        last_seen_post_id: int,
    ) -> None:
        async with self._session_factory() as session:
            state = await session.get(TopicState, topic_id)
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
            await session.commit()

    async def mark_reassigned(self, topic_id: int) -> None:
        async with self._session_factory() as session:
            state = await session.get(TopicState, topic_id)
            now = datetime.now(UTC)
            if state is None:
                state = TopicState(topic_id=topic_id)
                session.add(state)
            state.last_action = "reassigned"
            state.last_reassigned_at = now
            state.last_unassigned_user_id = None
            state.last_unassigned_username = None
            state.updated_at = now
            await session.commit()

    async def mark_skipped(self, topic_id: int, last_seen_post_id: int | None = None) -> None:
        async with self._session_factory() as session:
            state = await session.get(TopicState, topic_id)
            now = datetime.now(UTC)
            if state is None:
                state = TopicState(topic_id=topic_id)
                session.add(state)
            state.last_action = "skipped"
            if last_seen_post_id is not None:
                state.last_seen_post_id = last_seen_post_id
            state.updated_at = now
            await session.commit()

    async def update_last_seen_post(self, topic_id: int, last_seen_post_id: int) -> None:
        async with self._session_factory() as session:
            state = await session.get(TopicState, topic_id)
            if state is None:
                return
            state.last_seen_post_id = last_seen_post_id
            state.updated_at = datetime.now(UTC)
            await session.commit()

    async def append_action(self, action: ActionRecord) -> None:
        async with self._session_factory() as session:
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
            await session.commit()

    async def cleanup_history(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        async with self._session_factory() as session:
            stmt = delete(ActionHistory).where(ActionHistory.created_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount)
