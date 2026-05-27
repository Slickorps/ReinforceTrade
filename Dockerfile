# =============================================================================
# ReinforceTrade - Multi-Language Docker Build
#
# Stages:
#   1. rust-builder   - Builds the Rust high-performance engine
#   2. go-builder     - Builds the Go monitoring agent
#   3. python-base    - Python runtime with Rust engine
#   4. production     - Final image with all components
# =============================================================================

# ---- Stage 1: Rust Builder ----
FROM rust:1.77-slim AS rust-builder

WORKDIR /rust-build
COPY rust/ .

# Build release version of the Rust engine
RUN cargo build --release && \
    # Copy the compiled library to a known location
    cp target/release/*.dll /usr/lib/ 2>/dev/null; \
    cp target/release/*.so /usr/lib/ 2>/dev/null; \
    cp target/release/libreforcetrade_engine* /usr/lib/ 2>/dev/null; \
    # Also build the maturin wheel for Python
    pip install maturin && \
    maturin build --release --out /wheels/ 2>/dev/null || \
    echo "maturin wheel build skipped (not a pyo3 project)"

# ---- Stage 2: Go Builder ----
FROM golang:1.22-alpine AS go-builder

WORKDIR /go-build
COPY monitor/ .

# Build the Go monitoring agent as a static binary
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /monitor-agent .

# ---- Stage 3: Python Base ----
FROM python:3.11-slim AS python-base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Copy Rust engine (if built)
COPY --from=rust-builder /wheels/ /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl 2>/dev/null || \
    echo "Rust engine wheel not available, using pure Python mode"

# Copy Go monitoring agent
COPY --from=go-builder /monitor-agent /usr/local/bin/monitor-agent

# Create necessary directories
RUN mkdir -p logs reports models data optimization web/static

# Set environment variables
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV MONITOR_PORT=:9090

# Expose ports
EXPOSE 8000 9090

# Default command
CMD ["python", "-m", "trading_bot"]