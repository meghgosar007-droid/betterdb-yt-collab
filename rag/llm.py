from __future__ import annotations

from fastapi import HTTPException
from google.genai import types
from openai import APIStatusError, RateLimitError

from .config import get_gemini, get_openai, get_settings


def _raise_provider_error(exc: Exception) -> None:
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, RateLimitError) or "429" in message or "quota" in lowered or "resource_exhausted" in lowered:
        raise HTTPException(status_code=429, detail=message) from exc
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and 400 <= status < 600:
        raise HTTPException(status_code=status, detail=message) from exc
    raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {message}") from exc


async def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    s = get_settings()
    try:
        if s.llm_provider == "gemini":
            client = get_gemini()
            vectors: list[list[float]] = []
            batch_size = 16
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                resp = await client.aio.models.embed_content(
                    model=s.embedding_model,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                if not resp.embeddings:
                    raise RuntimeError("Gemini returned no embeddings")
                vectors.extend([list(item.values or []) for item in resp.embeddings])
            return vectors

        client = get_openai()
        vectors = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await client.embeddings.create(model=s.embedding_model, input=batch)
            vectors.extend([item.embedding for item in resp.data])
        return vectors
    except HTTPException:
        raise
    except (RateLimitError, APIStatusError, Exception) as exc:
        _raise_provider_error(exc)
        raise


async def generate_answer(query: str, context: str) -> str:
    s = get_settings()
    system = "Answer the question using only the context provided. Be concise."
    user = f"Context:\n{context}\n\nQuestion: {query}"
    try:
        if s.llm_provider == "gemini":
            client = get_gemini()
            resp = await client.aio.models.generate_content(
                model=s.gemini_model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=512,
                ),
            )
            return (resp.text or "").strip()

        client = get_openai()
        completion = await client.chat.completions.create(
            model=s.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=512,
        )
        return (completion.choices[0].message.content or "").strip()
    except HTTPException:
        raise
    except (RateLimitError, APIStatusError, Exception) as exc:
        _raise_provider_error(exc)
        raise
