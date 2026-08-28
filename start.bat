@echo off
REM ============================================================
REM OilTrace — Windows Start (Poetry)
REM Launches FastAPI (uvicorn) and Vite dev server side-by-side
REM ============================================================

echo [OilTrace] Starting API server on http://localhost:8000 ...
start "OilTrace API" cmd /k "cd /d %~dp0 && poetry run python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000"

echo [OilTrace] Starting UI dev server on http://localhost:5173 ...
start "OilTrace UI" cmd /k "cd /d %~dp0\apps\web && pnpm run dev"

echo.
echo [OilTrace] Both servers starting in new windows.
echo   API:  http://localhost:8000
echo   UI:   http://localhost:5173
echo   Docs: http://localhost:8000/docs
