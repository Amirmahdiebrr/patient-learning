"""
app/infrastructure/external/ai_provider.py

Thin async wrapper around an OpenAI-compatible chat-completion API
(NVIDIA NIM / DeepSeek endpoint, same pattern as the reference project's
app/services/deepseek.py). Kept provider-agnostic behind AIProviderError
so the rest of the app never talks to httpx directly.
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


async def ask_ai(prompt: str) -> str:
    """
    Sends a single-turn prompt to the configured AI provider and
    returns the raw text response. Retries once on timeout/5xx.
    """
    if not settings.AI_API_KEY:
        raise AIProviderError("سرویس هوش مصنوعی هنوز پیکربندی نشده است.")

    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
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
                response = await client.post(settings.AI_API_URL, headers=headers, json=payload)
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