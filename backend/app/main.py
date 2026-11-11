"""FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import make_url

from app.api.routes import router
from app.config import DEFAULT_DB_PATH, get_settings
from app.db.seed import build_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite" and url.database == str(DEFAULT_DB_PATH):
        build_database(DEFAULT_DB_PATH)  # no-op when the database already exists
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="InsightGraph API",
        description="Agentic SQL data analyst built with LangGraph and LangChain.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    dist = settings.frontend_dist
    if dist.is_dir() and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
