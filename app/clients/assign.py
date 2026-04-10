from __future__ import annotations

from app.clients.http import HttpClient
from app.config.settings import Settings


class AssignClient:
    def __init__(self, http: HttpClient, settings: Settings):
        self._http = http
        self._settings = settings

    async def unassign(self, topic_id: int) -> int:
        payload = {
            self._settings.assign_payload_topic_key: topic_id,
            "target_type": "Topic",
        }
        return await self._http.request_status(
            "PUT",
            self._settings.assign_unassign_endpoint,
            json_body=payload,
        )

    async def assign(
        self,
        topic_id: int,
        assignee_user_id: int | None,
        assignee_username: str | None,
    ) -> int:
        if self._settings.assign_use_user_id:
            if assignee_user_id is None:
                raise ValueError("assignee_user_id is required when ASSIGN_USE_USER_ID=true")
            assignee_value: int | str = assignee_user_id
        else:
            if not assignee_username:
                raise ValueError("assignee_username is required when ASSIGN_USE_USER_ID=false")
            assignee_value = assignee_username

        payload = {
            self._settings.assign_payload_topic_key: topic_id,
            "target_type": "Topic",
            self._settings.assign_payload_user_key: assignee_value,
        }

        return await self._http.request_status(
            "PUT",
            self._settings.assign_assign_endpoint,
            json_body=payload,
        )
