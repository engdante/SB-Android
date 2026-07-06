"""
API endpoints for managing LLM models.
Allows viewing available models (local + cloud) and runtime switching.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.llm.llm_manager import llm_manager
from app.config.settings import get_settings
from loguru import logger

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ModelSwitchInput(BaseModel):
    """Input for runtime model switching."""
    model: str


class AudioSwitchInput(BaseModel):
    """Input for runtime audio engine switching."""
    engine: str = "local"       # "local" | "remote" | "ollama"
    model: str = "large-v3"     # model name
    host: str = ""              # URL for remote/ollama


@router.get("/models")
async def get_available_models():
    """
    Returns all available models — local (from /api/tags) + cloud (from .env).
    """
    s = get_settings()
    try:
        models = await llm_manager.get_available_models()
        return {
            "status": "ok",
            "models": models,
            "selected": {
                "ingestion": s.ingestion_model,
                "rag": s.rag_model,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/health")
async def llm_health():
    """
    Checks if both clients (ingestion + RAG) are available.
    """
    s = get_settings()
    try:
        health = await llm_manager.health_check()
        return {
            "status": "ok",
            "health": health,
            "config": {
                "ingestion_model": s.ingestion_model,
                "ingestion_host": s.get_model_host(s.ingestion_model),
                "rag_model": s.rag_model,
                "rag_host": s.get_model_host(s.rag_model),
                "is_ingestion_cloud": s.is_cloud_model(s.ingestion_model),
                "is_rag_cloud": s.is_cloud_model(s.rag_model),
            }
        }
    except Exception as e:
        logger.error(f"Error during health check: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/switch/ingestion")
async def switch_ingestion_model(data: ModelSwitchInput):
    """
    Switches the ingestion model at runtime (without modifying .env).
    """
    try:
        model_name = data.model
        logger.info(f"Switching ingestion model to: {model_name}")
        llm_manager.update_runtime_ingestion_model(model_name)
        s = get_settings()
        return {
            "status": "ok",
            "message": f"Ingestion model switched to {model_name}",
            "current_model": s.ingestion_model,
            "host": s.get_model_host(model_name),
            "is_cloud": s.is_cloud_model(model_name),
        }
    except Exception as e:
        logger.error(f"Error switching ingestion model: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/switch/rag")
async def switch_rag_model(data: ModelSwitchInput):
    """
    Switches the RAG model at runtime (without modifying .env).
    """
    try:
        model_name = data.model
        logger.info(f"Switching RAG model to: {model_name}")
        llm_manager.update_runtime_rag_model(model_name)
        s = get_settings()
        return {
            "status": "ok",
            "message": f"RAG model switched to {model_name}",
            "current_model": s.rag_model,
            "host": s.get_model_host(model_name),
            "is_cloud": s.is_cloud_model(model_name),
        }
    except Exception as e:
        logger.error(f"Error switching RAG model: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/switch/audio")
async def switch_audio_engine(data: AudioSwitchInput):
    """
    Switches the audio engine at runtime (without modifying .env).
    """
    try:
        logger.info(f"Switching audio engine: engine={data.engine}, model={data.model}, host={data.host}")

        from app.config.settings import set_runtime_setting
        set_runtime_setting("audio_engine", data.engine)
        if data.model:
            set_runtime_setting("audio_model", data.model)
        if data.host:
            set_runtime_setting("audio_host", data.host)

        s = get_settings()
        return {
            "status": "ok",
            "message": f"Audio engine switched: {data.engine} / {data.model}",
            "current": {
                "engine": s.audio_engine,
                "model": s.audio_model,
                "host": s.audio_host,
            }
        }
    except Exception as e:
        logger.error(f"Error switching audio engine: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/config")
async def get_llm_config():
    """
    Returns the current LLM configuration.
    """
    s = get_settings()
    return {
        "status": "ok",
        "config": {
            "ollama_host": s.ollama_host,
            "ingestion_model": s.ingestion_model,
            "rag_model": s.rag_model,
            "cloud_models": s.cloud_models_list,
            "ingestion_host": s.get_model_host(s.ingestion_model),
            "rag_host": s.get_model_host(s.rag_model),
            "is_ingestion_cloud": s.is_cloud_model(s.ingestion_model),
            "is_rag_cloud": s.is_cloud_model(s.rag_model),
        }
    }
