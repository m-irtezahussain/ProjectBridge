from fastapi import APIRouter

from app.api.routers.audit import router as audit_router
from app.api.routers.auth import router as auth_router
from app.api.routers.businesses import router as businesses_router
from app.api.routers.health import router as health_router
from app.api.routers.projects import router as projects_router
from app.api.routers.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(audit_router, prefix="/audit-events", tags=["audit"])
api_router.include_router(businesses_router, prefix="/businesses", tags=["businesses"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(
    tasks_router, prefix="/projects/{project_id}/tasks", tags=["tasks"]
)

