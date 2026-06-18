# beat-the-jam — FastAPI app served by uvicorn, dependencies managed by uv.
# Base image already bundles uv + CPython 3.12.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Compile bytecode for faster cold starts; copy packages into the layer
# (hardlinks don't survive across Docker's build cache mounts).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first so this layer is cached unless the lock or
# manifest changes. --no-dev drops pytest; --frozen forbids relocking.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application source (flat modules under src/, run via --app-dir).
COPY src ./src

EXPOSE 8000

# Bind to 0.0.0.0 so the port is reachable from outside the container.
# No cache by design: each request downloads that day's M05A archive live.
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "main:app", \
     "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
