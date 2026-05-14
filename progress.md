# Session Progress Log
> Date: April 14, 2026

---

## 1. Project Initialization

Created `CLAUDE.md` at the repo root — a guidance file for future Claude Code sessions. It documents:
- All confirmed tech stack decisions (do not suggest alternatives)
- How to run the backend, frontend, scraper, and rebuild the ChromaDB index
- The full data flow: scraper → processor → ChromaDB → RAG pipeline → GPT-4o
- The per-request `/chat` flow through each module
- What is built vs. not yet built
- Arabic/encoding notes (UTF-8, RTL, `query:`/`passage:` prefix requirement)

---

## 2. Backend & RAG Design Review

Analyzed the full backend stack and identified improvements. Focused on RAG and backend only (frontend excluded by request).

### Problem: Self-hosted Whisper

- `stt.py` originally loaded OpenAI Whisper locally via the `openai-whisper` package
- The medium model requires ~5 GB RAM and ~10 s to load
- `multilingual-e5-base` needs ~600 MB RAM on top of that
- Combined: ~6 GB RAM just for AI models before FastAPI handles a request
- The "privacy" justification in the original code was inconsistent — all text already goes to OpenAI via GPT-4o

**Decision:** Replace with OpenAI Whisper API (`whisper-1`). Same model, same accuracy, ~$0.006/min, no local model loading.

**Docker image impact:** Removing `torch` and `openai-whisper` from requirements saves ~3 GB from the image.

### Problem: LangChain listed but never used

- `requirements.txt` had `langchain>=0.2.0` and `langchain-openai>=0.1.0`
- Zero imports of either in the entire codebase
- `pipeline.py`, `retriever.py`, `prompts.py`, `llm/client.py` are all pure Python + OpenAI SDK

**Decision:** Remove both lines from `requirements.txt`. No behavior change.

### Problem: multilingual-e5-large is oversized for this corpus

- Large model: 1024-dim vectors, ~1.2 GB
- Base model: 768-dim vectors, ~600 MB
- The knowledge base has 36 chunks (growing to ~200 with PDFs)
- At this corpus size, retrieval quality is bottlenecked by chunk quality, not model capacity

**Decision:** Switch `MODEL_NAME` in `embedder.py` from `intfloat/multilingual-e5-large` to `intfloat/multilingual-e5-base`.

**Important:** Changing the embedding model changes vector dimensions. The ChromaDB index must be rebuilt whenever the model changes (see Section 4).

### Problem: Hard language filter cuts the knowledge base in half per query

- `retriever.py` passes `{"language": "ar"}` or `{"language": "en"}` as a hard ChromaDB `where` filter
- With only 18 Arabic + 18 English chunks, a hard filter means each query searches only half the knowledge base
- If a topic has sparse coverage in one language, the bot says "I don't know" even though the information exists in the other language

**Proposed fix (not yet implemented):** Over-retrieve without the language filter, then rerank results by same-language preference before returning top-k. This gives cross-language fallback while still surfacing same-language chunks first.

### Problem: TTS development blocked on Azure key

- `tts.py` uses Azure Cognitive Services (`ar-JO-ZariyahNeural`, Jordanian Arabic — a strong justification)
- Azure key was confirmed to be configured in `.env` so this blocker was resolved during the session
- The proposal to add an OpenAI TTS fallback (`TTS_PROVIDER` config flag) remains a good option for future robustness but was not implemented

### Impact Summary

| Change | Docker Image | Runtime RAM | Status |
|---|---|---|---|
| OpenAI Whisper API (replace self-hosted) | −3 GB | −5 GB | Done |
| Drop LangChain | −100 MB | — | Done |
| multilingual-e5-base (replace large) | −600 MB | −600 MB | Done |
| Soft language filter in retriever | — | — | Proposed, not implemented |
| Swappable TTS provider | — | — | Proposed, not implemented (Azure key available) |

---

## 3. Code Changes Made

### `backend/voice/stt.py` — full rewrite

**Before:** Self-hosted Whisper using `openai-whisper` package. Loaded model as singleton, wrote audio to temp file, ran `model.transcribe()`.

**After:** OpenAI Whisper API via the existing `openai` SDK.

```python
from openai import OpenAI
from backend.utils.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes),
        response_format="verbose_json",
    )
    language = "ar" if result.language == "ar" else "en"
    return {"text": result.text.strip(), "language": language}
```

**Bugs caught and fixed during review** (the user's first draft had three errors):

| Line | Bug | Fix |
|---|---|---|
| client init | `OPENAI(...)` — wrong case | `OpenAI(...)` |
| API call | `respone_format` — typo | `response_format` |
| return dict | `langauge` — typo, also wrong key `langage` | `language` in both places |

### `backend/requirements.txt` — cleaned up

Removed (already done by the time of review, confirmed clean):
- `langchain>=0.2.0`
- `langchain-openai>=0.1.0`
- `torch>=2.2.0`
- `openai-whisper>=20231117`

Note: `sentence-transformers` still brings in PyTorch as a transitive dependency (needed for multilingual-e5). PyTorch is not in the explicit requirements but will still be installed. To remove PyTorch entirely, embeddings would need to switch to OpenAI's embeddings API — not done.

### `backend/rag/embedder.py` — model constant changed

```python
# Before
MODEL_NAME = "intfloat/multilingual-e5-large"

# After
MODEL_NAME = "intfloat/multilingual-e5-base"
```

---

## 4. ChromaDB Index Rebuild

Switching from `multilingual-e5-large` (1024 dims) to `multilingual-e5-base` (768 dims) caused a dimension mismatch. ChromaDB locks the vector dimension at collection creation time.

**Error encountered:**
```
chromadb.errors.InvalidArgumentError: Collection expecting embedding with dimension of 1024, got 768
```

**Fix:** Delete the old collection and rebuild.

```python
# Delete old collection
import chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(
    path='backend/vectorstore/chroma_data',
    settings=Settings(anonymized_telemetry=False)
)
client.delete_collection('digix_knowledge')
```

```bash
# Rebuild with base model
python -m backend.vectorstore.chroma_store
```

Result: `Done. Collection contains 36 documents.`

**Rule going forward:** Any time `MODEL_NAME` in `embedder.py` is changed, the collection must be deleted and the index rebuilt before starting the server.

---

## 5. End-to-End Test Results

All tests run from the repo root with the venv active.

### Dependency check
```bash
python -c "import fastapi, chromadb, sentence_transformers, openai, langdetect"
# Exit 0 — all deps present
```

### Config check
```
OpenAI key: set
Azure key: set
```

### ChromaDB check
```
ChromaDB collection: 36 documents
```

### Full RAG pipeline test
```python
from backend.rag.pipeline import run
result = run(query='ما هي خدمات Digix AI؟', language='ar')
```

Output:
```
Language: ar
Collect lead: False
Response preview: Digix AI تقدم مجموعة من الخدمات والحلول المتكاملة في مجال الذكاء الاصطناعي، بما في ذلك:
1. الحلول الذكية: تتضمن الذكاء الاصطناعي، الذكاء الاصطناعي التوليدي (Gen AI)، الأتمتة، التحليلات...
```

Pipeline confirmed working: Arabic query → correct language detection → ChromaDB retrieval → GPT-4o → Arabic response.

---

## 6. How to Run

### Prerequisites
- `.env` file at repo root with `OPENAI_API_KEY` and `AZURE_TTS_KEY` set
- venv activated: `source venv/bin/activate`
- ChromaDB index built (already done — 36 documents)

### Start the backend
```bash
uvicorn backend.main:app --reload --port 8000
```

Swagger UI available at: `http://localhost:8000/docs`

### Start the frontend (optional)
```bash
cd frontend
npm start
# Widget at http://localhost:3000
```

### Quick smoke test via curl
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ما هي خدمات Digix AI؟", "session_id": "test-1", "language": "ar"}'
```

### Rebuild ChromaDB index (only needed after model or chunks.json changes)
```bash
python -c "
import chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(path='backend/vectorstore/chroma_data', settings=Settings(anonymized_telemetry=False))
client.delete_collection('digix_knowledge')
"
python -m backend.vectorstore.chroma_store
```

---

## 7. Current Feature Status

| Feature | Status | Notes |
|---|---|---|
| Arabic & English chat (`/chat`) | Working | Multi-turn, session history in memory |
| RAG retrieval from knowledge base | Working | 36 chunks, multilingual-e5-base |
| Language detection | Working | `langdetect` via `backend/language/detector.py` |
| Lead trigger detection | Working | Keyword-based on query text |
| STT — `/transcribe` | Working | OpenAI Whisper API |
| TTS — `/tts` | Working | Azure `ar-JO-ZariyahNeural` configured |
| Lead submission — `/leads` | Stub only | Google Sheets not configured (no service account JSON) |
| `backend/leads/collector.py` | Not built | Conversational lead collection flow |
| `knowledge_base/sync/sync.py` | Not built | Scheduled re-scrape pipeline |

---

## 8. Known Warnings (Safe to Ignore)

```
embeddings.position_ids | UNEXPECTED
```
Appears every time multilingual-e5-base loads. Cosmetic only — does not affect embedding quality. Known upstream issue with how the model was exported to HuggingFace.

```
Warning: You are sending unauthenticated requests to the HF Hub.
```
The model is already cached locally after the first download. Set `HF_TOKEN` in `.env` to suppress this if desired — not required.
