# syntax=docker/dockerfile:1
FROM python:3.12-slim

# OCR för protokoll som bara innehåller bilder (#52): Tesseract och svensk språkdata (tessdata_best).
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
ENV TESSDATA_PREFIX=/opt/tessdata
ADD --checksum=sha256:360303308aa5d4a912ac3b3637691152b7532d9bd6e960639db1affb83db7ea9 \
    https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/swe.traineddata \
    /opt/tessdata/swe.traineddata

# Omräkning av SKR:s prognosunderlag för Härnösand (#61): LibreOffice Calc utan grafiskt gränssnitt.
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-calc-nogui     && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
RUN uv sync --locked --no-dev

EXPOSE 8000
# Migreringarna körs när appen startar.
CMD ["/app/.venv/bin/uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
