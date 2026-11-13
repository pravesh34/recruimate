"""RecruiMate API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import (
    account,
    auth,
    compatibility,
    dashboard,
    interviews,
    jobs,
    pipeline,
    providers,
    resume,
    skill_gaps,
)
from .config import BASE_DIR, settings
from .database.models import init_db
from .graph.workflow import SupervisorAgent
from .services.embedding_service import get_embedding_service
from .services.resume_parser import ResumeParseError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("recruimate")

FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    logger.info("RecruiMate ready — embeddings: %s", get_embedding_service().name)
    yield


app = FastAPI(
    title="RecruiMate API",
    description="Candidate-side AI career and interview preparation platform.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ResumeParseError)
async def resume_error_handler(request: Request, exc: ResumeParseError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "embeddings": get_embedding_service().name,
        "engine": SupervisorAgent.__name__,
        "auth": "accounts" if settings.auth_enabled else ("token" if settings.api_token else "trusted-local"),
    }


for module in (auth, resume, jobs, compatibility, skill_gaps, interviews, providers, dashboard, pipeline, account):
    app.include_router(module.router)


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {
            "message": "RecruiMate API is running. Build the frontend (`cd frontend && npm run build`) "
            "or run `npm run dev` on port 5173.",
            "docs": "/docs",
        }
    )
