"""
backend/tests/system/conftest.py

Shared fixtures for system tests.

OpenAI is mocked at the HTTP transport level via pytest-httpx so that the
retriever, embedder, and ChromaDB are exercised for real.  Google Sheets is
mocked by patching the synchronous _sync_submit function (gspread uses its
own HTTP stack, not httpx, so pytest-httpx cannot intercept it).
"""
import os

import pytest

# Prevent HuggingFace Hub from making HTTP requests to check for model updates.
# The multilingual-e5-base model is already cached; pytest-httpx would otherwise
# intercept the HEAD requests to huggingface.co and raise "No response can be found".
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _oai_envelope(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


# Canned model outputs used across multiple test files
_AR_CONTENT = (
    "تقدم Digix AI حلول الذكاء الاصطناعي المتعددة.\n"
    "[CHUNK_ID: services_ar_chunk_0]"
)
_EN_CONTENT = (
    "Power BI is a business analytics tool by Microsoft.\n"
    "[CHUNK_ID: services_chunk_0]"
)
_REFUSAL_CONTENT = "I don't have information about this topic in my knowledge base."


@pytest.fixture
def non_mocked_hosts() -> list[str]:
    """Allow HuggingFace Hub requests through pytest-httpx without interception.

    HF Hub uses httpx for model-file HEAD checks; without this, pytest-httpx
    intercepts them and causes the sentence-transformers tokenizer to fail.
    With HF_HUB_OFFLINE=1 these requests never fire anyway — this fixture is
    a belt-and-suspenders safety net for any other httpx calls the embedder makes.
    """
    return ["huggingface.co", "cdn-lfs.huggingface.co"]


@pytest.fixture
def mock_openai_ar(httpx_mock):
    """GPT-4o mock returning Arabic answer with services_ar_chunk_0 tag."""
    httpx_mock.add_response(
        url=_OPENAI_URL, method="POST", json=_oai_envelope(_AR_CONTENT)
    )
    return httpx_mock


@pytest.fixture
def mock_openai_en(httpx_mock):
    """GPT-4o mock returning English answer with services_chunk_0 tag."""
    httpx_mock.add_response(
        url=_OPENAI_URL, method="POST", json=_oai_envelope(_EN_CONTENT)
    )
    return httpx_mock


@pytest.fixture
def mock_openai_refusal(httpx_mock):
    """GPT-4o mock returning a topic-refusal with no [CHUNK_ID] tag."""
    httpx_mock.add_response(
        url=_OPENAI_URL, method="POST", json=_oai_envelope(_REFUSAL_CONTENT)
    )
    return httpx_mock
