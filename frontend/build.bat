@echo off
chcp 65001 >nul
title pi_sb — Frontend Build

echo ============================================
echo   📦 pi_sb — Frontend Build
echo ============================================
echo.

pushd "%~dp0"

:: ─── Install dependencies if needed ───
if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed.
    echo.
)

:: ─── Build ───
echo [INFO] Building frontend...
call npm run build
if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ Frontend built successfully!
echo   📁 Output: dist/
echo ============================================
echo.

popd

pause