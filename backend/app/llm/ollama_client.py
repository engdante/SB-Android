"""
HTTP клиент за комуникация с отдалечен или локален Ollama сървър.
Използва shared HTTP client за connection pooling.
"""

from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from app.config.settings import get_settings
from app.core.debug_logger import debug_logger
from app.llm.http_client import get_http_client


class OllamaClient:
    """Клиент за изпращане на заявки към Ollama API."""

    def __init__(self, model: str, host: Optional[str] = None,
                 api_key: Optional[str] = None):
        # Използваме актуалните настройки от .env (live)
        s = get_settings()
        self.host = (host or s.ollama_host).rstrip("/")
        self.model = model
        # Fallback към OLLAMA_API_KEY от .env, ако не е подаден api_key
        self.api_key = api_key or s.ollama_api_key or ""
        self.base_url = f"{self.host}/api"

    def _get_headers(self) -> dict:
        """Връща HTTP headers, включително Authorization ако има API key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       temperature: float = 0.3, max_tokens: int = 2048,
                       max_retries: int = 3) -> str:
        """
        Изпраща prompt към Ollama и връща генерирания текст.
        Автоматично retry-ва при празен отговор, timeout или HTTP 5xx грешки.

        Args:
            prompt: Потребителският prompt
            system_prompt: Системен prompt (ако има)
            temperature: Температура за генерация (0.0 - 1.0)
            max_tokens: Максимален брой токени
            max_retries: Максимален брой повторения при грешка

        Returns:
            Генерираният текст от модела
        """
        import asyncio
        import time

        last_error = None

        for attempt in range(1, max_retries + 1):
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            logger.debug(f"Ollama заявка (опит {attempt}/{max_retries}) -> {self.host}, модел: {self.model}")

            start_time = time.time()
            error = None

            try:
                client = get_http_client(timeout=120.0)
                response = await client.post(f"{self.base_url}/generate", json=payload, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()
                generated_text = result.get("response", "").strip()

                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"Ollama отговор: {len(generated_text)} символа за {duration_ms:.0f}ms (опит {attempt})")

                # Ако отговорът е празен, retry-ваме
                if not generated_text:
                    error = "empty_response"
                    logger.warning(f"Ollama върна празен отговор (опит {attempt}/{max_retries})")
                    debug_logger.log_llm(
                        action="generate",
                        model=self.model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        duration_ms=duration_ms,
                        error=error,
                    )
                    if attempt < max_retries:
                        wait = 1.0 * attempt
                        logger.info(f"Изчаквам {wait}s преди retry...")
                        await asyncio.sleep(wait)
                        continue
                    return generated_text

                debug_logger.log_llm(
                    action="generate",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response=generated_text,
                    duration_ms=duration_ms,
                )
                return generated_text

            except httpx.TimeoutException:
                duration_ms = (time.time() - start_time) * 1000
                error = "timeout"
                last_error = error
                logger.warning(f"Ollama timeout (опит {attempt}/{max_retries}): {duration_ms:.0f}ms")
                debug_logger.log_llm(
                    action="generate",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    duration_ms=duration_ms,
                    error=error,
                )
                if attempt < max_retries:
                    wait = 2.0 * attempt
                    logger.info(f"Изчаквам {wait}s преди retry...")
                    await asyncio.sleep(wait)
                    continue
                raise

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                duration_ms = (time.time() - start_time) * 1000
                if isinstance(e, httpx.HTTPStatusError):
                    status = e.response.status_code
                    error = f"HTTP {status}"
                    # Retry-ваме само при 5xx грешки
                    if status < 500:
                        raise
                else:
                    error = str(e)
                last_error = error

                logger.warning(f"Ollama грешка (опит {attempt}/{max_retries}): {error}")
                debug_logger.log_llm(
                    action="generate",
                    model=self.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    duration_ms=duration_ms,
                    error=error,
                )
                if attempt < max_retries:
                    wait = 2.0 * attempt
                    logger.info(f"Изчаквам {wait}s преди retry...")
                    await asyncio.sleep(wait)
                    continue
                raise

        # Ако сме стигнали дотук след всички retry-та, връщаме празен низ
        # с логване, вместо да crash-ваме
        logger.error(f"Ollama не върна валиден отговор след {max_retries} опита. Последна грешка: {last_error}")
        return ""

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Генерира embedding вектор за даден текст.

        Args:
            text: Текстът за векторизиране

        Returns:
            Списък с float стойности (embedding вектор)
        """
        payload = {
            "model": self.model,
            "prompt": text
        }

        try:
            client = get_http_client(timeout=30.0)
            response = await client.post(f"{self.base_url}/embeddings", json=payload, headers=self._get_headers())
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])

        except Exception as e:
            logger.error(f"Грешка при генериране на embedding: {e}")
            raise

    async def list_models(self) -> list[dict]:
        """
        Връща списък на всички налични модели от /api/tags.

        Returns:
            list[dict]: Списък с информация за всеки модел
        """
        try:
            client = get_http_client(timeout=10.0)
            response = await client.get(f"{self.host}/api/tags", headers=self._get_headers())
            response.raise_for_status()
            result = response.json()
            models = result.get("models", [])
            # Връщаме само полезната информация
            return [
                {
                    "name": m.get("name", "unknown"),
                    "size": m.get("size", 0),
                    "family": m.get("details", {}).get("family", ""),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
                    "context_length": m.get("details", {}).get("context_length", 0),
                    "capabilities": m.get("capabilities", []),
                }
                for m in models
            ]
        except Exception as e:
            logger.error(f"Грешка при взимане на списък с модели от {self.host}: {e}")
            return []

    async def health_check(self) -> bool:
        """Проверява дали Ollama сървърът е достъпен."""
        try:
            client = get_http_client(timeout=5.0)
            response = await client.get(f"{self.host}/api/tags", headers=self._get_headers())
            return response.status_code == 200
        except Exception:
            return False
