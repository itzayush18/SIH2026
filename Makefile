# OilTrace — Makefile (macOS / Linux, Poetry)

.PHONY: setup dev test clean

setup:
	@echo "[OilTrace] Installing Python dependencies via Poetry..."
	poetry install
	@echo "[OilTrace] Installing UI dependencies via pnpm..."
	cd apps/web && pnpm install
	@echo "[OilTrace] Setup complete! Run 'make dev' to start."

dev:
	@chmod +x start.sh
	@./start.sh

test:
	poetry run pytest tests/ -v

clean:
	rm -rf .venv apps/web/node_modules
	@echo "[OilTrace] Cleaned."
