"""
Shared HTTP client за Ollama API комуникация.

Използва singleton AsyncClient с connection pooling за по-добра ефективност.
Вместо да създаваме нов client за всяка заявка, използваме един споделен.
"""

import httpx
from loguru import logger
from typing import Optional


# ──────────────────────────────────────────────
# Module-level singleton HTTP client
# ──────────────────────────────────────────────
_shared_client: Optional[httpx.AsyncClient] = None

# Default конфигурация
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_LIMITS = httpx.Limits(
    max_connections=10,           # Максимален брой едновременни връзки
    max_keepalive_connections=5,  # Връзки които пазим отворени
    keepalive_expiry=30.0,        # Колко време пазим връзките отворени (секунди)
)


def get_http_client(timeout: float = _DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    """
    Връща споделения HTTP клиент.
    Създава го при първо извикване или ако е затворен.
    
    Args:
        timeout: Timeout за заявки в секунди (default: 120s)
    
    Returns:
        httpx.AsyncClient: Споделеният клиент
    """
    global _shared_client
    
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=timeout,
            limits=_DEFAULT_LIMITS,
        )
        logger.debug(f"HTTP client created (timeout={timeout}s, "
                     f"max_connections={_DEFAULT_LIMITS.max_connections})")
    
    return _shared_client


async def close_http_client():
    """
    Затваря споделения HTTP клиент.
    Трябва да се извика при shutdown на приложението.
    """
    global _shared_client
    
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        logger.debug("HTTP client closed")
    
    _shared_client = None


def get_client_status() -> dict:
    """Връща информация за състоянието на HTTP клиента."""
    global _shared_client
    
    if _shared_client is None:
        return {"created": False, "closed": True}
    
    return {
        "created": True,
        "closed": _shared_client.is_closed,
        "timeout": _shared_client.timeout.connect if hasattr(_shared_client.timeout, 'connect') else str(_shared_client.timeout),
        "limits": {
            "max_connections": _DEFAULT_LIMITS.max_connections,
            "max_keepalive_connections": _DEFAULT_LIMITS.max_keepalive_connections,
        }
    }