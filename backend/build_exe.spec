# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for pi_sb — Second Brain EXE.

Build:
    pyinstaller build_exe.spec

Output: build/pi_sb.exe (onefile — no _internal folder)
    pi_sb.exe                  # Single EXE with Python + frontend + config inside
    whisper.cpp/               # whisper.cpp binaries (copied by build_exe.bat)
    ffmpeg.exe                 # FFmpeg (copied by build_exe.bat)
    .env                       # User config (copied by build_exe.bat)
    data/                      # Runtime user data (created on first run)
"""

import sys
from pathlib import Path

# ─── Project paths ────────────────────────────────────────────
# __file__ is not available in PyInstaller spec context,
# so we use Path.cwd() — must run pyinstaller from backend/
BACKEND_DIR = Path.cwd().resolve()
PROJECT_ROOT = BACKEND_DIR.parent.resolve()

# ─── Block cipher ────────────────────────────────────────────
# PyInstaller's default is to obfuscate; we keep it simple.
block_cipher = None

# ─── Data files to bundle inside the EXE ──────────────────────
# These are loaded via get_app_internal_dir() (sys._MEIPASS)
datas = []

# Frontend dist — pre-built React app
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    datas.append(
        (str(frontend_dist), "frontend/dist")
    )
    print(f"[SPEC] Bundling frontend/dist: {frontend_dist}")
else:
    print("[SPEC] WARNING: frontend/dist not found — API-only mode")

# Config JSON
config_json = PROJECT_ROOT / "config" / "concept_types.json"
if config_json.exists():
    datas.append(
        (str(config_json), "config")
    )
    print(f"[SPEC] Bundling config/concept_types.json")

# Prompt files
prompts_dir = BACKEND_DIR / "app" / "config" / "prompts"
if prompts_dir.exists():
    datas.append(
        (str(prompts_dir), "backend/app/config/prompts")
    )
    print(f"[SPEC] Bundling backend/app/config/prompts/")

# ─── Hidden imports ───────────────────────────────────────────
# Modules that PyInstaller might miss
hiddenimports = [
    # Core
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "fastapi",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "loguru",
    "yaml",
    "python_multipart",
    "dotenv",
    "starlette",
    # App modules
    "app.main",
    "app.config.settings",
    "app.config.concept_types",
    "app.config.okf_schema",
    "app.core.storage",
    "app.core.processor",
    "app.core.debug_logger",
    "app.llm.ollama_client",
    "app.llm.llm_manager",
    "app.audio.transcriber",
    "app.audio.postprocessor",
    "app.wiki.indexer",
    "app.wiki.retriever",
    "app.api.input",
    "app.api.search",
    "app.api.settings",
    "app.api.debug",
    "app.api.data",
    "app.api.llm_router",
]

# ─── Excludes ─────────────────────────────────────────────────
# Things we don't need in the EXE
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "PIL",
    "cv2",
    "numpy",
    "tortoise",
    "pywin32",
]

# ─── PyInstaller analysis ─────────────────────────────────────
a = Analysis(
    [str(BACKEND_DIR / "run.py")],  # entry point
    pathex=[str(BACKEND_DIR)],       # PYTHONPATH
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(BACKEND_DIR / "pyinstaller_hooks")],
    hooksconfig={},
    excludes=excludes,
    runtime_hooks=[],
    cipher=block_cipher,
)

# ─── PYZ (compressed Python code) ────────────────────────────
pyz = PYZ(a.pure, cipher=block_cipher)

# ─── EXE (onefile — no COLLECT) ───────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pi_sb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,         # Show console window (for server logs)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,            # Optional: add an .ico file here
)
