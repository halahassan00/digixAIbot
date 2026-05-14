"""
backend/main.py

FastAPI application entry point.

Registers all routes and middleware, then starts uvicorn.

Run locally:
    uvicorn backend.main:app --reload --port 8000

Run in Docker (see Dockerfile):
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.middleware import add_cors, add_error_handler
from backend.api.routes.chat import router as chat_router
from backend.api.routes.leads import router as leads_router
from backend.api.routes.voice import router as voice_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DIGIX AI Chatbot API",
    description="Arabic-first RAG chatbot for digix-ai.com",
    version="1.0.0",
    docs_url="/docs",     # Swagger UI — disable in production if needed
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

add_cors(app)
add_error_handler(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(leads_router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Used by Railway/Render/Docker to verify the container is running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend widget (static files)
# ---------------------------------------------------------------------------
# Route order matters: /widget/main.js must be a named route registered BEFORE
# the app.mount("/widget", ...) call below, otherwise the StaticFiles mount
# intercepts it first and the stable URL would not be reachable.

_BUILD_DIR = Path(__file__).resolve().parents[1] / "frontend" / "build"

if _BUILD_DIR.exists():
    # Read the asset manifest to resolve the content-hashed JS filename.
    # This gives DIGIX AI a stable embed URL (/widget/main.js) that does not
    # change between deployments even though the actual file has a hash suffix.
    _js_src: Path | None = None
    try:
        _manifest = json.loads((_BUILD_DIR / "asset-manifest.json").read_text())
        _js_src = _BUILD_DIR / _manifest["files"]["main.js"].lstrip("/")
    except Exception:
        logger.warning("frontend/build/asset-manifest.json missing or malformed — /widget/main.js will 404")

    if _js_src and _js_src.exists():
        @app.get("/widget/main.js", include_in_schema=False)
        async def _widget_js() -> FileResponse:
            """Stable entry-point URL for the chat widget script."""
            return FileResponse(str(_js_src), media_type="application/javascript")

    @app.get("/", include_in_schema=False)
    async def _serve_root() -> FileResponse:
        """Serve the widget landing page at the root URL."""
        return FileResponse(str(_BUILD_DIR / "index.html"))

    # index.html references /static/css/... and /static/js/... as root-relative
    # paths. Mount the build's static sub-directory at /static so those URLs
    # resolve correctly regardless of where the widget is embedded.
    app.mount(
        "/static",
        StaticFiles(directory=str(_BUILD_DIR / "static")),
        name="frontend-static",
    )

    # Mount the full build directory at /widget for everything else
    # (asset-manifest.json, favicon, etc.).
    app.mount(
        "/widget",
        StaticFiles(directory=str(_BUILD_DIR), html=True),
        name="widget",
    )
