from pathlib import Path

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.main import app


class SPAStaticFiles(StaticFiles):
    """Serve built frontend assets and fall back to index.html for SPA routes."""

    async def get_response(self, path: str, scope: dict) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or scope.get("method") not in {"GET", "HEAD"}:
                raise
            return await super().get_response("index.html", scope)


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if not FRONTEND_DIST.is_dir():
    raise RuntimeError(f"Frontend build not found at {FRONTEND_DIST}")

# As rotas /api/* e /health já foram registradas antes deste mount.
app.mount("/", SPAStaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")