# Production Dockerfile for Splintercom ClientPython
# Multi-stage: build deps → slim runtime image
# Target: ARM64 (Raspberry Pi)

# ---- Stage 1: Builder ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

COPY pyproject.toml /app/
COPY uv.lock /app/
RUN uv sync --no-dev --frozen

# ---- Stage 2: Runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

COPY --from=builder /app/.venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY . /app/

CMD ["uv", "run", "python", "main.py"]
