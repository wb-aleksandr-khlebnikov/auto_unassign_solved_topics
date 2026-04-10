from types import SimpleNamespace

import pytest

from app.models.domain import AssignmentInfo, TopicSnapshot
from app.services.processor import TopicProcessor


class FakeSearch:
    async def get_assigned_solved_topic_ids(self, after_date):
        return [1]

    async def get_assigned_pm_topic_ids(self):
        return []


class FakeDiscourse:
    def __init__(self):
        self.topic = TopicSnapshot(
            topic_id=1,
            closed=False,
            archived=False,
            is_solved=True,
            assignment=AssignmentInfo(user_id=7, username="user7"),
            post_ids=[10, 11],
        )

    async def get_topic_snapshot(self, topic_id):
        return TopicSnapshot(
            topic_id=self.topic.topic_id,
            closed=self.topic.closed,
            archived=self.topic.archived,
            is_solved=self.topic.is_solved,
            assignment=AssignmentInfo(
                user_id=self.topic.assignment.user_id,
                username=self.topic.assignment.username,
            ),
            post_ids=list(self.topic.post_ids),
        )

    async def get_post(self, post_id):
        return {"id": post_id, "staff": False}


class FakeAssign:
    def __init__(self, discourse):
        self.discourse = discourse
        self.unassign_calls = 0
        self.assign_calls = 0

    async def unassign(self, topic_id):
        self.unassign_calls += 1
        self.discourse.topic.assignment = AssignmentInfo(user_id=None, username=None)
        self.discourse.topic.post_ids.append(12)
        return 200

    async def assign(self, topic_id, assignee_user_id, assignee_username):
        self.assign_calls += 1
        self.discourse.topic.assignment = AssignmentInfo(
            user_id=assignee_user_id,
            username=assignee_username,
        )
        return 200


class FakeStateRepo:
    def __init__(self):
        self.states = {}
        self.pending = []

    async def get_topic_state(self, topic_id):
        return self.states.get(topic_id)

    async def list_topics_with_pending_reassign(self):
        return self.pending

    async def upsert_unassigned_state(
        self, topic_id, assignee_user_id, assignee_username, last_seen_post_id
    ):
        self.states[topic_id] = SimpleNamespace(
            topic_id=topic_id,
            last_unassigned_user_id=assignee_user_id,
            last_unassigned_username=assignee_username,
            last_seen_post_id=last_seen_post_id,
            last_action="unassigned",
        )
        self.pending = [self.states[topic_id]]

    async def mark_reassigned(self, topic_id):
        self.states[topic_id].last_action = "reassigned"
        self.pending = []

    async def mark_skipped(self, topic_id, last_seen_post_id=None):
        if topic_id in self.states and last_seen_post_id is not None:
            self.states[topic_id].last_seen_post_id = last_seen_post_id

    async def update_last_seen_post(self, topic_id, last_seen_post_id):
        if topic_id in self.states:
            self.states[topic_id].last_seen_post_id = last_seen_post_id

    async def append_action(self, action):
        return None

    async def cleanup_history(self, retention_days):
        return 0


@pytest.mark.asyncio
async def test_processor_unassign_and_reassign():
    settings = SimpleNamespace(
        search_after_date="2023-11-01",
        batch_size=50,
        history_retention_days=180,
        dry_run=False,
    )
    explorer = FakeSearch()
    discourse = FakeDiscourse()
    assign = FakeAssign(discourse)
    state = FakeStateRepo()

    processor = TopicProcessor(settings, explorer, discourse, assign, state)
    summary = await processor.run_cycle()

    assert summary.unassigned == 1
    assert summary.reassigned == 1
    assert assign.unassign_calls == 1
    assert assign.assign_calls == 1
