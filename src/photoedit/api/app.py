"""FastAPI application: JSON API under ``/api`` plus the built web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from photoedit import __version__
from photoedit.config import Settings, load_settings

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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    app = FastAPI(title="PhotoEditor", version=__version__)
    app.state.settings = settings

    @app.get("/api/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(status="ok", version=__version__)

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


def _safe_child(root: Path, relative: str) -> Path | None:
    """Resolve ``relative`` under ``root``; None if it escapes the root (path traversal)."""
    candidate = (root / relative).resolve()
    return candidate if candidate.is_relative_to(root.resolve()) else None
