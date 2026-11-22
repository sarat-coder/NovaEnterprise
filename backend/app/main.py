from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.research import router as research_router
from app.api.customers import router as customers_router
from app.api.decisions import router as decisions_router
from app.api.documents import router as documents_router
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.memory import router as memory_router
from app.core.config import get_settings
from app.core.health import register_check
from app.core.logging import configure_logging, get_logger
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("NovaEnterprise backend starting", extra={"env": settings.app_env})

    # Phase 1: application-level readiness check.
    register_check("app", lambda: {"status": "ok", "detail": "fastapi"})

    # Phase 2: initialise database (create tables) and seed sample data.
    from app.core.db import (
        get_session_factory,  # noqa: PLC0415
        init_db,  # noqa: PLC0415
    )
    from app.services.seed_service import seed  # noqa: PLC0415

    init_db()
    factory = get_session_factory()
    with factory() as session:
        seed(session)

    # Phase 3: Redis readiness check.
    from app.core.redis_client import register_redis_check  # noqa: PLC0415

    register_redis_check()

    # Phase 4: LLM readiness check.
    from app.core.llm import register_llm_check  # noqa: PLC0415

    register_llm_check()

    # Phase 6: Vector store readiness check.
    from rag.vector_store import register_vector_store_check  # noqa: PLC0415

    register_vector_store_check()

    # Phase 7: Graph store readiness check.
    from rag.graph_store import register_graph_store_check  # noqa: PLC0415

    register_graph_store_check()

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
    # CORS → RequestContext → RateLimit → Audit
    # With Starlette's add_middleware (insert-at-0 + reversed build), first added = outermost.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuditMiddleware)

    # Health routes are unprefixed (not under /api/v1)
    app.include_router(health_router)
    # Auth routes under /api/v1/auth
    app.include_router(auth_router)
    # Browse API routes (Phase 5)
    app.include_router(customers_router)
    app.include_router(incidents_router)
    app.include_router(decisions_router)
    # Documents + approvals (Phase 9)
    app.include_router(documents_router)
    # Knowledge graph (Phase 9)
    app.include_router(graph_router)
    # Memory API (Phase 10)
    app.include_router(memory_router)
    # Research API (Phase 12)
    app.include_router(research_router)

    return app


app = create_app()
