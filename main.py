"""Agent Escrow API + public landing / docs site (single-service deploy)."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.escrow.api.experiments_dashboard import router as experiments_router
from src.escrow.api.fund import router as fund_router
from src.escrow.api.jobs import router as jobs_router
from src.escrow.api.metrics_endpoint import router as metrics_router
from src.escrow.api.settle import router as settle_router
from src.escrow.api.start import router as start_router
from src.escrow.api.submit import router as submit_router
from src.escrow.api.verification_ai import router as ai_verification_router
from src.escrow.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Ensure DB tables exist before first request (TestClient may not run lifespan)
init_db()

app = FastAPI(
    title="Agent Escrow API",
    description=(
        "Middleware for safe, programmable agent-to-agent transactions. "
        "See / for the landing page, /docs for the interactive API explorer."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# --- CORS ------------------------------------------------------------------
# Local dev origins always allowed; production origins configurable via env.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
_extra = os.environ.get("ESCROW_CORS_ORIGINS", "").strip()
_origins = list(_default_origins) + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if "*" not in _extra else ["*"],
    allow_credentials="*" not in _extra,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---------------------------------------------------------------
app.include_router(jobs_router)
app.include_router(fund_router)
app.include_router(start_router)
app.include_router(submit_router)
app.include_router(ai_verification_router)
app.include_router(settle_router)
app.include_router(metrics_router)
app.include_router(experiments_router)


# --- Public site -----------------------------------------------------------
_SITE_DIR = Path(__file__).resolve().parent / "site"
if _SITE_DIR.is_dir():
    app.mount("/site", StaticFiles(directory=_SITE_DIR, html=True), name="site")


@app.get("/", include_in_schema=False)
def root() -> Response:
    """Serve the landing / docs page at the root."""
    index = _SITE_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse(
        {
            "name": "Agent Escrow",
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
        }
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
