# PST Document Review

A self-hosted eDiscovery/document review tool for Outlook PST files — import, de-duplicate, thread, review, tag, redact, and export a Bates-numbered production set, all from a browser.

## Features

- **PST import** — parses email, attachments (as their own reviewable documents), contacts, and calendar items out of a `.pst` file, using `libpff-python` with an automatic `readpst` fallback for PSTs that fail to open directly.
- **De-duplication** — case-wide, content-hash based; duplicates link back to a primary document instead of being re-reviewed.
- **Email threading** — groups messages into threads via `Message-ID`/`In-Reply-To`/`References`, with a subject/participant fallback for messages missing real headers.
- **Rendering** — every document (email, attachment, contact, calendar item) is rendered to PDF for consistent viewing/redaction/export, regardless of its native format (Office docs via LibreOffice, images via Pillow, HTML email via WeasyPrint).
- **Review workflow** — tag documents, organize them into review sets, and track a per-document review status (unreviewed / in review / reviewed / flagged).
- **Redaction** — draw redaction rectangles directly on the rendered PDF in the browser; burn-in happens at export time and genuinely strips the underlying content (not just an overlay).
- **Export** — produce a Bates-numbered production set (one PDF per document + a CSV Bates log, zipped) or a single combined PDF, independent of whether Bates numbering is applied.
- **Full-text search** — Postgres `tsvector`-backed search across subject/sender/body/OCR text, ranked by relevance, with a trigram-indexed substring fallback.
- **OCR** — scanned/image-only attachments are automatically run through Tesseract at render time, so their text becomes searchable and reviewable.
- **Audit log** — every meaningful action (imports, tagging, redaction, review-set changes, exports, membership changes) is recorded and browsable per case.
- **Multi-user, per-case roles** — `admin` (manage case/members/import/export), `reviewer` (tag/redact/review), `viewer` (read-only).

## Architecture

| Layer | Tech |
|---|---|
| Backend API | FastAPI (async), SQLAlchemy 2.0 + asyncpg, Alembic migrations |
| Background jobs | Celery + Redis (PST ingestion, rendering, export) |
| Database | PostgreSQL 16 |
| Auth | `fastapi-users`, cookie-based JWT sessions, per-case RBAC |
| PST parsing | `libpff-python`, with `readpst` (`pst-utils`) as a fallback/contacts exporter |
| PDF pipeline | PyMuPDF (`fitz`) for redaction burn-in, Bates stamping, and merging; WeasyPrint for email→PDF; LibreOffice headless for Office docs; Pillow/img2pdf for images |
| OCR | Tesseract via `pytesseract` |
| Frontend | React + TypeScript + Vite, Mantine UI, TanStack Query, React Router, `react-pdf` |

Case files (uploads, staged extraction, native attachments, rendered PDFs, exports) live on a Docker volume mounted only into the `backend` and `worker` containers — never served as static content. All document access goes through authenticated, case-membership-checked API endpoints.

### Repository layout

```
backend/
  app/
    api/routers/     # FastAPI routers (cases, documents, tags, review-sets, redactions, export-jobs, audit, ...)
    models/          # SQLAlchemy models
    schemas/         # Pydantic request/response schemas
    services/        # PST extraction, dedup, threading, rendering, PDF processing, OCR, storage
    tasks/           # Celery tasks (ingest, render, export)
  alembic/versions/  # DB migrations
  tests/             # pytest suite
frontend/
  src/
    api/             # fetch wrappers per resource
    pages/           # route-level components
    components/      # PDF viewer, redaction overlay, document table, etc.
```

## Running it

Requires Docker and Docker Compose.

```bash
cp .env.example .env
# edit .env — at minimum set a real JWT_SECRET before deploying anywhere but localhost

make up          # docker compose up -d --build
make migrate     # docker compose exec backend alembic upgrade head
```

The frontend dev server is at `http://localhost:5173`, the API at `http://localhost:8000`. Register a user via the login page (self-serve registration — the first user in a case that creates it becomes that case's admin).

Other Makefile targets:

```bash
make logs             # tail all container logs
make test             # run the backend pytest suite
make lint             # ruff check
make fmt              # ruff format
make makemigration m="message"   # generate a new Alembic migration
make shell-backend    # shell into the backend container
make down             # stop everything
```

`docker-compose.override.yml` is applied automatically in dev — it bind-mounts source into the containers and runs `uvicorn --reload` / `vite dev` for live reload. For a production-style build, run with `docker compose -f docker-compose.yml up -d --build` to skip the override.

### Environment variables

See `.env.example`. Notable ones:

- `JWT_SECRET` — must be a long random value in any non-local deployment; sessions are forgeable otherwise (the backend logs a startup warning if it's left at the placeholder).
- `STORAGE_ROOT` — where case files live inside the `backend`/`worker` containers (defaults to the `case_storage` volume at `/data`).
- `COOKIE_SECURE` — set to `true` once served over HTTPS.

## Development without Docker

Each service can also be run natively (useful for iterating without a rebuild):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# needs a running Postgres + Redis, and: pst-utils, libreoffice, tesseract-ocr, poppler-utils
export DATABASE_URL=postgresql+asyncpg://pstreview:change-me@localhost:5432/pstreview
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head
uvicorn app.main:app --reload          # API
celery -A app.celery_app worker --loglevel=info   # in a second shell
```

```bash
cd frontend
npm install
VITE_PROXY_TARGET=http://localhost:8000 npm run dev
```

Backend tests spin up an isolated `<db>_test` Postgres database automatically (never touches the dev database):

```bash
cd backend
pytest
```

## API

The full OpenAPI schema is served at `/openapi.json` (Swagger UI at `/docs`) once the backend is running. Endpoints are organized around a case (`/api/cases/{case_id}/...`): custodians, import-jobs, documents, threads, tags, review-sets, redactions, export-jobs, audit-logs, plus case membership management and `fastapi-users`' auth routes.

## Known limitations

- Calendar item detailed fields (start/end/location/attendees) depend on PST-specific MAPI named-property resolution that isn't implemented yet — calendar items import and are reviewable, but only with reduced metadata fidelity.
- No S3-compatible object storage backend yet — case files live on a local Docker volume, which is fine for a single self-hosted server but doesn't horizontally scale. Swapping this out is isolated to `backend/app/services/storage.py`.
