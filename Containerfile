# Multi-stage build for Konflux DevLake MCP Server using Red Hat UBI
# Stage 1: Builder - Install dependencies and build packages
FROM registry.access.redhat.com/ubi9/ubi as builder

# Set build arguments for potential customization
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

# Set working directory
WORKDIR /app

# Install Python 3.11 and system dependencies required for building Python packages
# python3.11, python3.11-pip: Python 3.11 runtime and package manager
# gcc, gcc-c++: Required for compiling C extensions (cryptography, bcrypt, etc.)
# libffi-devel: Required for cryptography
# openssl-devel: Required for SSL/TLS support
# python3.11-devel: Python development headers
# git: Required for installing packages from git repositories (toon-format)
# Note: Python 3.11 is required for mcp>=1.8.0
# Update all packages first to get latest security patches
RUN dnf update -y --nodocs \
    && dnf install -y --nodocs \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    gcc-c++ \
    libffi-devel \
    openssl-devel \
    git \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Create symlinks for python3 and pip3 to point to python3.11
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

# Upgrade pip to latest version for better dependency resolution
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better Docker layer caching
# This layer will only be rebuilt if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip3 install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Minimal production image
FROM registry.access.redhat.com/ubi9/ubi

# Set metadata labels for better image management
LABEL maintainer="Konflux CI" \
      org.opencontainers.image.title="Konflux DevLake MCP Server" \
      org.opencontainers.image.description="MCP server providing natural language access to Konflux DevLake databases" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="Konflux" \
      com.redhat.license_terms="https://www.redhat.com/en/about/red-hat-end-user-license-agreements#UBI"

# Set working directory
WORKDIR /app

# Install Python 3.11 and minimal runtime dependencies
# python3.11: Python 3.11 runtime (required for mcp>=1.8.0)
# ca-certificates: For SSL/TLS certificate validation
# libffi: Runtime library for cryptography
# openssl-libs: Runtime library for SSL/TLS
# Update all packages to get latest security patches
RUN dnf update -y --nodocs \
    && dnf install -y --nodocs \
    python3.11 \
    ca-certificates \
    libffi \
    openssl-libs \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Create symlink for python3 to point to python3.11
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Copy Python dependencies from builder stage
# Install to a location accessible by the devlake user
COPY --from=builder /root/.local /usr/local

# Ensure Python can find the installed packages
ENV PATH=/usr/local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
# Copy files in order of change frequency (least to most frequent)
# This optimizes Docker layer caching
COPY __init__.py .
COPY konflux-devlake-mcp.py .
COPY server/ ./server/
COPY tools/ ./tools/
COPY utils/ ./utils/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chmod 755 /app/logs

# Set default environment variables
# These can be overridden at runtime via docker run -e or Kubernetes env vars
ENV LOG_DIR=/app/logs \
    LOG_LEVEL=INFO \
    TRANSPORT=http \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=3000

# Create non-root user for security
# Using numeric IDs for better Kubernetes compatibility
# Red Hat recommends using UID/GID 1001 for applications
RUN groupadd -r -g 1001 devlake && \
    useradd -r -u 1001 -g devlake -d /app -s /bin/bash devlake && \
    chown -R devlake:devlake /app

# Switch to non-root user
USER devlake

# Expose the HTTP port
EXPOSE 3000

# Health check using Python instead of curl (more reliable and no extra dependency)
# Checks the /health endpoint every 30 seconds
# Start period of 30s allows the server to start up
# Timeout of 5s gives enough time for the request
# Retries 3 times before marking as unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/health', timeout=3).read()" || exit 1

# Use exec form for better signal handling
# ENTRYPOINT allows overriding with custom arguments
ENTRYPOINT ["python3", "konflux-devlake-mcp.py"]

# Default command arguments
# These can be overridden via docker run or Kubernetes command/args
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "3000"]
