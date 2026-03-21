.PHONY: serve serve-http install dev docker docker-run kill-ports help

PORTS ?= 8000

help:
	@echo "OpenX MCP Server"
	@echo ""
	@echo "  make install     — install the package (editable) + dependencies"
	@echo "  make serve       — start the MCP server (stdio transport)"
	@echo "  make serve-http  — start the MCP server (HTTP transport on :8000)"
	@echo "  make dev         — install + start in HTTP mode for development"
	@echo "  make docker      — build the Docker image"
	@echo "  make docker-run  — run the server in Docker (HTTP on :8000)"
	@echo "  make kill-ports  — kill processes on port(s) (default: 8000)"
	@echo ""

install:
	pip install -e .

serve:
	@cd "$(CURDIR)" && ./run-openx-agent

serve-http:
	@cd "$(CURDIR)" && ./run-openx-agent --http --host 127.0.0.1 --port 8000

dev: install serve-http

docker:
	docker build -t openx-mcp .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env openx-mcp

kill-ports:
	@for p in $(PORTS); do \
		pid=$$(lsof -ti:$$p 2>/dev/null); \
		if [ -n "$$pid" ]; then \
			echo "Killing process(es) on port $$p: $$pid"; \
			kill -9 $$pid 2>/dev/null || true; \
		else \
			echo "No process on port $$p"; \
		fi; \
	done
