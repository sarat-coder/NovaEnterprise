from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.health import register_check
from app.core.logging import configure_logging, get_logger
from app.middleware.request_context import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("NovaEnterprise backend starting", extra={"env": settings.app_env})

    # Phase 1: register the application-level readiness check.
    # Later phases add their own (database, redis, vector_store, graph_store, llm).
    register_check("app", lambda: {"status": "ok", "detail": "fastapi"})

    logger.info("Startup complete")
    yield
    logger.info("NovaEnterprise backend stopping")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="NovaEnterprise API",
        description="Enterprise Knowledge & Decision Intelligence Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware order (outermost first = executes first):
    # CORS → RequestContext (→ rate-limit in P3 → audit in P3)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    # Health routes are unprefixed (not under /api/v1)
    app.include_router(health_router)

    return app


app = create_app()
