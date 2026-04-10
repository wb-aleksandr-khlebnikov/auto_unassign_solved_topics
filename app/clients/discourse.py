from __future__ import annotations

from typing import Any

from app.clients.http import HttpClient
from app.models.domain import AssignmentInfo, TopicSnapshot


class DiscourseClient:
    def __init__(self, http: HttpClient):
        self._http = http

    async def get_topic_snapshot(self, topic_id: int) -> TopicSnapshot:
        data = await self._http.request_json("GET", f"/t/{topic_id}.json")

        closed = bool(data.get("closed", False))
        archived = bool(data.get("archived", False))

        details = data.get("details", {}) if isinstance(data.get("details"), dict) else {}
        assigned = data.get("assigned_to_user")
        if not isinstance(assigned, dict):
            assigned = (
                details.get("assigned_to") if isinstance(details.get("assigned_to"), dict) else None
            )

        assignment = AssignmentInfo(
            user_id=(
                int(assigned.get("id"))
                if isinstance(assigned, dict) and assigned.get("id")
                else None
            ),
            username=(
                str(assigned.get("username"))
                if isinstance(assigned, dict) and assigned.get("username")
                else None
            ),
        )

        accepted_answer = data.get("accepted_answer")
        is_solved = isinstance(accepted_answer, dict)

        post_stream = (
            data.get("post_stream", {}) if isinstance(data.get("post_stream"), dict) else {}
        )
        stream = post_stream.get("stream", [])
        post_ids = [int(x) for x in stream if isinstance(x, int)]

        return TopicSnapshot(
            topic_id=topic_id,
            closed=closed,
            archived=archived,
            is_solved=is_solved,
            assignment=assignment,
            post_ids=post_ids,
        )

    async def get_post(self, post_id: int) -> dict[str, Any]:
        return await self._http.request_json("GET", f"/posts/{post_id}.json")

    async def ping(self) -> bool:
        data = await self._http.request_json("GET", "/site.json")
        return "site" in data or "users" in data
