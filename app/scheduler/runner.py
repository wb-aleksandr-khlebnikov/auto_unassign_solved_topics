from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.processor import TopicProcessor

logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    running: bool = False
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_cycle_status: str = "never"


class SchedulerRunner:
    def __init__(self, processor: TopicProcessor, interval_seconds: int):
        self._processor = processor
        self._interval = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.state = SchedulerState()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self.state.running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self.state.running = False
        self._stop_event.set()
        if self._task:
            await self._task

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.state.last_cycle_started_at = datetime.now(UTC)
            try:
                await self._processor.run_cycle()
                self.state.last_cycle_status = "ok"
            except Exception:
                self.state.last_cycle_status = "error"
                logger.exception("cycle_crashed")
            self.state.last_cycle_finished_at = datetime.now(UTC)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                continue
