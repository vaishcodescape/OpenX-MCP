FROM python:3.12-slim AS base

WORKDIR /app

# Install git and gh (GitHub CLI)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends gh && \
    apt-get purge -y --auto-remove curl && \
    rm -rf /var/lib/apt/lists/*

FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS runtime

# Create a non-root user for security (AWS Best Practice)
RUN useradd -m -u 1000 openxuser && \
    chown -R openxuser:openxuser /app

COPY --chown=openxuser:openxuser pyproject.toml .
COPY --chown=openxuser:openxuser README.md .
COPY --chown=openxuser:openxuser openx-agent/ openx-agent/

RUN ln -s openx-agent openx_agent && \
    chown -h openxuser:openxuser openx_agent

# Set standard AWS environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Switch to non-root user
USER openxuser

EXPOSE ${PORT}

# Healthcheck using the configured port
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx, os; httpx.get(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/health').raise_for_status()" || exit 1

ENTRYPOINT ["python", "-m", "openx_agent.server"]
# Use SSE transport for better compatibility with AWS ALBs/API Gateways
CMD ["--sse", "--host", "0.0.0.0"]
