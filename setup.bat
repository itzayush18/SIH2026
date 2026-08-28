@echo off
REM ============================================================
REM OilTrace — Windows Setup (Poetry)
REM Installs Python deps via Poetry and UI deps via pnpm
REM ============================================================

echo [OilTrace] Installing Python dependencies via Poetry...
poetry install
if errorlevel 1 (
    echo [ERROR] poetry install failed. Ensure Poetry is installed: pip install poetry
    exit /b 1
)

echo [OilTrace] Installing UI dependencies via pnpm...
cd apps\web
call pnpm install
if errorlevel 1 (
    echo [ERROR] pnpm install failed. Ensure pnpm is installed: npm i -g pnpm
    cd ..\..
    exit /b 1
)
cd ..\..

echo.
echo [OilTrace] Setup complete!
echo   Run start.bat to launch the API and UI.
