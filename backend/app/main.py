"""
pi_sb — Second Brain API
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config.settings import get_settings, get_app_internal_dir
from app.api import input as input_routes
from app.api import search as search_routes
from app.api import settings as settings_routes
from app.api import debug as debug_routes
from app.api import data as data_routes
from app.api import llm_router as llm_routes
from app.wiki.indexer import WikiIndexer
from app.core.storage import OkfStorage
from app.core.debug_logger import debug_logger
from app.audio.transcriber import AudioTranscriber
from app.llm.http_client import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan събития: startup и shutdown."""
    s = get_settings()
    logger.info(f"🚀 {s.app_name} v{s.app_version} starting...")
    logger.info(f"📂 OKF storage: {s.okf_data_path}")
    logger.info(f"🤖 Ollama: {s.ollama_host} | Ingestion: {s.ingestion_model} | RAG: {s.rag_model}")

    # Създаваме data директориите
    s.okf_data_path.mkdir(parents=True, exist_ok=True)
    s.audio_upload_path.mkdir(parents=True, exist_ok=True)

    # Clear debug logs from previous sessions — always fresh info
    debug_logger.clear_all_logs()
    logger.info("🔍 Debug logs cleared (fresh start)")

    # Initialize audio transcriber (on-demand, no persistent server)
    app.state.transcriber = AudioTranscriber()
    logger.info("🎤 Audio transcriber initialized (on-demand mode)")

    # Initialize wiki indexes on startup
    storage = OkfStorage()
    indexer = WikiIndexer(storage=storage)
    indexer.regenerate_all()
    indexer.log_event(event_type="update", title="System startup", details="Wiki indexes regenerated.")
    logger.info("📚 Wiki indexes initialized")

    yield

    # Shutdown: close shared HTTP client (connection pooling)
    await close_http_client()
    logger.info("🌐 HTTP client closed")

    # No persistent whisper server to stop — model is loaded on-demand
    logger.info("🎤 Audio transcriber shut down")

    logger.info("👋 Server stopped.")


app = FastAPI(
    title=get_settings().app_name,
    version=get_settings().app_version,
    description="Local Second Brain system for knowledge storage and retrieval",
    lifespan=lifespan
)

# CORS - configurable via CORS_ORIGINS in .env
# Default: * (allows all origins - backward compatible)
# For production: CORS_ORIGINS=http://localhost:5173,http://localhost:8000
_s = get_settings()
_cors_origins = _s.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != [chr(42)],
    allow_methods=[chr(42)],
    allow_headers=[chr(42)],
)
logger.info('CORS configured: origins={_cors_origins}, credentials={_cors_origins != [*]}')

# Debug middleware — логва всяка заявка/отговор (само ако е включен)
@app.middleware("http")
async def debug_middleware(request, call_next):
    import time

    # Ако debug системата е изключена — skip-ваме логването
    if not debug_logger.enabled:
        return await call_next(request)

    start = time.time()

    # Логваме заявката
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = await request.body()

    debug_logger.log_request(
        method=request.method,
        path=str(request.url.path),
        params=dict(request.query_params),
        body=body,
    )

    # Изпълняваме заявката
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    # Логваме отговора
    debug_logger.log_response(
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response


# Регистриране на endpoints
app.include_router(input_routes.router)
app.include_router(search_routes.router)
app.include_router(settings_routes.router)
app.include_router(debug_routes.router)
app.include_router(data_routes.router)
app.include_router(llm_routes.router)


@app.get("/api/health")
async def health():
    """Проверка на състоянието на системата."""
    from app.llm.ollama_client import OllamaClient
    from app.config.settings import get_settings
    from app.core.storage import OkfStorage
    ollama = OllamaClient(model=get_settings().ingestion_model)
    llm_online = await ollama.health_check()

    # Броим само реални OKF концепции (използваме storage който правилно филтрира)
    s = get_settings()
    storage = OkfStorage(data_dir=s.okf_data_path)
    all_concepts = storage.get_all_concepts()
    total = len(all_concepts)

    return {
        "status": "healthy" if llm_online else "degraded",
        "llm_connected": llm_online,
        "data_dir": str(s.okf_data_path),
        "total_concepts": total
    }


# Serve React frontend in production — MUST BE LAST to avoid blocking API routes
frontend_dist = get_app_internal_dir() / "frontend" / "dist"
if frontend_dist.exists() and frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    logger.info(f"📦 React frontend served from {frontend_dist}")
else:
    logger.info("📦 React frontend not built — API-only mode")


if __name__ == "__main__":
    import uvicorn
    import sys
    # In frozen (EXE) mode, disable reload
    is_frozen = getattr(sys, 'frozen', False)
    # На Android/Termux reload винаги е False — не искаме да watch-ваме файлове на телефона
    is_android = sys.platform == "linux" and ("com.termux" in str(sys.executable) or "termux" in str(Path.home()))
    enable_reload = not is_frozen and not is_android and get_settings().debug
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=enable_reload)
