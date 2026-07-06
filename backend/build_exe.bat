@echo off
chcp 65001 >nul
title pi_sb — EXE Build

echo ============================================
echo   🔨 pi_sb — EXE Build (PyInstaller)
echo ============================================
echo.

:: ─── Detect paths ─────────────────────────────
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"
set "BACKEND_DIR=%CD%"
popd

set "PROJECT_DIR=%BACKEND_DIR%\.."
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"
set "BUILD_DIR=%PROJECT_DIR%\build\pi_sb"
set "WHISPER_SRC=%PROJECT_DIR%\whisper.cpp"

echo [INFO] Project dir: %PROJECT_DIR%
echo [INFO] Backend dir: %BACKEND_DIR%
echo [INFO] Frontend dir: %FRONTEND_DIR%
echo [INFO] Output dir:  %BUILD_DIR%
echo.

:: ─── Clean previous build ─────────────────────
echo [0/5] Cleaning previous build...
if exist "%PROJECT_DIR%\build" (
    rmdir /S /Q "%PROJECT_DIR%\build"
    echo [OK] Old build removed
)
echo.

:: ─── Step 1: Build frontend ───────────────────
echo [1/5] Building frontend...
pushd "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo [INFO] Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
)
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
echo [OK] Frontend built
popd
echo.

:: ─── Step 2: Ensure PyInstaller ───────────────
echo [2/5] Checking PyInstaller...
python -m pip install pyinstaller 2>&1 | findstr /v "already satisfied"
echo [OK] PyInstaller ready
echo.

:: ─── Step 3: Run PyInstaller (--onefile) ──────
echo [3/5] Running PyInstaller (--onefile)...
pushd "%BACKEND_DIR%"
python -m PyInstaller --distpath "%BUILD_DIR%" --clean build_exe.spec
set "PYI_ERROR=%ERRORLEVEL%"
popd
if %PYI_ERROR% neq 0 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)
echo [OK] PyInstaller build complete — single pi_sb.exe (no _internal folder)
echo.

:: ─── Step 4: Copy whisper.cpp binaries ────────
echo [4/5] Copying whisper.cpp binaries...
set "WHISPER_OUT=%BUILD_DIR%\whisper.cpp"

if not exist "%WHISPER_OUT%" mkdir "%WHISPER_OUT%"

if exist "%WHISPER_SRC%\whisper-server.exe" (
    copy /Y "%WHISPER_SRC%\whisper-server.exe" "%WHISPER_OUT%" >nul
    echo [OK] whisper-server.exe copied
) else (
    echo [WARN] whisper-server.exe not found — audio transcription may not work
)

if exist "%WHISPER_SRC%\ggml-large-v3-q5_0.bin" (
    copy /Y "%WHISPER_SRC%\ggml-large-v3-q5_0.bin" "%WHISPER_OUT%" >nul
    echo [OK] ggml-large-v3-q5_0.bin copied
) else (
    echo [WARN] ggml-large-v3-q5_0.bin not found — audio transcription may not work
)

if exist "%WHISPER_SRC%\ggml-large-v3-turbo-q5_0.bin" (
    copy /Y "%WHISPER_SRC%\ggml-large-v3-turbo-q5_0.bin" "%WHISPER_OUT%" >nul
    echo [OK] ggml-large-v3-turbo-q5_0.bin copied
)

if exist "%WHISPER_SRC%\ggml-silero-v6.2.0.bin" (
    copy /Y "%WHISPER_SRC%\ggml-silero-v6.2.0.bin" "%WHISPER_OUT%" >nul
    echo [OK] ggml-silero-v6.2.0.bin copied
) else (
    echo [WARN] ggml-silero-v6.2.0.bin not found — VAD may not work
)
echo.

:: ─── Step 5: Copy ffmpeg if available ─────────
echo [5/5] Copying ffmpeg.exe...
if exist "%PROJECT_DIR%\ffmpeg.exe" (
    copy /Y "%PROJECT_DIR%\ffmpeg.exe" "%BUILD_DIR%" >nul
    echo [OK] ffmpeg.exe copied
) else if exist "%BACKEND_DIR%\ffmpeg.exe" (
    copy /Y "%BACKEND_DIR%\ffmpeg.exe" "%BUILD_DIR%" >nul
    echo [OK] ffmpeg.exe copied from backend/
) else (
    echo [INFO] ffmpeg.exe not found — will use system PATH or fallback
)
echo.

:: ─── Copy .env from project root ──────────────
echo [5/5] Copying .env from project root...
if exist "%PROJECT_DIR%\.env" (
    copy /Y "%PROJECT_DIR%\.env" "%BUILD_DIR%\.env" >nul
    echo [OK] .env copied from %PROJECT_DIR%\.env
) else if not exist "%BUILD_DIR%\.env" (
    (
        echo # pi_sb — Second Brain
        echo # Edit this file to configure your Ollama host and models
        echo.
        echo OLLAMA_HOST=https://api.ollama.com
        echo # OLLAMA_API_KEY=your-api-key-here
        echo CLOUD_MODELS=["gemma4:cloud"]
        echo INGESTION_MODEL=gemma4:cloud
        echo RAG_MODEL=gemma4:cloud
        echo AUDIO_MODEL=ggml-large-v3-q5_0.bin
        echo DEBUG_ENABLED=true
        echo OKF_DATA_DIR=./data
        echo APP_NAME=pi_sb
        echo APP_VERSION=1.0.0
        echo AUDIO_UPLOAD_DIR=./data/audio
        echo BACKEND_URL=http://localhost:8000
        echo DEBUG=true
    ) > "%BUILD_DIR%\.env"
    echo [OK] .env template created (no API key)
) else (
    echo [OK] .env already exists
)
echo.

:: ─── Clean up PyInstaller temp files ──────────
echo [Cleanup] Removing PyInstaller temp files...
if exist "%BACKEND_DIR%\build" (
    rmdir /S /Q "%BACKEND_DIR%\build"
)
if exist "%BACKEND_DIR%\__pycache__" (
    rmdir /S /Q "%BACKEND_DIR%\__pycache__"
)
echo [OK] Cleanup done
echo.

:: ─── Done ──────────────────────────────────────
echo ============================================
echo   ✅ Build complete!
echo.
echo   📁 Output: %BUILD_DIR%
echo.
echo   🚀 To run: %BUILD_DIR%\pi_sb.exe
echo.
echo   💡 pi_sb.exe — single file (no _internal folder)
echo   ℹ️  data/ and debug/ will be created on first run
echo ============================================
echo.

pause
