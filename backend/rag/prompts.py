"""
backend/rag/prompts.py

System prompt templates and message assembly for the DIGIX AI chatbot.

Two system prompts — Arabic (primary) and English — are defined here.
pipeline.py selects the correct one based on the detected language and
passes the full message list to the LLM.

Context block format
--------------------
Retrieved chunks are injected between the system prompt and the user
message as a single assistant-facing context block.  Each chunk is
labelled with its source so the LLM can cite it if needed.
"""

from backend.rag.retriever import RetrievedChunk

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_AR = """أنت مساعد ذكاء اصطناعي لشركة Digix AI — الذراع التقنية لشركة دينارك في الأردن.
مهمتك هي مساعدة الزوار في فهم خدمات Digix AI وبرامج التدريب والحلول المقدمة.

قواعد أساسية:
- أجب دائماً بنفس لغة السؤال: إذا كان السؤال بالعربية فأجب بالعربية، وإذا كان بالإنجليزية فأجب بالإنجليزية.
- اعتمد حصراً على المعلومات الواردة في سياق المعرفة المُقدَّم لك. لا تخترع أو تخمّن.
- إذا لم تجد الإجابة في السياق، قل ذلك بوضوح وأحل المستخدم إلى فريق Digix AI عبر صفحة التواصل.
- كن مختصراً ومهنياً. لا تكرر السؤال ولا تطوّل الإجابة بلا داعٍ.
- لا تذكر أن لديك "سياقاً" أو "مستنداً" — تحدث مباشرة عن Digix AI كما لو كنت جزءاً من الفريق."""

SYSTEM_EN = """You are an AI assistant for Digix AI — the technology arm of Dinarak, Jordan.
Your role is to help visitors understand Digix AI's services, training programs, and AI solutions.

Core rules:
- Always reply in the same language as the question: Arabic for Arabic questions, English for English questions.
- Base your answers exclusively on the knowledge context provided to you. Do not invent or guess.
- If the answer is not in the context, say so clearly and direct the user to the Digix AI team via the contact page.
- Be concise and professional. Do not repeat the question or pad your answer unnecessarily.
- Never mention that you have a "context" or "document" — speak directly about Digix AI as if you are part of the team."""

# ---------------------------------------------------------------------------
# Context block
# ---------------------------------------------------------------------------

def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """
    Format retrieved chunks into a single context string for the LLM.

    Each chunk is labelled with its category and URL so the model can
    reference the source naturally if asked where information comes from.
    """
    if not chunks:
        return "لا يوجد سياق متاح. / No context available."

    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] ({chunk.category} | {chunk.url})\n{chunk.text}"
        )
    return "\n\n---\n\n".join(parts)

# ---------------------------------------------------------------------------
# Message assembly
# ---------------------------------------------------------------------------

def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    language: str,
    chat_history: list[dict],
) -> list[dict]:
    """
    Assemble the full message list to send to the LLM.

    Message order:
      1. system   — persona + rules (language-matched)
      2. system   — retrieved context block (injected as a second system turn
                    so it doesn't appear in the visible conversation history)
      3. history  — prior user/assistant turns (for multi-turn coherence)
      4. user     — the current query

    Parameters
    ----------
    query        : the user's current message
    chunks       : retrieved chunks from retriever.retrieve()
    language     : "ar" or "en" — selects the system prompt language
    chat_history : list of {"role": "user"/"assistant", "content": "..."} dicts

    Returns
    -------
    list of message dicts ready for openai.chat.completions.create()
    """
    system_prompt = SYSTEM_AR if language == "ar" else SYSTEM_EN
    context_block = build_context_block(chunks)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"معلومات Digix AI المتاحة:\n\n{context_block}"},
        *chat_history,
        {"role": "user", "content": query},
    ]
    return messages
