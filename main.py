"""Escrow API entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.escrow.api.experiments_dashboard import router as experiments_router
from src.escrow.api.fund import router as fund_router
from src.escrow.api.jobs import router as jobs_router
from src.escrow.api.metrics_endpoint import router as metrics_router
from src.escrow.api.settle import router as settle_router
from src.escrow.api.start import router as start_router
from src.escrow.api.submit import router as submit_router
from src.escrow.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Ensure DB tables exist before first request (TestClient may not run lifespan)
init_db()

app = FastAPI(title="Agentic Escrow API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)
app.include_router(fund_router)
app.include_router(start_router)
app.include_router(submit_router)
app.include_router(settle_router)
app.include_router(metrics_router)
app.include_router(experiments_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
