"""
app/infrastructure/external/ai_provider.py

Provider-agnostic async wrapper around an OpenAI-compatible
chat-completion API. AI_PROVIDER in settings picks which base URL +
key to use (gapgpt / nvidia / deepseek / openai); everything else in
the app just calls ask_ai() and never talks to httpx directly.
"""

import asyncio
import time

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

MAX_TOKENS = 2048
REQUEST_TIMEOUT = httpx.Timeout(connect=15, read=120, write=15, pool=15)
MAX_ATTEMPTS = 2


class AIProviderError(Exception):
    pass


def _resolve_provider() -> tuple[str, str]:
    provider = (settings.AI_PROVIDER or "gapgpt").lower()

    if provider == "gapgpt":
        return f"{settings.GAPGPT_BASE_URL.rstrip('/')}/chat/completions", settings.GAPGPT_API_KEY
    if provider == "nvidia":
        return settings.AI_API_URL, settings.NVIDIA_API_KEY
    if provider == "deepseek":
        return "https://api.deepseek.com/v1/chat/completions", settings.DEEPSEEK_API_KEY
    if provider == "openai":
        return "https://api.openai.com/v1/chat/completions", settings.OPENAI_API_KEY

    return settings.AI_API_URL, settings.AI_API_KEY


async def ask_ai(prompt: str) -> str:
    """
    Sends a single-turn prompt to the configured AI provider and
    returns the raw text response. Retries once on timeout/5xx.
    """
    url, api_key = _resolve_provider()

    if not api_key:
        raise AIProviderError("سرویس هوش مصنوعی هنوز پیکربندی نشده است.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                response = await client.post(url, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                elapsed = time.perf_counter() - started
                logger.warning(f"[AIProvider] network error attempt {attempt}: {exc!r} [{elapsed:.2f}s]")
                if attempt == MAX_ATTEMPTS:
                    raise AIProviderError("ارتباط با سرویس هوش مصنوعی برقرار نشد. لطفاً دوباره تلاش کنید.")
                await asyncio.sleep(3)
                continue

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]

            if response.status_code in (429, 503):
                logger.warning(f"[AIProvider] provider busy ({response.status_code})")
                if attempt == MAX_ATTEMPTS:
                    raise AIProviderError("سرویس هوش مصنوعی موقتاً شلوغ است.")
                await asyncio.sleep(5)
                continue

            logger.error(f"[AIProvider] error {response.status_code}: {response.text[:300]}")
            raise AIProviderError(f"خطای سرویس هوش مصنوعی ({response.status_code})")

    raise AIProviderError("سرویس هوش مصنوعی در دسترس نیست.")