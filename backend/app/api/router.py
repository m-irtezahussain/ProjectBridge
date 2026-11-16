from fastapi import APIRouter

from app.api.routers.auth import router as auth_router
from app.api.routers.businesses import router as businesses_router
from app.api.routers.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(businesses_router, prefix="/businesses", tags=["businesses"])

