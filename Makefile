# OpenX MCP — single commands to run openx-agent and openx-tui

.PHONY: openx-agent openx-tui kill-ports help

# Ports to kill (default: 8000 for openx-agent). Override: make kill-ports PORTS="8000 3000"
PORTS ?= 8000

help:
	@echo "OpenX MCP"
	@echo ""
	@echo "  make openx-agent  — start the Python MCP server (http://127.0.0.1:8000)"
	@echo "  make openx-tui    — build (if needed) and run the Rust TUI"
	@echo "  make kill-ports   — kill processes on port(s) (default: 8000; use PORTS=\"8000 3000\" for multiple)"
	@echo ""

openx-agent:
	@cd "$(CURDIR)" && ./run-openx-agent

openx-tui:
	@cd "$(CURDIR)/openx-tui" && \
	cargo build --release && \
	OPENX_BASE_URL=$${OPENX_BASE_URL:-http://127.0.0.1:8000} ./target/release/openx-tui

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
