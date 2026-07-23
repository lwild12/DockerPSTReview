FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool pkg-config python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt requirements-dev.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels/dist -r requirements-dev.txt

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    pst-utils \
    libreoffice-writer libreoffice-calc libreoffice-impress \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi8 shared-mime-info \
    fonts-liberation fonts-dejavu-core \
    poppler-utils \
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /wheels/dist /wheels/dist
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels/dist -r requirements-dev.txt \
    && rm -rf /wheels

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
COPY pyproject.toml ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
