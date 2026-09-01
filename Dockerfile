FROM python:3.11.16-slim-trixie@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements-build.lock ./
RUN python -m pip install --require-hashes --requirement requirements-build.lock
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m pip wheel --no-build-isolation --no-deps --wheel-dir /wheel .

FROM python:3.11.16-slim-trixie@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6

LABEL org.opencontainers.image.title="Math Anchor Runtime" \
      org.opencontainers.image.description="Headless deterministic mathematical runtime for Agents" \
      org.opencontainers.image.source="https://github.com/tetracoralla/math-anchor" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /opt/math-anchor
COPY requirements-runtime.lock ./
RUN python -m pip install --require-hashes --requirement requirements-runtime.lock
COPY --from=builder /wheel/math_anchor-*.whl /tmp/
RUN python -m pip install --no-deps /tmp/math_anchor-*.whl && \
    rm /tmp/math_anchor-*.whl && \
    python -c 'import math_anchor; print(math_anchor.__version__)'

USER 65532:65532
ENTRYPOINT ["python", "-m", "math_anchor.mcp_server"]
