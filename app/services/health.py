from __future__ import annotations

import logging

from app.clients.discourse import DiscourseClient
from app.clients.search import SearchClient
from app.config.settings import Settings
from app.state.repository import StateRepository

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(
        self,
        settings: Settings,
        state_repo: StateRepository,
        discourse_client: DiscourseClient,
        search_client: SearchClient,
    ) -> None:
        self._settings = settings
        self._state = state_repo
        self._discourse = discourse_client
        self._search = search_client

    async def readiness(self) -> tuple[bool, dict[str, str]]:
        checks: dict[str, str] = {
            "process": "ok",
            "sqlite": "ok",
            "discourse": "ok",
            "search": "ok",
        }

        try:
            await self._state.ping()
        except Exception as exc:
            checks["sqlite"] = f"error:{exc.__class__.__name__}"

        try:
            discourse_ok = await self._discourse.ping()
            if not discourse_ok:
                checks["discourse"] = "error:unexpected_response"
        except Exception as exc:
            checks["discourse"] = f"error:{exc.__class__.__name__}"

        try:
            search_ok = await self._search.ping()
            if not search_ok:
                checks["search"] = "error:unexpected_response"
        except Exception as exc:
            checks["search"] = f"error:{exc.__class__.__name__}"

        healthy = all(value == "ok" for value in checks.values())
        if not healthy:
            logger.warning("readiness_failed %s", checks)
        return healthy, checks
