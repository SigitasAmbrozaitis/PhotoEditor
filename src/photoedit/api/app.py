"""FastAPI application: JSON API under ``/api`` plus the built web UI."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from photoedit import __version__
from photoedit.api.routes import router
from photoedit.config import Settings, load_settings
from photoedit.core.errors import ConflictError, InvalidRequestError, NotFoundError
from photoedit.safety import WriteNotAllowedError
from photoedit.services import Services

UI_NOT_BUILT_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>PhotoEditor</title></head>
<body style="font-family:system-ui;background:#1e1e1e;color:#ddd;padding:2rem">
<h1>PhotoEditor</h1>
<p>The web UI is not built yet.
Run <code>npm install</code> and <code>npm run build</code> in <code>ui/</code>,
or use the dev server (<code>npm run dev</code>).</p>
<p>The API is running: <a style="color:#8ab4f8" href="/api/health">/api/health</a></p>
</body></html>"""


class Health(BaseModel):
    status: str
    version: str


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    provider = _ServicesProvider(settings, services)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        provider.close()

    app = FastAPI(title="PhotoEditor", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.services = provider

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequestError)
    async def invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(WriteNotAllowedError)
    async def write_refused(_: Request, exc: WriteNotAllowedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.get("/api/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(status="ok", version=__version__)

    app.include_router(router)

    ui_dist = settings.ui_dist_dir

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def ui(full_path: str) -> Response:
        # Unknown API routes must stay JSON 404s, not fall through to the UI.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if full_path:
            candidate = _safe_child(ui_dist, full_path)
            if candidate is not None and candidate.is_file():
                return FileResponse(candidate)
        index = ui_dist / "index.html"
        if index.is_file():
            # Single-page app: client-side routes (e.g. /library) are served by index.html.
            return FileResponse(index)
        return HTMLResponse(UI_NOT_BUILT_HTML)

    return app


class _ServicesProvider:
    """Builds the services on first use, so ``create_app()`` alone (e.g. for ``photoedit openapi``) never
    creates a catalog or touches the workspace."""

    def __init__(self, settings: Settings, services: Services | None) -> None:
        self._settings = settings
        self._services = services
        self._lock = threading.Lock()
        self._factory: Callable[[Settings], Services] = Services

    def __call__(self) -> Services:
        with self._lock:
            if self._services is None:
                self._services = self._factory(self._settings)
            return self._services

    def close(self) -> None:
        with self._lock:
            if self._services is not None:
                self._services.close()
                self._services = None


def _safe_child(root: Path, relative: str) -> Path | None:
    """Resolve ``relative`` under ``root``; None if it escapes the root (path traversal)."""
    candidate = (root / relative).resolve()
    return candidate if candidate.is_relative_to(root.resolve()) else None
