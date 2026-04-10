from types import SimpleNamespace

import pytest

from app.models.domain import AssignmentInfo, TopicSnapshot
from app.services.processor import TopicProcessor


class FakeSearch:
    async def get_assigned_solved_topic_ids(self, after_date):
        return [99]

    async def get_assigned_pm_topic_ids(self):
        return []


class FakeDiscourse:
    async def get_topic_snapshot(self, topic_id):
        return TopicSnapshot(
            topic_id=99,
            closed=False,
            archived=False,
            is_solved=False,
            assignment=AssignmentInfo(user_id=10, username="agent"),
            post_ids=[1, 2, 3],
        )

    async def get_post(self, post_id):
        return {"id": post_id, "staff": False}


class FakeAssign:
    async def unassign(self, topic_id):
        raise AssertionError("unassign must not be called for unsolved topic")

    async def assign(self, topic_id, assignee_user_id, assignee_username):
        raise AssertionError("assign must not be called in this test")


class FakeStateRepo:
    async def get_topic_state(self, topic_id):
        return None

    async def list_topics_with_pending_reassign(self):
        return []

    async def upsert_unassigned_state(
        self, topic_id, assignee_user_id, assignee_username, last_seen_post_id
    ):
        raise AssertionError("state upsert must not be called for unsolved topic")

    async def mark_reassigned(self, topic_id):
        return None

    async def mark_skipped(self, topic_id, last_seen_post_id=None):
        return None

    async def update_last_seen_post(self, topic_id, last_seen_post_id):
        return None

    async def append_action(self, action):
        return None

    async def cleanup_history(self, retention_days):
        return 0


@pytest.mark.asyncio
async def test_unsolved_topic_is_skipped_before_unassign():
    settings = SimpleNamespace(
        search_after_date="2023-11-01",
        batch_size=50,
        history_retention_days=180,
        dry_run=False,
    )

    processor = TopicProcessor(
        settings, FakeSearch(), FakeDiscourse(), FakeAssign(), FakeStateRepo()
    )
    summary = await processor.run_cycle()

    assert summary.processed == 1
    assert summary.skipped == 1
    assert summary.unassigned == 0
