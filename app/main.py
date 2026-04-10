from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.clients.assign import AssignClient
from app.clients.discourse import DiscourseClient
from app.clients.http import HttpClient, build_discourse_headers
from app.clients.search import SearchClient
from app.config.settings import get_settings
from app.db.base import build_engine, build_session_factory
from app.logging.setup import configure_logging
from app.scheduler.runner import SchedulerRunner
from app.services.health import HealthService
from app.services.processor import TopicProcessor
from app.state.repository import StateRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.sqlite_path)
    session_factory = build_session_factory(engine)
    state_repo = StateRepository(session_factory)
    state_repo.init_schema(engine)

    headers = build_discourse_headers(settings.discourse_api_key, settings.discourse_api_username)
    http = HttpClient(settings.discourse_base_url, headers, settings.retry)

    discourse_client = DiscourseClient(http)
    search_client = SearchClient(http)
    assign_client = AssignClient(http, settings)

    processor = TopicProcessor(
        settings, search_client, discourse_client, assign_client, state_repo
    )
    health_service = HealthService(settings, state_repo, discourse_client, search_client)
    scheduler = SchedulerRunner(processor, interval_seconds=settings.poll_interval_seconds)

    app.state.settings = settings
    app.state.state_repo = state_repo
    app.state.health_service = health_service
    app.state.scheduler = scheduler

    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await http.close()


app = FastAPI(title="Discourse Assignee Automation", lifespan=lifespan)
app.include_router(health_router)
