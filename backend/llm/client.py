"""
backend/llm/client.py

GPT-4o client via the OpenAI API.

This is the only place in the backend that calls OpenAI.
pipeline.py calls chat(messages) and gets back a plain string —
nothing here leaks OpenAI types into the rest of the codebase.

Model: gpt-4o — non-negotiable per CONTEXT.md (best Arabic dialect support).
Temperature: 0.3 — low, because answers must be grounded in retrieved
context, not creative. Higher values increase hallucination risk.
"""

from openai import OpenAI

from backend.utils.config import OPENAI_API_KEY, OPENAI_MODEL

# ---------------------------------------------------------------------------
# Singleton client — initialised once, reused across all requests
# ---------------------------------------------------------------------------

_client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def chat(messages: list[dict]) -> str:
    """
    Send a message list to GPT-4o and return the assistant's reply as a string.

    Parameters
    ----------
    messages : list of {"role": "system"/"user"/"assistant", "content": "..."}
               Built by prompts.build_messages().

    Returns
    -------
    str — the model's response text, stripped of leading/trailing whitespace.
    """
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()
