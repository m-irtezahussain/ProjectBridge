from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.db import create_database
from app.mcp.server import mcp_http_app, mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine, session_factory = create_database(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = session_factory

    async with mcp_server.session_manager.run():
        yield

    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ProjectBridge API",
        version="0.1.0",
        description="REST and MCP interfaces over the ProjectBridge shared core.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    app.include_router(api_router)
    app.mount("/mcp", mcp_http_app)
    return app


app = create_app()

