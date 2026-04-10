from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AssignmentInfo:
    user_id: int | None
    username: str | None


@dataclass(slots=True)
class TopicSnapshot:
    topic_id: int
    closed: bool
    archived: bool
    is_solved: bool
    assignment: AssignmentInfo
    post_ids: list[int]


@dataclass(slots=True)
class TopicCandidate:
    topic_id: int

    @staticmethod
    def from_explorer_row(row: dict[str, Any]) -> TopicCandidate | None:
        raw_id = row.get("topic_id")
        if raw_id is None:
            return None
        try:
            topic_id = int(raw_id)
        except (TypeError, ValueError):
            return None
        return TopicCandidate(topic_id=topic_id)


@dataclass(slots=True)
class CycleSummary:
    total_fetched: int = 0
    processed: int = 0
    unassigned: int = 0
    reassigned: int = 0
    skipped: int = 0
    failed: int = 0

    def as_log_dict(self, duration_seconds: float) -> dict[str, float | int]:
        return {
            "total_fetched": self.total_fetched,
            "processed": self.processed,
            "unassigned": self.unassigned,
            "reassigned": self.reassigned,
            "skipped": self.skipped,
            "failed": self.failed,
            "duration_seconds": round(duration_seconds, 3),
        }


@dataclass(slots=True)
class ActionRecord:
    topic_id: int
    action: str
    status: str
    reason: str | None
    assignee_user_id: int | None
    assignee_username: str | None
    actor_user_id: int | None
    post_id: int | None
    timestamp: datetime
