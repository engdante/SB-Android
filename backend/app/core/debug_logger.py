"""
Debug Logger — centralized debug system.
Logs all backend and frontend actions to the debug/ directory.
Can be enabled/disabled via .env (DEBUG_ENABLED) and frontend settings.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any
import json
import traceback
import time

from loguru import logger
from app.config.settings import get_settings, get_app_base_dir


class DebugLogger:
    """
    Centralized debug logger.
    Writes structured logs to the debug/ directory.
    """

    def __init__(self):
        s = get_settings()
        # Debug dir is alongside the EXE or in project root
        self.debug_dir: Path = get_app_base_dir() / "debug"
        self._enabled: bool = s.debug_enabled
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create the directory
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Create .gitignore
        self._ensure_gitignore()

        logger.info(f"🔍 Debug system: {'ENABLED' if self._enabled else 'DISABLED'} -> {self.debug_dir}")

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        """Enables/disables debug logging at runtime."""
        self._enabled = value
        self._write_settings()
        logger.info(f"🔍 Debug system set to {'ENABLED' if value else 'DISABLED'}")

    def log_request(self, method: str, path: str, params: Any = None,
                    body: Any = None, headers: Any = None) -> None:
        """Logs an API request."""
        if not self._enabled:
            return
        self._append("requests.log", {
            "type": "request",
            "timestamp": self._now(),
            "method": method,
            "path": path,
            "params": self._safe_str(params),
            "body": self._safe_str(body, max_len=2000),
            "headers": self._safe_str(headers),
        })

    def log_response(self, method: str, path: str, status_code: int,
                     response: Any = None, duration_ms: float = 0) -> None:
        """Logs an API response."""
        if not self._enabled:
            return
        self._append("requests.log", {
            "type": "response",
            "timestamp": self._now(),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "response": self._safe_str(response, max_len=2000),
        })

    def log_llm(self, action: str, model: str, prompt: str,
                system_prompt: Optional[str] = None,
                response: Optional[str] = None,
                duration_ms: float = 0,
                error: Optional[str] = None) -> None:
        """Logs an LLM request/response."""
        if not self._enabled:
            return
        self._append("llm.log", {
            "type": "llm",
            "timestamp": self._now(),
            "action": action,
            "model": model,
            "prompt": self._safe_str(prompt, max_len=500),
            "system_prompt": self._safe_str(system_prompt, max_len=500),
            "response": self._safe_str(response, max_len=2000),
            "duration_ms": round(duration_ms, 2),
            "error": error,
        })

    def log_ingest(self, text_len: int, title: str, doc_type: str,
                   filepath: str, success: bool, error: Optional[str] = None) -> None:
        """Logs an ingest operation."""
        if not self._enabled:
            return
        self._append("ingest.log", {
            "type": "ingest",
            "timestamp": self._now(),
            "text_length": text_len,
            "title": title,
            "doc_type": doc_type,
            "filepath": filepath,
            "success": success,
            "error": error,
        })

    def log_query(self, question: str, sources: list[str],
                  answer_len: int, duration_ms: float,
                  success: bool, error: Optional[str] = None) -> None:
        """Logs a query operation."""
        if not self._enabled:
            return
        self._append("queries.log", {
            "type": "query",
            "timestamp": self._now(),
            "question": question[:200],
            "sources": sources,
            "answer_length": answer_len,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error,
        })

    def log_error(self, source: str, message: str,
                  exception: Optional[Exception] = None,
                  context: Optional[dict] = None) -> None:
        """Logs an error with full stack trace."""
        if not self._enabled:
            return
        entry = {
            "type": "error",
            "timestamp": self._now(),
            "source": source,
            "message": message,
            "context": self._safe_str(context),
        }
        if exception:
            entry["exception"] = f"{type(exception).__name__}: {exception}"
            entry["traceback"] = traceback.format_exc()

        self._append("errors.log", entry)
        # Also write to session log
        self._append(f"session_{self._session_id}.log", entry)

    def log_frontend(self, level: str, source: str, message: str,
                     data: Any = None) -> None:
        """Logs an event from the frontend."""
        if not self._enabled:
            return
        self._append("frontend.log", {
            "type": "frontend",
            "timestamp": self._now(),
            "level": level,
            "source": source,
            "message": message,
            "data": self._safe_str(data, max_len=1000),
        })

    def log_generic(self, category: str, action: str, details: Any = None) -> None:
        """Logs a generic event."""
        if not self._enabled:
            return
        self._append("events.log", {
            "type": "event",
            "timestamp": self._now(),
            "category": category,
            "action": action,
            "details": self._safe_str(details, max_len=1000),
        })

    # ──────────────────────────────────────────────
    # Reading logs
    # ──────────────────────────────────────────────

    def list_log_files(self) -> list[dict]:
        """Returns a list of all log files."""
        files = []
        if self.debug_dir.exists():
            for f in sorted(self.debug_dir.glob("*.log")):
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(self.debug_dir)),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
        return files

    def read_log_file(self, filepath: str, max_lines: int = 500) -> list[dict]:
        """Reads a log file and returns parsed JSON entries."""
        full_path = self.debug_dir / filepath
        if not full_path.exists() or not full_path.is_file():
            return []

        entries = []
        with open(full_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        entries.append({"raw": line})
        return entries

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_str(self, obj: Any, max_len: int = 5000) -> str:
        """Safely converts an object to string with a length limit."""
        if obj is None:
            return ""
        try:
            if isinstance(obj, (dict, list)):
                s = json.dumps(obj, ensure_ascii=False, default=str)
            else:
                s = str(obj)
            if len(s) > max_len:
                s = s[:max_len] + f"... [truncated {len(s) - max_len} chars]"
            return s
        except Exception:
            return "<unprintable>"

    def _append(self, filename: str, entry: dict) -> None:
        """Appends a JSON entry to a log file."""
        filepath = self.debug_dir / filename
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Error writing debug log: {e}")

    def _write_settings(self) -> None:
        """Writes the current debug state to settings.json."""
        settings_path = self.debug_dir / "settings.json"
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self._enabled,
                    "session_id": self._session_id,
                    "updated_at": self._now(),
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error writing debug settings: {e}")

    def clear_all_logs(self) -> None:
        """Clears all log files on startup — always fresh debug info."""
        import shutil
        for f in self.debug_dir.glob("*.log"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Error clearing debug logs: {e}")
        for f in self.debug_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Error clearing debug settings: {e}")

    def _ensure_gitignore(self) -> None:
        """Creates .gitignore in debug/ if it doesn't exist."""
        gitignore_path = self.debug_dir / ".gitignore"
        if not gitignore_path.exists():
            try:
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write("# Debug logs - ignore all\n*\n")
            except Exception:
                pass


# Singleton
debug_logger = DebugLogger()