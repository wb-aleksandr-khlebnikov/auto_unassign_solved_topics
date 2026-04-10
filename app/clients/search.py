from __future__ import annotations

from app.clients.http import HttpClient


class SearchClient:
    def __init__(self, http: HttpClient):
        self._http = http

    async def get_assigned_solved_topic_ids(self, after_date: str) -> list[int]:
        topic_ids: list[int] = []
        page = 1
        while True:
            data = await self._http.request_json(
                "GET",
                "/search.json",
                params={"q": f"in:assigned status:solved after:{after_date}", "page": page},
            )
            topics = data.get("topics") or []
            if not topics:
                break
            topic_ids.extend(int(t["id"]) for t in topics if "id" in t)
            more = (
                data.get("grouped_search_result", {})
                .get("more_full_page_results", False)
            )
            if not more:
                break
            page += 1
            if page > 20:  # safety cap
                break
        return topic_ids

    async def get_assigned_pm_topic_ids(self) -> list[int]:
        """Return IDs of private message topics that are currently assigned.

        Uses ``in:assigned in:messages`` search — Discourse does not support
        ``status:solved`` for PM search, so the caller must check ``is_solved``
        on each topic individually.
        """
        topic_ids: list[int] = []
        page = 1
        while True:
            data = await self._http.request_json(
                "GET",
                "/search.json",
                params={"q": "in:assigned in:messages", "page": page},
            )
            topics = data.get("topics") or []
            if not topics:
                break
            topic_ids.extend(int(t["id"]) for t in topics if "id" in t)
            more = (
                data.get("grouped_search_result", {})
                .get("more_full_page_results", False)
            )
            if not more:
                break
            page += 1
            if page > 20:  # safety cap
                break
        return topic_ids

    async def ping(self) -> bool:
        data = await self._http.request_json(
            "GET",
            "/search.json",
            params={"q": "in:assigned status:solved"},
        )
        return "topics" in data
