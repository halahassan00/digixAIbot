"""
backend/api/middleware.py

CORS configuration and global error handling for the FastAPI app.

Applied in main.py via app.add_middleware() and @app.exception_handler().
"""

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.utils.config import ALLOWED_ORIGINS
from backend.utils.logger import log_error

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def add_cors(app: FastAPI) -> None:
    """
    Allow the React frontend and digix-ai.com to call the backend.

    ALLOWED_ORIGINS is set in .env — during dev it includes localhost:3000,
    in production it includes https://digix-ai.com.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

def add_error_handler(app: FastAPI) -> None:
    """
    Catch any unhandled exception and return a clean JSON error response.

    Returns 500 with a generic message to the client (never raw tracebacks)
    and logs the full traceback server-side for debugging.
    """
    @app.exception_handler(Exception)
    async def _handler(request: Request, exc: Exception) -> JSONResponse:
        log_error(
            str(exc),
            context={
                "path": request.url.path,
                "method": request.method,
                "trace": traceback.format_exc()[-500:],   # last 500 chars
            },
        )
        return JSONResponse(
            status_code=500,
            content={"error": "حدث خطأ داخلي. يرجى المحاولة مرة أخرى."},
        )
