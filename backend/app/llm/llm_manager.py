"""
LLM Manager — manages two separate Ollama clients:
- ingestion_client: for writing new notes (smarter model)
- rag_client: for RAG responses (faster model)
"""

from typing import Optional

from loguru import logger

from app.config.settings import get_settings
from app.llm.ollama_client import OllamaClient


class LLMManager:
    """
    Manages two Ollama clients with different models.
    Automatically determines the host for each model (local or cloud).
    """

    def __init__(self):
        self._ingestion_host = None
        self._ingestion_model = None
        self._rag_host = None
        self._rag_model = None
        self.ingestion_client = None
        self.rag_client = None
        self._ensure_clients()

    def _ensure_clients(self):
        """Checks if settings have changed and recreates clients if necessary."""
        s = get_settings()

        # Ingestion client
        ingestion_host = s.get_model_host(s.ingestion_model)
        ingestion_api_key = s.get_model_api_key(s.ingestion_model)
        if (self.ingestion_client is None or
            self._ingestion_host != ingestion_host or
            self._ingestion_model != s.ingestion_model):
            self.ingestion_client = OllamaClient(
                host=ingestion_host,
                model=s.ingestion_model,
                api_key=ingestion_api_key
            )
            self._ingestion_host = ingestion_host
            self._ingestion_model = s.ingestion_model
            logger.info(
                f"LLMManager: Ingestion client -> {ingestion_host}, "
                f"model: {s.ingestion_model}"
            )

        # RAG client
        rag_host = s.get_model_host(s.rag_model)
        rag_api_key = s.get_model_api_key(s.rag_model)
        if (self.rag_client is None or
            self._rag_host != rag_host or
            self._rag_model != s.rag_model):
            self.rag_client = OllamaClient(
                host=rag_host,
                model=s.rag_model,
                api_key=rag_api_key
            )
            self._rag_host = rag_host
            self._rag_model = s.rag_model
            logger.info(
                f"LLMManager: RAG client -> {rag_host}, "
                f"model: {s.rag_model}"
            )

    async def get_available_models(self) -> dict:
        """
        Returns all available models — remote (from /api/tags) + cloud (from .env).
        Gracefully handles when /api/tags is unreachable (e.g. cloud-only setups).

        Returns:
            dict: {"local": [...], "cloud": [...]}
        """
        from loguru import logger
        s = get_settings()

        # Remote models from OLLAMA_HOST /api/tags
        remote_models = []
        try:
            remote_client = OllamaClient(model=s.ingestion_model, host=s.ollama_host)
            remote_models = await remote_client.list_models()
        except Exception as e:
            logger.warning(f"Ollama /api/tags unreachable at {s.ollama_host}: {e}")

        # Cloud models from configuration (already just names)
        cloud_models = [
            {
                "name": name,
                "host": s.ollama_host,
                "has_api_key": bool(s.ollama_api_key),
            }
            for name in s.cloud_models_list
        ]

        return {
            "local": remote_models,
            "cloud": cloud_models,
        }

    def update_runtime_ingestion_model(self, model_name: str) -> None:
        """
        Switches the ingestion model at runtime (without modifying .env).
        Creates a new client with the new model.
        """
        from app.config.settings import set_runtime_setting
        set_runtime_setting("ingestion_model", model_name)
        self._ensure_clients()
        s = get_settings()
        logger.info(f"LLMManager: Ingestion model switched to {model_name} (host: {s.get_model_host(model_name)})")

    def update_runtime_rag_model(self, model_name: str) -> None:
        """
        Switches the RAG model at runtime (without modifying .env).
        Creates a new client with the new model.
        """
        from app.config.settings import set_runtime_setting
        set_runtime_setting("rag_model", model_name)
        self._ensure_clients()
        s = get_settings()
        logger.info(f"LLMManager: RAG model switched to {model_name} (host: {s.get_model_host(model_name)})")

    async def health_check(self) -> dict:
        """
        Checks if both clients are available.

        Returns:
            dict: {"ingestion": bool, "rag": bool}
        """
        self._ensure_clients()
        return {
            "ingestion": await self.ingestion_client.health_check(),
            "rag": await self.rag_client.health_check(),
        }


# Singleton instance
llm_manager = LLMManager()