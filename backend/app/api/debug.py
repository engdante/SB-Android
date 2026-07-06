"""
API endpoints за debug системата.
Позволява преглед на логове, включване/изключване от runtime и frontend.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from loguru import logger

from app.core.debug_logger import debug_logger
from app.config.settings import get_settings, get_runtime_setting, set_runtime_setting

router = APIRouter(prefix="/api/debug", tags=["debug"])


class FrontendLogInput(BaseModel):
    level: str = "info"  # info | warn | error
    source: str
    message: str
    data: Optional[str] = None


@router.get("/status")
async def get_debug_status():
    """Връща дали debug системата е включена."""
    s = get_settings()
    return {
        "status": "ok",
        "debug_enabled": debug_logger.enabled,
        "env_setting": s.debug_enabled,
        "runtime_override": get_runtime_setting("debug_enabled") is not None,
        "log_dir": str(debug_logger.debug_dir),
    }


@router.post("/toggle")
async def toggle_debug(enabled: bool):
    """Включва/изключва debug системата в runtime."""
    debug_logger.set_enabled(enabled)
    set_runtime_setting("debug_enabled", enabled)
    debug_logger.log_generic("debug", f"Debug system {'enabled' if enabled else 'disabled'}")
    return {
        "status": "ok",
        "debug_enabled": debug_logger.enabled,
    }


@router.get("/logs")
async def list_logs():
    """Връща списък с всички лог файлове."""
    files = debug_logger.list_log_files()
    return {
        "status": "ok",
        "total": len(files),
        "files": files,
    }


@router.get("/logs/{filepath:path}")
async def read_log(filepath: str, lines: int = Query(100, description="Максимален брой редове")):
    """Връща съдържанието на конкретен лог файл."""
    entries = debug_logger.read_log_file(filepath, max_lines=lines)
    return {
        "status": "ok",
        "file": filepath,
        "total_entries": len(entries),
        "entries": entries,
    }


@router.post("/log")
async def log_frontend(data: FrontendLogInput):
    """Приема log съобщение от frontend-а."""
    debug_logger.log_frontend(
        level=data.level,
        source=data.source,
        message=data.message,
        data=data.data,
    )
    return {"status": "ok"}