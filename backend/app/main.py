import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    audit,
    auth,
    cases,
    custodians,
    documents,
    export_jobs,
    import_jobs,
    redactions,
    review_sets,
    tags,
)
from app.config import DEFAULT_JWT_SECRET, get_settings

logger = logging.getLogger("app")
settings = get_settings()


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
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(custodians.router, prefix="/api")
app.include_router(import_jobs.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(documents.threads_router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(tags.document_tags_router, prefix="/api")
app.include_router(review_sets.router, prefix="/api")
app.include_router(redactions.router, prefix="/api")
app.include_router(export_jobs.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
