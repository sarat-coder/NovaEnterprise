# NovaEnterprise Makefile
# Requires: uv, GNU Make (Git for Windows / WSL / macOS / Linux)
#
# Windows note: .venv\Scripts\python.exe — the PYTHON variable handles this.
# PYTHONPATH must include `backend` so `import app.*` resolves.
# PYTHONIOENCODING=utf-8 avoids box-drawing issues on Windows terminals.

SHELL := bash

# Detect OS and choose the right venv binary path
ifeq ($(OS),Windows_NT)
    PYTHON   := .venv/Scripts/python.exe
    PIP      := .venv/Scripts/pip.exe
    SEP      := ;
else
    PYTHON   := .venv/bin/python
    PIP      := .venv/bin/pip
    SEP      := :
endif

UV       := uv
BACKEND  := backend
PORT     := 8001

.PHONY: setup backend test lint ingest seed-graph demo help

## setup: create .venv with uv, install all dependencies, copy .env if missing
setup:
	$(UV) sync --all-groups
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; fi

## backend: start FastAPI on :8001 (reload enabled)
backend:
	PYTHONPATH=$(BACKEND)$(SEP)$$PYTHONPATH PYTHONIOENCODING=utf-8 \
	$(UV) run uvicorn app.main:app \
	    --host 0.0.0.0 --port $(PORT) --reload \
	    --app-dir $(BACKEND)

## test: run the full offline pytest suite
test:
	PYTHONPATH=$(BACKEND)$(SEP)$$PYTHONPATH \
	LLM_PROVIDER=fake VECTOR_STORE=memory GRAPH_STORE=memory \
	$(UV) run pytest tests/ -v

## lint: ruff check and format verification
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

## ingest: (re)index all sample documents — added in Phase 9
ingest:
	@echo "ingest target is added in Phase 9"

## seed-graph: build the in-memory or Neo4j graph — added in Phase 7
seed-graph:
	@echo "seed-graph target is added in Phase 7"

## demo: run canonical question end-to-end — added in Phase 12
demo:
	@echo "demo target is added in Phase 12"

## help: show available targets
help:
	@grep -E '^## ' Makefile | sed 's/## //'
