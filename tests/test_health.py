from types import SimpleNamespace

import pytest

from app.services.health import HealthService


class OkState:
    async def ping(self):
        return None


class BadState:
    async def ping(self):
        raise RuntimeError("db down")


class OkDiscourse:
    async def ping(self):
        return True


class OkSearch:
    async def ping(self):
        return True


@pytest.mark.asyncio
async def test_readiness_ok():
    settings = SimpleNamespace()
    svc = HealthService(settings, OkState(), OkDiscourse(), OkSearch())
    healthy, checks = await svc.readiness()

    assert healthy is True
    assert checks["sqlite"] == "ok"


@pytest.mark.asyncio
async def test_readiness_degraded_on_db_error():
    settings = SimpleNamespace()
    svc = HealthService(settings, BadState(), OkDiscourse(), OkSearch())
    healthy, checks = await svc.readiness()

    assert healthy is False
    assert checks["sqlite"].startswith("error")
