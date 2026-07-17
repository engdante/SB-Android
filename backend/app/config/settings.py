import sys
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional
import json

from loguru import logger


# ──────────────────────────────────────────────
# Path resolution — works in both dev and frozen (PyInstaller) mode
# ──────────────────────────────────────────────

def get_app_base_dir() -> Path:
    """
    Returns the application's base directory.
    - Dev mode: the project root (D:/AI/SB or ~/pi_sb on Android)
    - Frozen mode: the directory containing the .exe
    - Android/Termux: ~/pi_sb/
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    
    # Android/Termux detection
    if sys.platform == "linux" and ("com.termux" in str(sys.executable) or "termux" in str(Path.home())):
        home = Path.home()
        # Check common project locations
        for candidate in [home / "pi_sb", home / "storage" / "pi_sb", home / "projects" / "pi_sb"]:
            if (candidate / "backend" / "app").exists():
                return candidate
        # Fallback: use the current file's path (works if running from project dir)
    
    return Path(__file__).resolve().parent.parent.parent.parent


def get_app_internal_dir() -> Path:
    """
    Returns the directory where bundled data files live.
    - Dev mode: the project root
    - Frozen mode: sys._MEIPASS (PyInstaller temp extraction dir)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent.parent


# Project base directory
BASE_DIR = get_app_base_dir()
ENV_FILE = BASE_DIR / ".env"
RUNTIME_FILE = BASE_DIR / "data" / "runtime_settings.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8")

    # Ollama (local or cloud)
    ollama_host: str = "http://192.168.1.100:11434"
    ollama_api_key: str = ""

    # Cloud models (JSON array)
    # Format: [{"name":"gemma4:cloud","host":"http://...","api_key":""}]
    cloud_models: str = "[]"

    # Model selection for ingest and RAG
    ingestion_model: str = "gemma4:cloud"
    rag_model: str = "qwen3.5:9b"

    # OKF storage
    okf_data_dir: str = "./data"

    # Application
    app_name: str = "pi_sb"
    app_version: str = "1.0.0"
    debug: bool = True

    # Audio transcription (whisper.cpp)
    audio_model: str = "ggml-medium.en-q5_0.bin"  # GGUF model for whisper.cpp
    audio_upload_dir: str = "./data/audio"

    # Backend URL (for frontend to know where to find the backend)
    backend_url: str = "http://localhost:8000"

    # CORS origins — comma-separated list or "*" for all (default: "*" for backward compatibility)
    cors_origins: str = "*"

    # Debug system
    debug_enabled: bool = False

    @property
    def okf_data_path(self) -> Path:
        return (BASE_DIR / self.okf_data_dir).resolve()

    @property
    def audio_upload_path(self) -> Path:
        path = (BASE_DIR / self.audio_upload_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_model_host(self, model_name: str) -> str:
        """
        Returns the host for a given model.
        Always returns OLLAMA_HOST — the single host for all LLM requests.
        """
        return self.ollama_host

    def get_model_api_key(self, model_name: str) -> str:
        """
        Returns the API key for Ollama cloud (OLLAMA_API_KEY).
        Passed as Bearer token in Authorization header.
        """
        return self.ollama_api_key

    def is_cloud_model(self, model_name: str) -> bool:
        """Checks if the model is a cloud model (defined in CLOUD_MODELS)."""
        return model_name in self.cloud_models_list

    @property
    def cloud_models_list(self) -> list[str]:
        """Parses CLOUD_MODELS JSON string into a list of model names."""
        try:
            raw = json.loads(self.cloud_models)
            # Support both formats: list of names or list of objects (backward compatibility)
            if raw and isinstance(raw[0], dict):
                return [cm["name"] for cm in raw if "name" in cm]
            return [str(m) for m in raw]
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def cors_origins_list(self) -> list[str]:
        """Parses CORS_ORIGINS string into a list of origins."""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# ──────────────────────────────────────────────
# Runtime overrides (live, not saved to .env)
# ──────────────────────────────────────────────

# Mapping: JSON key -> Settings attribute name
# Only these settings can be changed at runtime.
#
# Excluded fields (require server restart):
#   - cloud_models       — complex JSON, set only in .env
#   - audio_upload_dir   — directory created on startup (lifespan)
#   - okf_data_dir       — used during storage initialization
#   - debug              — controls uvicorn reload, requires restart
#   - app_name/version   — set once in .env
#   - cors_origins       — set at startup, requires restart
_RUNTIME_KEYS = {
    "ollama_host": "ollama_host",
    "ollama_api_key": "ollama_api_key",
    "ingestion_model": "ingestion_model",
    "rag_model": "rag_model",
    "audio_model": "audio_model",
    "debug_enabled": "debug_enabled",
    "backend_url": "backend_url",
}


def _load_runtime() -> dict:
    """Reads runtime overrides from the JSON file."""
    if not RUNTIME_FILE.exists():
        return {}
    try:
        with open(RUNTIME_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_runtime(runtime: dict) -> None:
    """Saves runtime overrides to the JSON file."""
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNTIME_FILE, "w", encoding="utf-8") as f:
        json.dump(runtime, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# Singleton Settings с mtime-based cache invalidation
# ──────────────────────────────────────────────
_settings_cache: Optional[Settings] = None
_env_mtime: float = 0.0
_runtime_mtime: float = 0.0


def _get_file_mtime(path: Path) -> float:
    """Връща mtime на файл или 0 ако не съществува."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def invalidate_settings_cache() -> None:
    """Изчиства кеша с Settings. Извиква се при ръчна промяна на настройките."""
    global _settings_cache, _env_mtime, _runtime_mtime
    _settings_cache = None
    _env_mtime = 0.0
    _runtime_mtime = 0.0
    logger.debug("Settings cache invalidated")


def get_settings() -> Settings:
    """
    Връща кеширан Settings обект.
    Автоматично презарежда ако .env или runtime_settings.json са променени.
    
    Използва mtime check за ефективност - не чете файловете при всяко извикване,
    а само проверява дали са модифицирани.
    """
    global _settings_cache, _env_mtime, _runtime_mtime
    
    # Проверяваме mtime на файловете
    current_env_mtime = _get_file_mtime(ENV_FILE)
    current_runtime_mtime = _get_file_mtime(RUNTIME_FILE)
    
    # Ако кешът е валиден (файловете не са променени), връщаме го
    if (_settings_cache is not None and 
        current_env_mtime == _env_mtime and 
        current_runtime_mtime == _runtime_mtime):
        return _settings_cache
    
    # Файловете са променени или кешът е празен - презареждаме
    s = Settings()
    runtime = _load_runtime()

    for json_key, attr_name in _RUNTIME_KEYS.items():
        if json_key in runtime:
            setattr(s, attr_name, runtime[json_key])

    # Обновяваме кеша
    _settings_cache = s
    _env_mtime = current_env_mtime
    _runtime_mtime = current_runtime_mtime
    logger.debug(f"Settings reloaded (env_mtime={current_env_mtime}, runtime_mtime={current_runtime_mtime})")
    
    return s


def set_runtime_setting(key: str, value) -> None:
    """Sets a runtime override for a given setting."""
    if key not in _RUNTIME_KEYS:
        raise ValueError(f"Invalid runtime setting: {key}")
    runtime = _load_runtime()
    if value is None:
        runtime.pop(key, None)
    else:
        runtime[key] = value
    _save_runtime(runtime)
    # Инвалидираме кеша за да се презареди при следващото get_settings()
    invalidate_settings_cache()
    logger.info(f"Runtime setting '{key}' = {value}")


def clear_runtime_setting(key: str) -> None:
    """Clears a runtime override for a given setting."""
    runtime = _load_runtime()
    if key in runtime:
        del runtime[key]
        _save_runtime(runtime)
    # Инвалидираме кеша за да се презареди при следващото get_settings()
    invalidate_settings_cache()
    logger.info(f"Runtime setting '{key}' cleared")


def get_runtime_setting(key: str, default=None):
    """Returns a runtime override for a given setting."""
    runtime = _load_runtime()
    return runtime.get(key, default)


# ──────────────────────────────────────────────
# .env file I/O
# ──────────────────────────────────────────────

def save_settings_to_env(settings: Settings) -> None:
    """Saves current settings to the .env file."""
    env_path = ENV_FILE

    # Create file if it doesn't exist
    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("", encoding="utf-8")

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Collect current values from Settings
    values = {
        "OLLAMA_HOST": settings.ollama_host,
        "OLLAMA_API_KEY": settings.ollama_api_key,
        "CLOUD_MODELS": settings.cloud_models,
        "INGESTION_MODEL": settings.ingestion_model,
        "RAG_MODEL": settings.rag_model,
        "AUDIO_MODEL": settings.audio_model,
        "DEBUG_ENABLED": "true" if settings.debug_enabled else "false",
        "DEBUG": "true" if settings.debug else "false",
        "OKF_DATA_DIR": settings.okf_data_dir,
        "APP_NAME": settings.app_name,
        "APP_VERSION": settings.app_version,
        "AUDIO_UPLOAD_DIR": settings.audio_upload_dir,
        "BACKEND_URL": settings.backend_url,
        "CORS_ORIGINS": settings.cors_origins,
    }

    updated = {k: False for k in values}
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in stripped:
            key, _ = stripped.split("=", 1)
            key = key.strip()
            if key in values:
                new_lines.append(f"{key}={values[key]}\n")
                updated[key] = True
            else:
                new_lines.append(line)

    # Add missing variables
    for key, value in values.items():
        if not updated[key]:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Инвалидираме кеша за да се презареди при следващото get_settings()
    invalidate_settings_cache()
    logger.info(f"Settings saved to .env: {env_path}")