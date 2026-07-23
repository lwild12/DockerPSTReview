import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.routers import (
    admin,
    audit,
    auth,
    cases,
    coding_fields,
    custodians,
    documents,
    export_jobs,
    import_jobs,
    redactions,
    review_sets,
    tags,
)
from app.config import DEFAULT_JWT_SECRET, get_settings
from app.db import get_db
from app.models.system_settings import SystemSettings

logger = logging.getLogger("app")
settings = get_settings()

_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        logger.warning(
            "JWT_SECRET is still set to the default placeholder value — sessions are "
            "forgeable. Set a long random JWT_SECRET via the environment before deploying."
        )
    yield


app = FastAPI(
    title="PST Document Review",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def gate_api_docs(request: Request, call_next):
    # enable_api_docs is admin-toggleable at runtime (see the admin router),
    # so it's checked live against the DB rather than baked in at startup.
    # Goes through the same get_db dependency as everything else (rather than
    # the module-level engine directly) so tests' dependency_overrides apply.
    if request.url.path in _DOCS_PATHS:
        db_dependency = request.app.dependency_overrides.get(get_db, get_db)
        db_gen = db_dependency()
        db = await anext(db_gen)
        try:
            result = await db.execute(select(SystemSettings.enable_api_docs).limit(1))
            row = result.scalar_one_or_none()
        finally:
            await db_gen.aclose()
        enabled = row if row is not None else settings.enable_api_docs
        if not enabled:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(custodians.router, prefix="/api")
app.include_router(import_jobs.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(documents.threads_router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(tags.document_tags_router, prefix="/api")
app.include_router(coding_fields.router, prefix="/api")
app.include_router(coding_fields.document_coding_router, prefix="/api")
app.include_router(review_sets.router, prefix="/api")
app.include_router(redactions.router, prefix="/api")
app.include_router(redactions.case_log_router, prefix="/api")
app.include_router(export_jobs.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
