from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TopicState(Base):
    __tablename__ = "topic_state"

    topic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_unassigned_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_unassigned_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_action: Mapped[str] = mapped_column(String(32), default="none")
    last_seen_post_id: Mapped[int] = mapped_column(Integer, default=0)
    last_unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ActionHistory(Base):
    __tablename__ = "action_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignee_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
