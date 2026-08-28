#!/usr/bin/env bash
# ============================================================
# OilTrace — macOS/Linux Start (Poetry)
# Launches FastAPI (uvicorn) and Vite dev server side-by-side
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

cleanup() {
    echo ""
    echo "[OilTrace] Shutting down..."
    kill "$API_PID" "$UI_PID" 2>/dev/null || true
    wait "$API_PID" "$UI_PID" 2>/dev/null || true
    echo "[OilTrace] Stopped."
}
trap cleanup EXIT INT TERM

echo "[OilTrace] Starting API server on http://localhost:8000 ..."
poetry run python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "[OilTrace] Starting UI dev server on http://localhost:5173 ..."
(cd apps/web && pnpm run dev) &
UI_PID=$!

echo ""
echo "[OilTrace] Both servers running."
echo "  API:  http://localhost:8000"
echo "  UI:   http://localhost:5173"
echo "  Docs: http://localhost:8000/docs"
echo "  Press Ctrl+C to stop."
echo ""

wait
