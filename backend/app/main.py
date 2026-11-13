"""FastAPI application factory for The Idea Board."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .db import build_engine, run_migrations, session_scope, wait_for_database
from .models import Idea
from .schemas import IdeaCreate, IdeaOut

log = logging.getLogger("idea_board")


class _JsonFormatter(logging.Formatter):
    """One JSON object per line: easy for humans, `kubectl logs` and the AI health check."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our middleware


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


# Module level on purpose: with postponed annotations FastAPI resolves these names
# from module globals, so a dependency alias defined inside create_app() is invisible.
SessionDep = Annotated[Session, Depends(get_session)]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings.sqlalchemy_url)
        wait_for_database(engine, settings.db_connect_timeout_seconds)
        run_migrations(engine)
        app.state.engine = engine
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
        log.info("startup complete", extra={"fields": {"db_dialect": engine.dialect.name}})
        yield
        engine.dispose()

    app = FastAPI(title="The Idea Board API", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception(
                "unhandled error",
                extra={"fields": {"method": request.method, "path": request.url.path}},
            )
            response = JSONResponse({"detail": "internal server error"}, status_code=500)
        fields = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        }
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        if request.url.path not in ("/healthz", "/readyz") or response.status_code >= 400:
            log.log(level, "request", extra={"fields": fields})
        return response

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        """Liveness: the process is up. Deliberately does not touch the database."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz(session: SessionDep) -> dict[str, str]:
        """Readiness: the database answers."""
        try:
            session.execute(text("SELECT 1"))
        except Exception as exc:
            log.error("readiness check failed", extra={"fields": {"error": str(exc)}})
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from exc
        return {"status": "ready"}

    @app.get("/api/ideas", response_model=list[IdeaOut], tags=["ideas"])
    def list_ideas(session: SessionDep) -> list[Idea]:
        stmt = select(Idea).order_by(Idea.created_at.desc(), Idea.id.desc())
        return list(session.scalars(stmt))

    @app.post(
        "/api/ideas",
        response_model=IdeaOut,
        status_code=status.HTTP_201_CREATED,
        tags=["ideas"],
    )
    def create_idea(payload: IdeaCreate, session: SessionDep) -> Idea:
        if len(payload.content) > settings.max_idea_length:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"content must be at most {settings.max_idea_length} characters",
            )
        idea = Idea(content=payload.content)
        session.add(idea)
        session.commit()
        session.refresh(idea)
        return idea

    return app
