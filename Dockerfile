FROM python:3.13-slim

# ---------------------------------------------------------------------------
# System dependencies
# Single RUN layer to minimise image layers.
# ffmpeg: required for audio processing (Whisper STT transcription)
# git:    required by some Python packages at install time
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Python dependencies
# Copy requirements first so pip install is a cached layer and only re-runs
# when backend/requirements.txt changes, not on every source-code change.
# ---------------------------------------------------------------------------
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ---------------------------------------------------------------------------
# Pre-download the multilingual-e5-base embedding model (~280 MB).
# Baking it into the image means first container startup is instant;
# without this the model would download on the very first /chat request.
#
# The Whisper model is NOT pre-downloaded here because:
#   - It is served via the OpenAI Whisper API (no local model needed).
#   - The WHISPER_MODEL env var is still accepted for reference but the
#     download would add ~1-5 GB to the image for no benefit.
# ---------------------------------------------------------------------------
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

# ---------------------------------------------------------------------------
# Application source
# Copying after pip install so source changes do not bust the pip cache.
# frontend/build/ is included — it is served as static files by FastAPI.
# ---------------------------------------------------------------------------
COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
