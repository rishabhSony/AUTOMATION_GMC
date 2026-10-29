# syntax=docker/dockerfile:1.7
# QuotePulse GMC API (FastAPI · Polars · Docling/PyMuPDF), Python 3.11, non-root.
#
#   docker build -t quotepulse-api services/backend
#   (behind a TLS-inspecting proxy add: --secret id=corp_ca,src=/path/to/ca.pem)
#
# torch (pulled in by Docling) comes from the CPU-only wheel index (TORCH_INDEX_URL): the
# CUDA builds on PyPI add several GB and the EC2 target has no GPU.

ARG PYTHON_IMAGE=python:3.11-slim

# --- dependencies (virtualenv built once, copied into the runtime) ------------
FROM ${PYTHON_IMAGE} AS deps
# Extra index for torch; empty (--build-arg TORCH_INDEX_URL=) installs the PyPI build.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY requirements.txt /tmp/requirements.txt
# Optional corporate/TLS-inspection CA (TRD §6): docker build --secret id=corp_ca,src=ca.pem
# Mounted for this step only; it never lands in an image layer.
RUN --mount=type=secret,id=corp_ca,required=false \
    if [ -s /run/secrets/corp_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/corp_ca > /tmp/ca-bundle.pem; \
      export PIP_CERT=/tmp/ca-bundle.pem SSL_CERT_FILE=/tmp/ca-bundle.pem UV_NATIVE_TLS=1; \
    fi; \
    pip install "uv>=0.5,<1" \
 && uv venv /opt/venv \
 && uv pip install --python /opt/venv/bin/python \
      --index-strategy unsafe-best-match \
      ${TORCH_INDEX_URL:+--extra-index-url "$TORCH_INDEX_URL"} \
      -r /tmp/requirements.txt \
 && rm -f /tmp/ca-bundle.pem

# --- runtime ------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ARG APP_UID=10001
# No OS packages needed: Docling pulls opencv-python-headless, whose wheel bundles its libs.
RUN useradd --uid ${APP_UID} --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data/storage/inputs /data/storage/outputs \
 && chown -R app:app /data/storage
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    STORAGE_BACKEND=local \
    LOCAL_STORAGE_PATH=/data/storage \
    HF_HOME=/home/app/.cache/huggingface
COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app app ./app
COPY --chown=app:app pyproject.toml ./
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
