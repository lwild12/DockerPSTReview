# PST Document Review

A self-hosted eDiscovery/document review tool for Outlook PST files — import, de-duplicate, thread, review, tag, redact, and export a Bates-numbered production set, all from a browser.

This guide assumes no prior familiarity with the project. Follow it top to bottom.

## 1. What you need before you start

- **Docker Desktop** (Mac/Windows) or **Docker Engine + the Compose plugin** (Linux). This is the only real dependency — Postgres, Redis, and all the PDF/OCR tooling run inside containers, so you do not need to install Python, Node, Postgres, Tesseract, or anything else yourself.
  - Mac/Windows: install Docker Desktop from https://www.docker.com/products/docker-desktop/ and start it.
  - Linux: install Docker Engine + the Compose plugin per your distro (e.g. https://docs.docker.com/engine/install/), then make sure your user can run `docker` without `sudo` (`sudo usermod -aG docker $USER`, then log out/in).
- **Git**, to clone the repository.
- About **4 GB of free disk space** (container images include LibreOffice and Tesseract, which aren't tiny) and a few minutes for the first build.

Verify Docker is ready before continuing:

```bash
docker --version
docker compose version
```

Both commands must succeed (not `command not found`, not an error). If `docker compose version` fails but `docker-compose --version` works instead, you have the old standalone Compose — upgrade Docker Desktop, or install the `docker-compose-plugin` package on Linux; the rest of this guide assumes `docker compose` (two words, no hyphen).

## 2. Get the code

```bash
git clone <this-repository-url>
cd DockerPSTReview
```

## 3. Configure

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` in a text editor. For trying it out on your own machine, the defaults work as-is — you don't need to change anything to get started. Before you consider this reachable from anywhere other than `localhost`, though, change these two values:

- `JWT_SECRET` — replace `change-me-to-a-long-random-string` with a long random string (e.g. run `openssl rand -hex 32` and paste the output). This signs login sessions; leaving it at the default means anyone can forge a login. The backend will print a warning in its logs on startup if you forget.
- `POSTGRES_PASSWORD` — replace `change-me` with something real.

## 4. Start everything

```bash
make up
```

This runs `docker compose up -d --build`. The first run downloads base images and builds the backend/frontend containers, which can take several minutes — that's normal. When it finishes, check that everything is actually running:

```bash
docker compose ps
```

You should see five services (`postgres`, `redis`, `backend`, `worker`, `frontend`) all showing `Up` (postgres/redis will show `Up (healthy)` once their health checks pass, which takes a few seconds).

## 5. Set up the database

The containers are running, but the database schema doesn't exist yet. Create it:

```bash
make migrate
```

Expected output ends with something like `Running upgrade ... -> ..., add ocr fields and extend search vector` and no errors. You only need to run this once (and again after pulling code that adds a new migration).

## 6. Open the app

Go to **http://localhost:5173** in your browser. You'll land on a login page. There is no sign-up button in the UI yet — the first account has to be created through the API directly, once, as follows.

### Create your first account

Go to **http://localhost:8000/docs** (the API's interactive documentation). This works entirely by clicking, no terminal needed:

1. Find **`POST /api/auth/register`** in the list and click it to expand it.
2. Click **"Try it out"**.
3. Replace the example JSON with your own email and password, e.g.:
   ```json
   {
     "email": "you@example.com",
     "password": "choose-a-real-password",
     "full_name": "Your Name"
   }
   ```
4. Click **"Execute"**. A `201` response means your account was created.

(If you'd rather use a terminal, this is equivalent:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"choose-a-real-password","full_name":"Your Name"}'
```
)

Now go back to **http://localhost:5173/login** and sign in with that email and password.

## 7. Your first case, start to finish

Everything in this app is scoped to a **case**. Whoever creates a case automatically becomes its **admin**.

1. **Create a case** — after logging in you land on the case list. Click **"New case"**, give it a name, submit.
2. **Add a custodian** — open the case, click **"Add custodian"**. A custodian represents the person whose mailbox you're importing (name + optional email).
3. **Import a PST** — click **"Import PST"**, choose the custodian, choose a `.pst` file, submit. This kicks off a background job: the page polls its status (extracting → parsing → dedup → rendering → completed) until it's done. Large PSTs can take a while — this all happens in the `worker` container, so you can navigate away and come back.
4. **Browse documents** — click **"Documents"**. Filter by type (email/attachment/contact/calendar), search by keyword (full-text search covers subject, sender, body, and OCR'd text from scanned attachments), and open any document to view its rendered PDF.
5. **Tag and review** — on a document, apply tags, or select several documents from the list and add them to a **review set**, then work through them setting each one's review status (unreviewed / in review / reviewed / flagged).
6. **Redact** — open a document, click **"Redact"**, drag rectangles over anything sensitive. This saves immediately; nothing is permanently altered until export.
7. **Export** — click **"Export"** on the case, pick a review set, choose **Bates-numbered production set** (one PDF per document + a Bates log CSV, zipped) or **single combined PDF**, optionally set a Bates prefix/start number, and submit. Redactions are burned in (genuinely removed, not just covered) at this point. Download once the job shows **completed**.
8. **Audit log** — as an admin, click **"Audit log"** on the case to see a record of every import, tag, redaction, review-set, and export action taken on it.

To work with others, have them create their own account (step 6), then as the case admin go to the case page and use **"Add member"** with their user ID and a role (`admin` / `reviewer` / `viewer`). You can find a user's ID via `GET /api/auth/users/me` (while logged in as them) or the `/docs` page.

## Everyday commands

```bash
make logs             # tail all container logs (Ctrl+C to stop watching)
make down              # stop everything (data is preserved in Docker volumes)
make up                 # start it back up
docker compose logs -f worker   # just the background-job worker, e.g. while debugging an import
```

To update after pulling new code:

```bash
git pull
make up          # rebuilds changed images
make migrate     # applies any new database migrations
```

To wipe everything and start completely fresh (**this deletes all imported data**):

```bash
make down
docker volume rm dockerpstreview_pgdata dockerpstreview_redis_data dockerpstreview_case_storage
make up
make migrate
```
(the volume name prefix matches your project directory name — run `docker volume ls` if the above names don't match).

## Troubleshooting

- **`docker compose ps` shows a service restarting/unhealthy** — check its logs: `docker compose logs backend` (or `worker`, `postgres`, etc.). The most common cause is `make migrate` not having been run yet.
- **Port already in use** (`5173` or `8000`) — something else on your machine is using that port. Stop it, or edit the `ports:` mapping for that service in `docker-compose.yml`/`docker-compose.override.yml`.
- **Login says "Invalid email or password" right after registering** — double check you registered against `http://localhost:8000` (the backend, not the frontend on `5173`), and that email/password match exactly.
- **PST import job stays "pending" forever** — the `worker` container may not be running; check `docker compose ps` and `docker compose logs worker`.
- **A warning about `JWT_SECRET` in the logs** — expected if you skipped changing it in step 3; harmless for local trying-out, but fix it before exposing this beyond your own machine.
- **On Windows**, make sure Docker Desktop is set to use the WSL2 backend and that the repository is cloned inside your WSL filesystem (not `C:\...`) for reasonable performance.

## Advanced

### Architecture

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

Roles: `admin` (manage case/members/import/export), `reviewer` (tag/redact/review), `viewer` (read-only).

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

### More Makefile targets

```bash
make build             # docker compose build (no start)
make test              # run the backend pytest suite
make lint               # ruff check
make fmt                 # ruff format
make makemigration m="message"   # generate a new Alembic migration
make shell-backend    # shell into the backend container
```

`docker-compose.override.yml` is applied automatically in dev — it bind-mounts source into the containers and runs `uvicorn --reload` / `vite dev` for live reload. For a production-style build, run with `docker compose -f docker-compose.yml up -d --build` to skip the override.

### All environment variables

See `.env.example` for the full list. Beyond `JWT_SECRET` and `POSTGRES_PASSWORD` (covered in step 3):

- `STORAGE_ROOT` — where case files live inside the `backend`/`worker` containers (defaults to the `case_storage` volume at `/data`); not something you need to change for a Docker setup.
- `COOKIE_SECURE` — set to `true` once served over HTTPS.
- `BACKEND_CORS_ORIGINS` — origins allowed to call the API; adjust if you serve the frontend from somewhere other than `localhost:5173`.

### Development without Docker

Each service can also be run natively (useful for iterating without a rebuild). This requires installing Python 3.12, Node.js, Postgres, Redis, and the native tooling (`pst-utils`, LibreOffice, `tesseract-ocr`, `poppler-utils`) yourself — the whole point of the Docker path above is that you don't have to.

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

### API reference

The full OpenAPI schema is served at `/openapi.json` (interactive Swagger UI at `/docs`) once the backend is running. Endpoints are organized around a case (`/api/cases/{case_id}/...`): custodians, import-jobs, documents, threads, tags, review-sets, redactions, export-jobs, audit-logs, plus case membership management and `fastapi-users`' auth routes.

### Known limitations

- Calendar item detailed fields (start/end/location/attendees) depend on PST-specific MAPI named-property resolution that isn't implemented yet — calendar items import and are reviewable, but only with reduced metadata fidelity.
- No S3-compatible object storage backend yet — case files live on a local Docker volume, which is fine for a single self-hosted server but doesn't horizontally scale. Swapping this out is isolated to `backend/app/services/storage.py`.
- No sign-up page in the frontend UI yet — the first (and every) account is created via the `/docs` page or a direct API call, as shown in step 6 above.
