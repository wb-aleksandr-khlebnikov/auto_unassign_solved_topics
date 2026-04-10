from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from app.clients.assign import AssignClient
from app.clients.discourse import DiscourseClient
from app.clients.search import SearchClient
from app.config.settings import Settings
from app.db.models import TopicState
from app.models.domain import ActionRecord, CycleSummary
from app.state.repository import StateRepository

logger = logging.getLogger(__name__)


class TopicProcessor:
    def __init__(
        self,
        settings: Settings,
        search_client: SearchClient,
        discourse_client: DiscourseClient,
        assign_client: AssignClient,
        state_repo: StateRepository,
    ) -> None:
        self._settings = settings
        self._search = search_client
        self._discourse = discourse_client
        self._assign = assign_client
        self._state = state_repo

    async def run_cycle(self) -> CycleSummary:
        started = perf_counter()
        summary = CycleSummary()

        try:
            topic_ids = await self._search.get_assigned_solved_topic_ids(
                self._settings.search_after_date
            )
        except Exception:
            logger.exception("failed_to_fetch_solved_topics")
            summary.failed += 1
            return summary

        try:
            pm_ids = await self._search.get_assigned_pm_topic_ids()
        except Exception:
            logger.exception("failed_to_fetch_pm_topics")
            pm_ids = []

        topic_ids = sorted(set(topic_ids) | set(pm_ids))
        summary.total_fetched = len(topic_ids)

        for i in range(0, len(topic_ids), self._settings.batch_size):
            batch = topic_ids[i : i + self._settings.batch_size]
            for topic_id in batch:
                summary.processed += 1
                try:
                    result = await self._process_unassign(topic_id)
                    self._inc(summary, result)
                except Exception:
                    summary.failed += 1
                    logger.exception("topic_unassign_failed topic_id=%s", topic_id)

        pending_reassign = await self._state.list_topics_with_pending_reassign()
        for row in pending_reassign:
            try:
                result = await self._process_reassign(row)
                self._inc(summary, result)
            except Exception:
                summary.failed += 1
                logger.exception("topic_reassign_failed topic_id=%s", row.topic_id)

        deleted = await self._state.cleanup_history(self._settings.history_retention_days)
        duration = perf_counter() - started
        logger.info("cycle_summary %s retention_deleted=%s", summary.as_log_dict(duration), deleted)
        return summary

    async def _process_unassign(self, topic_id: int) -> str:
        snapshot = await self._discourse.get_topic_snapshot(topic_id)

        if snapshot.closed or snapshot.archived:
            await self._record(
                topic_id, "skipped", "success", "topic_closed_or_archived", snapshot.assignment
            )
            await self._state.mark_skipped(topic_id, max(snapshot.post_ids, default=0))
            return "skipped"

        if not snapshot.is_solved:
            await self._record(
                topic_id, "skipped", "success", "topic_not_solved_now", snapshot.assignment
            )
            await self._state.mark_skipped(topic_id, max(snapshot.post_ids, default=0))
            return "skipped"

        if snapshot.assignment.username is None and snapshot.assignment.user_id is None:
            await self._record(
                topic_id, "skipped", "noop", "assignment_absent", snapshot.assignment
            )
            await self._state.mark_skipped(topic_id, max(snapshot.post_ids, default=0))
            return "skipped"

        previous = await self._state.get_topic_state(topic_id)
        if (
            previous is not None
            and previous.last_action == "reassigned"
            and previous.last_unassigned_username
            and previous.last_unassigned_username == snapshot.assignment.username
        ):
            await self._record(
                topic_id, "skipped", "success", "loop_guard_recent_reassign", snapshot.assignment
            )
            await self._state.mark_skipped(topic_id, max(snapshot.post_ids, default=0))
            return "skipped"

        latest = await self._discourse.get_topic_snapshot(topic_id)
        if latest.closed or latest.archived:
            await self._record(
                topic_id, "skipped", "success", "topic_changed_before_unassign", latest.assignment
            )
            await self._state.mark_skipped(topic_id, max(latest.post_ids, default=0))
            return "skipped"

        if not latest.is_solved:
            await self._record(
                topic_id,
                "skipped",
                "success",
                "topic_not_solved_after_refresh",
                latest.assignment,
            )
            await self._state.mark_skipped(topic_id, max(latest.post_ids, default=0))
            return "skipped"

        if latest.assignment.username is None and latest.assignment.user_id is None:
            await self._record(
                topic_id, "skipped", "noop", "assignment_absent_after_refresh", latest.assignment
            )
            await self._state.mark_skipped(topic_id, max(latest.post_ids, default=0))
            return "skipped"

        if self._settings.dry_run:
            await self._record(
                topic_id, "unassigned", "dry-run", "would_unassign", latest.assignment
            )
            return "unassigned"

        status = await self._assign.unassign(topic_id)
        if status >= 400:
            await self._record(
                topic_id, "failed", "error", f"unassign_http_{status}", latest.assignment
            )
            return "failed"

        await self._state.upsert_unassigned_state(
            topic_id=topic_id,
            assignee_user_id=latest.assignment.user_id,
            assignee_username=latest.assignment.username,
            last_seen_post_id=max(latest.post_ids, default=0),
        )
        await self._record(topic_id, "unassigned", "success", None, latest.assignment)
        return "unassigned"

    async def _process_reassign(self, state_row: TopicState) -> str:
        topic_id = state_row.topic_id
        snapshot = await self._discourse.get_topic_snapshot(topic_id)

        if snapshot.closed or snapshot.archived:
            await self._record(
                topic_id, "skipped", "success", "topic_closed_or_archived", snapshot.assignment
            )
            await self._state.mark_skipped(
                topic_id, max(snapshot.post_ids, default=state_row.last_seen_post_id)
            )
            return "skipped"

        if snapshot.assignment.username is not None or snapshot.assignment.user_id is not None:
            if (
                state_row.last_unassigned_username
                and snapshot.assignment.username == state_row.last_unassigned_username
            ):
                await self._state.mark_reassigned(topic_id)
                await self._record(
                    topic_id,
                    "reassigned",
                    "success",
                    "already_assigned_expected_user",
                    snapshot.assignment,
                )
                return "reassigned"
            await self._record(
                topic_id, "skipped", "success", "already_assigned_other_user", snapshot.assignment
            )
            return "skipped"

        new_posts = sorted([pid for pid in snapshot.post_ids if pid > state_row.last_seen_post_id])
        if not new_posts:
            return "skipped"

        trigger_post_id: int | None = None
        for post_id in new_posts:
            post = await self._discourse.get_post(post_id)
            user_is_staff = bool(post.get("staff", False))
            if not user_is_staff:
                trigger_post_id = post_id
                break

        await self._state.update_last_seen_post(topic_id, last_seen_post_id=max(new_posts))

        if trigger_post_id is None:
            await self._record(
                topic_id, "skipped", "success", "new_posts_staff_only", snapshot.assignment
            )
            return "skipped"

        assignee_user_id = state_row.last_unassigned_user_id
        assignee_username = state_row.last_unassigned_username
        if assignee_user_id is None and not assignee_username:
            await self._record(
                topic_id, "failed", "error", "no_saved_assignee", snapshot.assignment
            )
            return "failed"

        latest = await self._discourse.get_topic_snapshot(topic_id)
        if latest.assignment.username is not None or latest.assignment.user_id is not None:
            await self._record(
                topic_id,
                "skipped",
                "success",
                "assignment_appeared_before_reassign",
                latest.assignment,
            )
            return "skipped"

        if self._settings.dry_run:
            await self._record(
                topic_id,
                "reassigned",
                "dry-run",
                f"would_reassign_on_post_{trigger_post_id}",
                latest.assignment,
                post_id=trigger_post_id,
            )
            return "reassigned"

        status = await self._assign.assign(topic_id, assignee_user_id, assignee_username)
        if status >= 400:
            await self._record(
                topic_id, "failed", "error", f"assign_http_{status}", latest.assignment
            )
            return "failed"

        await self._state.mark_reassigned(topic_id)
        await self._record(
            topic_id,
            "reassigned",
            "success",
            f"trigger_post_{trigger_post_id}",
            latest.assignment,
            post_id=trigger_post_id,
        )
        return "reassigned"

    async def _record(
        self,
        topic_id: int,
        action: str,
        status: str,
        reason: str | None,
        assignment,
        post_id: int | None = None,
    ) -> None:
        await self._state.append_action(
            ActionRecord(
                topic_id=topic_id,
                action=action,
                status=status,
                reason=reason,
                assignee_user_id=assignment.user_id,
                assignee_username=assignment.username,
                actor_user_id=None,
                post_id=post_id,
                timestamp=datetime.now(UTC),
            )
        )

    @staticmethod
    def _inc(summary: CycleSummary, key: str) -> None:
        if key == "unassigned":
            summary.unassigned += 1
        elif key == "reassigned":
            summary.reassigned += 1
        elif key == "skipped":
            summary.skipped += 1
        elif key == "failed":
            summary.failed += 1
