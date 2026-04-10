from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(request: Request):
    health_service = request.app.state.health_service
    scheduler = request.app.state.scheduler

    ready, checks = await health_service.readiness()
    body = {
        "status": "ok" if ready else "degraded",
        "checks": checks,
        "scheduler": {
            "running": scheduler.state.running,
            "last_cycle_started_at": (
                scheduler.state.last_cycle_started_at.isoformat()
                if scheduler.state.last_cycle_started_at
                else None
            ),
            "last_cycle_finished_at": (
                scheduler.state.last_cycle_finished_at.isoformat()
                if scheduler.state.last_cycle_finished_at
                else None
            ),
            "last_cycle_status": scheduler.state.last_cycle_status,
        },
    }
    code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=body, status_code=code)
