from fastapi import APIRouter
from sqlalchemy import text

from app.core.services.status import status_service
from app.deps import SessionDep
from app.schemas.status import ReadinessStatus, ServiceStatus

router = APIRouter()


@router.get("/live", response_model=ServiceStatus)
async def liveness() -> ServiceStatus:
    return status_service.get_status()


@router.get("/ready", response_model=ReadinessStatus)
async def readiness(session: SessionDep) -> ReadinessStatus:
    await session.execute(text("SELECT 1"))
    return ReadinessStatus(**status_service.get_status().model_dump())

