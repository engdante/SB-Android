"""
API endpoints for managing settings (Ollama host, model).
Allows runtime changes without server restart.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import httpx
from loguru import logger

from app.config.settings import (
    get_settings,
    set_runtime_setting,
    clear_runtime_setting,
    save_settings_to_env,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    ingestion_model: Optional[str] = None
    rag_model: Optional[str] = None
    audio_model: Optional[str] = None
    backend_url: Optional[str] = None
    save_to_env: bool = False


class SettingsResponse(BaseModel):
    ollama_host: str
    ollama_model: str
    effective_host: str
    effective_model: str
    ingestion_model: str
    rag_model: str
    cloud_models: list[str] = []
    available_models: list[str] = []
    audio_model: str = ""
    backend_url: str = "http://localhost:8000"


@router.get("")
async def read_settings():
    """Returns current settings and list of available models from Ollama."""
    s = get_settings()
    available_models = []

    # Try to fetch model list from Ollama
    host = s.ollama_host.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                available_models = [
                    m["name"] for m in data.get("models", [])
                ]
    except Exception as e:
        logger.warning(f"Failed to fetch models from Ollama: {e}")

    # effective_host reflects the real host for ingestion model
    effective_host = s.get_model_host(s.ingestion_model)

    return SettingsResponse(
        ollama_host=s.ollama_host,
        ollama_model=s.ingestion_model,
        effective_host=effective_host,
        effective_model=s.ingestion_model,
        ingestion_model=s.ingestion_model,
        rag_model=s.rag_model,
        cloud_models=s.cloud_models_list,
        available_models=available_models,
        audio_model=s.audio_model,
        backend_url=s.backend_url,
    )


@router.post("")
async def update_settings(data: SettingsUpdate):
    """Updates settings at runtime."""
    if data.ollama_host:
        # Validate the host
        host = data.ollama_host.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{host}/api/tags")
                if response.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Ollama server at {host} is not responding")
        except httpx.RequestError:
            raise HTTPException(status_code=400, detail=f"Failed to connect to Ollama at {host}")

    settings = get_settings()
    to_clear = []

    if data.ollama_host is not None:
        settings.ollama_host = data.ollama_host.rstrip("/")
        to_clear.append("ollama_host")
    if data.ollama_model is not None:
        # Legacy field — maps to ingestion_model
        settings.ingestion_model = data.ollama_model
        to_clear.append("ingestion_model")
    if data.ingestion_model is not None:
        settings.ingestion_model = data.ingestion_model
        to_clear.append("ingestion_model")
    if data.rag_model is not None:
        settings.rag_model = data.rag_model
        to_clear.append("rag_model")
    if data.audio_model is not None:
        settings.audio_model = data.audio_model
        to_clear.append("audio_model")
    if data.backend_url is not None:
        settings.backend_url = data.backend_url.rstrip("/")
        to_clear.append("backend_url")

    if data.save_to_env:
        save_settings_to_env(settings)
        for key in to_clear:
            clear_runtime_setting(key)
        logger.info(f"Settings saved to .env")
    else:
        for key in to_clear:
            value = getattr(settings, key)
            set_runtime_setting(key, value)

    s = get_settings()
    logger.info(f"Settings updated: host={s.ollama_host}, model={s.ingestion_model}")

    return {
        "status": "ok",
        "effective_host": s.ollama_host,
        "effective_model": s.ingestion_model,
        "effective_ingestion_model": s.ingestion_model,
        "effective_rag_model": s.rag_model,
        "effective_audio_model": s.audio_model,
        "effective_backend_url": s.backend_url,
    }


@router.get("/models")
async def list_models(host: Optional[str] = None):
    """Returns a list of available models from an Ollama server."""
    s = get_settings()
    target_host = (host or s.ollama_host).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{target_host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "status": "ok",
                    "host": target_host,
                    "models": models
                }
            else:
                return {
                    "status": "error",
                    "message": f"Ollama returned status {response.status_code}"
                }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
