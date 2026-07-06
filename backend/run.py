"""
pi_sb — Second Brain
EXE entry point for PyInstaller frozen builds.
Starts the FastAPI/uvicorn server.
"""
import sys
import os
import webbrowser
from pathlib import Path


def ensure_env_file():
    """Creates a default .env next to the EXE if it doesn't exist."""
    if getattr(sys, 'frozen', False):
        env_path = Path(sys.executable).parent / ".env"
    else:
        env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        env_path.write_text(
            "# pi_sb — Second Brain\n"
            "# Automatically created on first run\n"
            "# Edit this file to configure your Ollama host and models\n\n"
            "OLLAMA_HOST=http://192.168.1.100:11434\n"
            "# OLLAMA_API_KEY=your-api-key-here\n"
            "CLOUD_MODELS=[]\n"
            "INGESTION_MODEL=gemma4:cloud\n"
            "RAG_MODEL=gemma4:cloud\n"
            "AUDIO_MODEL=ggml-medium.en-q5_0.bin\n"
            "DEBUG_ENABLED=true\n"
            "OKF_DATA_DIR=./data\n"
            "APP_NAME=pi_sb\n"
            "APP_VERSION=1.0.0\n"
            "AUDIO_UPLOAD_DIR=./data/audio\n"
            "BACKEND_URL=http://localhost:8000\n"
            "DEBUG=true\n",
            encoding="utf-8"
        )
        print(f"[pi_sb] Created default .env at {env_path}")
    return env_path


def main():
    """Entry point: ensure .env, start server, open browser."""
    # Force UTF-8 encoding for console output (avoid cp1251 emoji issues)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    print("=" * 50)
    print("  pi_sb -- Second Brain")
    print("=" * 50)
    print()

    # Ensure .env exists
    ensure_env_file()

    # Start uvicorn
    import uvicorn
    print("  Starting server on http://localhost:8000")
    print("  Frontend: http://localhost:8000")
    print("  Backend:  http://localhost:8000/api")
    print()

    # Open browser after a short delay
    import threading
    threading.Timer(2.0, lambda: webbrowser.open("http://localhost:8000")).start()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()