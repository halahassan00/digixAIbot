<<<<<<< HEAD
# Digix AI Bot

A knowledge-base pipeline for building a RAG (Retrieval-Augmented Generation) chatbot for [digix-ai.com](https://digix-ai.com). The pipeline scrapes the Digix AI website, cleans and chunks the text, and enriches every chunk with metadata so it can be embedded and stored in a vector database.
This project was implemented for the purposes of a graduation project where we collaborated with DigixAI - a subsidary of Dinarak offering AI solutions and courses

---

## Project Structure

```
digix-chatbot/
│
├── README.md                          # Setup, run, and handover instructions
├── .env.example                       # Template for API keys — never commit .env
├── .gitignore
├── docker-compose.yml                 # Runs frontend + backend together
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt               # Python dependencies
│   ├── main.py                        # FastAPI entry point — registers all routes
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py                # POST /chat — main chatbot endpoint
│   │   │   ├── voice.py               # POST /transcribe — Whisper STT endpoint
│   │   │   └── leads.py               # POST /leads — manual lead submission
│   │   └── middleware.py              # CORS, logging, error handling
│   │
│   ├── rag/
│   │   ├── embedder.py                # Loads multilingual-e5, embeds text chunks
│   │   ├── retriever.py               # Queries ChromaDB, returns top-k chunks
│   │   ├── pipeline.py                # Ties retriever + LLM together — core RAG logic
│   │   └── prompts.py                 # System prompt templates (Arabic / English)
│   │
│   ├── vectorstore/
│   │   ├── chroma_store.py            # ChromaDB init, load, save
│   │   └── chroma_data/               # Persisted ChromaDB index lives here
│   │
│   ├── llm/
│   │   └── client.py                  # Groq client setup — swap to OpenAI here if needed
│   │
│   ├── voice/
│   │   ├── stt.py                     # Whisper speech-to-text logic
│   │   └── tts.py                     # Azure TTS logic — returns audio file/stream
│   │
│   ├── leads/
│   │   ├── collector.py               # Triggers lead collection in conversation flow
│   │   └── google_sheets.py           # Pushes collected data to Google Sheet via API
│   │
│   ├── language/
│   │   └── detector.py                # Detects Arabic vs English input, sets response language
│   │
│   └── utils/
│       ├── logger.py                  # Logs unanswered queries, errors, session events
│       └── config.py                  # Loads all env variables in one place
│
├── knowledge_base/
│   ├── scraper/
│   │   ├── scrape.py                  # Scrapes digix-ai.com, saves raw text per page
│   │   └── pages.py                   # List of all URLs to scrape
│   │
│   ├── processor/
│   │   ├── cleaner.py                 # Step 1 Strips HTML noise, remove scraper artefacts & boilerplate
│   │   ├── chunker.py                 # Splits text into 300-500 token chunks with overlap Step 2 split cleaned text into retrieval chunks
│   │   └── metadata.py                # Step 3 — run full pipeline, output chunks.json
│   │
|   ├── processed/
|   |   ├──chunks.json                  # Final output: all chunks with metadata 
|   |   ├──cleaned/                     # Intermediate: cleaned .txt files (one per page)
|   |   └──chunks/                      # Intermediate: human-readable chunk previews
│   ├── sync/
│   │   ├── sync.py                    # Full re-scrape + re-index pipeline — run to update
│   │   └── hash_store.json            # Stores page content hashes to detect changes
│   │
│   └── raw/                           # Raw scraped text files, one per page
│       ├── about.txt
│       ├── services.txt
│       ├── training.txt
│       ├── impact.txt
│       └── contact.txt
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── public/
    │   └── index.html
    └── src/
        ├── App.jsx
        ├── index.js                   # Embeddable entry point
        │
        ├── components/
        │   ├── ChatWidget.jsx         # Main chat bubble component
        │   ├── MessageList.jsx        # Renders conversation history
        │   ├── InputBar.jsx           # Text input + voice button
        │   ├── VoiceButton.jsx        # Mic button, recording state, sends to /transcribe
        │   └── LeadForm.jsx           # Inline form triggered during conversation
        │
        ├── hooks/
        │   ├── useChat.js             # Chat state, sends to /chat, handles responses
        │   └── useVoice.js            # Records audio, sends to /transcribe, plays TTS
        │
        ├── styles/
        │   ├── widget.css             # RTL layout, Arabic font stack (Tajawal/Cairo)
        │   └── themes.css             # DIGIX AI brand colors
        │
        └── utils/
            ├── api.js                 # All fetch calls to backend in one place
            └── language.js            # Switches UI direction (RTL/LTR) based on language
```
---

## Pipeline Overview

```
digix-ai.com
     │
     ▼
 scraper.py          fetch HTML, strip tags, save plain text
     │
     ▼
  raw/*.txt          one file per page, bilingual (EN + AR)
     │
     ▼
 cleaner.py          remove noise: "|" dividers → blank lines,
                     footer boilerplate, counter artefacts,
                     tag labels, step numbers, form markers
     │
     ▼
processed/cleaned/   clean, section-structured plain text
     │
     ▼
 chunker.py          paragraph-accumulation chunking (≤800 chars),
                     sentence-boundary fallback for long paragraphs
     │
     ▼
 metadata.py         attach source_file, category, language, URL,
                     chunk_index, char_count → serialize to JSON
     │
     ▼
processed/chunks.json   36 chunks ready for embedding
```

---

## Scraper

### `knowledge_base/scraper/pages.py`

The single source of truth for what gets scraped. Contains two lists:

- **`STATIC_PAGES`** — 12 pages (6 English + 6 Arabic) that are always present and scraped directly. Each entry has:
  - `url` — full URL
  - `category` — logical grouping (`home`, `about`, `services`, `training`, `impact`, `contact`)
  - `filename` — output filename under `raw/`
  - `language` — `"en"` or `"ar"`
  - `js_render` — `True` if the page requires JavaScript execution (training pages use this)

- **`DYNAMIC_SECTIONS`** — 4 section roots whose child pages are discovered at runtime by following links that match a `child_path` prefix. Used for individual training course pages and service detail pages once they exist.

### `knowledge_base/scraper/scraper.py`

Scrapes all pages defined in `pages.py` and saves plain text to `knowledge_base/raw/`.

**Key functions:**

| Function | Description |
|---|---|
| `fetch_page_static(url)` | HTTP GET via `requests`, with a browser User-Agent header |
| `fetch_page_js(url)` | Headless Chromium via Playwright — used for JS-rendered pages |
| `fetch_page(url, js_render)` | Router: delegates to static or JS fetch |
| `extract_text(html)` | BeautifulSoup — strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<head>`, `<noscript>`, then extracts and normalises text |
| `save_text(text, filename)` | Writes text to `raw/<filename>` |
| `discover_child_pages(section)` | Visits a section URL, finds all `<a>` links matching `child_path`, returns a list of page dicts |
| `scrape_all()` | Entry point — builds the full page list, scrapes each one, waits 1 s between requests |

**Run:**
```bash
python knowledge_base/scraper/scraper.py
```

---

## Processor

### `knowledge_base/processor/cleaner.py`

Removes scraper artefacts from raw text so only meaningful content remains.

**What it removes:**

| Pattern | Reason |
|---|---|
| Lines containing only `\|` | Section dividers added by the scraper — converted to blank lines to preserve structure |
| `•` alone on a line | Bullet markers that lost their content |
| `0`, `+`, `%` alone on a line | Animated counter placeholders from `impact.txt` (JS counters show `0` on initial load) |
| `*` alone on a line | Required-field markers from the contact form |
| `العربية` | Language-switcher link |
| `Show More` | Pagination button text from the training page |
| Lines matching `tags\.\S+` | Internal tag labels from the CMS (e.g. `tags.Cloud`, `tags.CRISC`) |
| Lines matching `^\d{2}$` | Step-number labels (e.g. `01`, `02`, `03`) |
| Everything from the copyright line onward | Footer boilerplate (copyright, "Powered by FikraTech", Privacy Policy, Terms of Use) |

Consecutive blank lines are collapsed into one.

**Public API:**

```python
from knowledge_base.processor.cleaner import clean_text, clean_file

clean_text(text: str) -> str          # clean a string
clean_file(filepath: str) -> str      # read a file and clean it
```

**Run standalone** (writes to `processed/cleaned/`):
```bash
python knowledge_base/processor/cleaner.py
```

---

### `knowledge_base/processor/chunker.py`

Splits cleaned text into retrieval-ready chunks of at most `max_chars` characters (default: **800**, roughly 150–200 tokens).

**Chunking strategy:**
1. Split on blank lines to obtain logical paragraphs (blank lines correspond to the original `|` section boundaries after cleaning).
2. Accumulate paragraphs into a buffer until adding the next one would exceed `max_chars` — then flush and start a new chunk.
3. If a single paragraph is itself longer than `max_chars`, apply sentence-boundary splitting as a fallback (splits on `.`, `!`, `?` followed by whitespace).

**Public API:**

```python
from knowledge_base.processor.chunker import chunk_text, chunk_file

chunk_text(text: str, max_chars: int = 800) -> list[str]
chunk_file(filepath: str, max_chars: int = 800) -> list[str]
```

**Run standalone** (reads from `processed/cleaned/`, writes preview files to `processed/chunks/`):
```bash
python knowledge_base/processor/chunker.py
```

---

### `knowledge_base/processor/metadata.py`

Orchestrates the full pipeline and produces the final JSON output.

**What it does:**
1. Builds a lookup table from `scraper/pages.py` mapping each filename to its URL, category, and language.
2. For every file in `raw/`, runs `clean_file` → `chunk_text`.
3. Wraps each chunk in a dict with a unique `id` and a `metadata` block.
4. Serialises everything to `processed/chunks.json`.

**Chunk schema:**
```json
{
  "id": "services_chunk_0",
  "text": "Our Services\nPath One\nAI Solutions for Organizations\n...",
  "metadata": {
    "source_file": "services.txt",
    "category": "services",
    "language": "en",
    "url": "https://digix-ai.com/services",
    "chunk_index": 0,
    "char_count": 777
  }
}
```

**Run (full pipeline — recommended entry point):**
```bash
python knowledge_base/processor/metadata.py
```

This is the only script you need to run day-to-day; it calls the cleaner and chunker internally.

---

## Raw Data

`knowledge_base/raw/` contains 12 plain-text files — one per scraped page. Files ending in `_ar.txt` are the Arabic versions of the same page.

| File | Content |
|---|---|
| `home.txt` / `home_ar.txt` | Hero section, key differentiators, partner logos, two service paths, impact stats, 90-day outcome promises |
| `about.txt` / `about_ar.txt` | Company story (founded 2016), vision, mission, regional expansion map |
| `services.txt` / `services_ar.txt` | AI Solutions (automation, decision intelligence, analytics, AI employees), Globally Accredited Training, Consulting services, 90-day outcome matrix |
| `training.txt` / `training_ar.txt` | Full catalogue of training programs grouped by domain: Fintech, AI, Blockchain, Cybersecurity, Project Management, GRC, Specialized, and Other Courses |
| `impact.txt` / `impact_ar.txt` | Impact numbers (note: counter values scrape as `0` due to JS animation), strategic partner list |
| `contact.txt` / `contact_ar.txt` | Contact details (website, email, address), contact form fields |

---

## Processed Output

`knowledge_base/processed/chunks.json` — **36 chunks** across all 12 pages, ready to be embedded and loaded into a vector store.

| Page | EN chunks | AR chunks |
|---|---|---|
| home | 6 | 5 |
| about | 3 | 2 |
| services | 5 | 2 |
| training | 4 | 4 |
| impact | 2 | 1 |
| contact | 1 | 1 |

`knowledge_base/processed/cleaned/` — intermediate cleaned text files (one per page).

`knowledge_base/processed/chunks/` — human-readable preview of how each page was split, with `--- chunk N ---` separators.

---

## Dependencies

```
beautifulsoup4==4.14.3
requests==2.33.1
playwright          # install separately for JS rendering
```

Install:
```bash
pip install -r requirments.txt
playwright install chromium
```

---

## Next Steps

The `chunks.json` file is the handoff point to the RAG layer. Typical next steps:

1. **Embed** — pass each chunk's `text` through an embedding model (e.g. `text-embedding-3-small`).
2. **Store** — insert vectors + metadata into a vector database (e.g. ChromaDB — note `chroma_data/` is already in `.gitignore`).
3. **Retrieve** — on user query, embed the query and find the top-k nearest chunks.
4. **Generate** — pass retrieved chunks as context to a language model (e.g. Claude) to produce a grounded answer.
