from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, cases, custodians
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="PST Document Review")

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


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
