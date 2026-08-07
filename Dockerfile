FROM python:3.12-slim AS build

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates curl build-essential libssl-dev \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && /root/.local/bin/uv --version
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml README.md LICENSE ./
COPY scripts/ ./scripts/
COPY src/ ./src/

RUN uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install --system --no-cache --python=/opt/venv/bin/python \
        -e . \
 && /opt/venv/bin/python -c "import autodiag; print('autodiag', autodiag.__version__ if hasattr(autodiag, '__version__') else 'ok')"


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="AutoDiag OBD2 Scanner" \
      org.opencontainers.image.description="Diagnóstico OBD2 universal local-first + PDF + Orçamento + Live Captura + QR" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTODIAG_HOME=/data \
    AUTODIAG_DB_PATH=/data/history.db \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates tini libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libatspi2.0-0 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        fonts-liberation fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /data /app \
 && chown -R 10007:10007 /data /app

COPY --from=build /opt/venv /opt/venv
COPY --from=build /app /app

# Chromium do Playwright: ~120MB. Skip se quiser imagem mínima e só usar HTML/CSV.
# Para deploy em escala sem PDF, comente a linha abaixo e a anterior do apt com libs gtk.
RUN python -c "import shutil, subprocess, sys" 2>/dev/null; \
  if /opt/venv/bin/python -c "import playwright.sync_api" 2>/dev/null; then \
    /opt/venv/bin/playwright install --with-deps chromium 2>/dev/null || true; \
  fi

WORKDIR /app
VOLUME ["/data"]
EXPOSE 8000

USER 10007

ENTRYPOINT ["/usr/bin/tini", "--", "python", "-m", "uvicorn", "autodiag.web.server:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
