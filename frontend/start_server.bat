@echo off
chcp 65001 >nul
title pi_sb — Second Brain

echo ============================================
echo   🧠 pi_sb — Second Brain (Unified)
echo ============================================
echo.

:: ─── Frontend build check ───
if not exist "%~dp0frontend\dist\index.html" (
    echo [INFO] Frontend not built. Building...
    pushd "%~dp0frontend"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        echo [ERROR] Frontend build failed!
        pause
        exit /b 1
    )
    popd
    echo [INFO] Frontend built successfully.
) else (
    echo [INFO] Frontend dist found.
)

echo.

:: ─── Backend virtual environment ───
if not exist "%~dp0backend\env\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv "%~dp0backend\env"
    echo [INFO] Installing dependencies...
    call "%~dp0backend\env\Scripts\pip" install -r "%~dp0backend\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed.
) else (
    echo [INFO] Virtual environment found.
)

echo.
echo ============================================
echo   🚀 Starting pi_sb...
echo.
echo   📦 Frontend : http://localhost:8000
echo   🔧 Backend  : http://localhost:8000/api
echo   🎤 whisper.cpp : auto-started (embedded)
echo   🤖 Ollama   : %OLLAMA_HOST% (for LLM)
echo.
echo   Press Ctrl+C to stop
echo ============================================
echo.

pushd "%~dp0backend"
call env\Scripts\activate.bat
python -m app.main
popd

if errorlevel 1 (
    echo.
    echo [ERROR] Server stopped with an error!
    pause
)