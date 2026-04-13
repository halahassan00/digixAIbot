"""
backend/main.py

FastAPI application entry point.

Registers all routes and middleware, then starts uvicorn.

Run locally:
    uvicorn backend.main:app --reload --port 8000

Run in Docker (see Dockerfile):
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI

from backend.api.middleware import add_cors, add_error_handler
from backend.api.routes.chat import router as chat_router
from backend.api.routes.leads import router as leads_router
from backend.api.routes.voice import router as voice_router

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
