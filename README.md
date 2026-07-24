# PST Document Review

A self-hosted eDiscovery/document review tool for Outlook PST files — import, de-duplicate, thread, review, tag, redact, and export a Bates-numbered production set, all from a browser.

This guide assumes no prior familiarity with the project. Follow it top to bottom.

## Quick install (Ubuntu Server)

If you just want it running on a fresh Ubuntu Server with no manual steps, run:

```bash
curl -fsSL https://raw.githubusercontent.com/lwild12/DockerPSTReview/main/install.sh | sudo bash
```

This installs Docker if it isn't already present, clones the repo to `/opt/DockerPSTReview`, generates a `.env` with real random secrets (never overwriting one that already exists, so it's safe to re-run), and brings the whole stack up. It prints the URLs to use when it's done. Skip straight to [step 6](#6-your-first-case-start-to-finish) below to create your first account and case — everything before that is what the script just did for you.

Prefer to do it by hand, understand each step, or you're not on Ubuntu? Continue reading.

## 1. What you need before you start

- **Docker Desktop** (Mac/Windows) or **Docker Engine + the Compose plugin** (Linux). This is the only real dependency — Postgres, Redis, and all the PDF/OCR tooling run inside containers, so you do not need to install Python, Node, Postgres, Tesseract, or anything else yourself.
  - Mac/Windows: install Docker Desktop from https://www.docker.com/products/docker-desktop/ and start it.
  - Linux: install Docker Engine + the Compose plugin per your distro (e.g. https://docs.docker.com/engine/install/), then make sure your user can run `docker` without `sudo` (`sudo usermod -aG docker $USER`, then log out/in).
- **Git**, to clone the repository.
- About **4 GB of free disk space** (container images include LibreOffice and Tesseract, which aren't tiny) and a few minutes for the first build.
- **`make`** is used for convenience throughout this guide, but it's optional. It's preinstalled on Mac/Linux; **plain Windows PowerShell does not have it** (`make : The term 'make' is not recognized...`). If you're on Windows without WSL, just skip installing it — every `make <target>` command below has the plain `docker compose ...` command it runs written next to it, and you can run that instead. (If you'd rather have `make` itself, install it via `choco install make` with Chocolatey, or use WSL2, where it's available out of the box.)

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

- `JWT_SECRET` — replace `change-me-to-a-long-random-string` with a long random string. This signs login sessions; leaving it at the default means anyone can forge a login. The backend will print a warning in its logs on startup if you forget.
  - Mac/Linux: `openssl rand -hex 32`
  - Windows PowerShell: `-join ((48..57)+(97..102)|Get-Random -Count 32|%{[char]$_})`
  - Or just mash the keyboard for 40+ random characters — it doesn't need to be memorable, only unpredictable.
- `POSTGRES_PASSWORD` — replace `change-me` with something real.

## 4. Start everything

```bash
make up
# or, without make:
docker compose up -d --build
```

The first run downloads base images and builds the backend/frontend containers, which can take several minutes — that's normal. Database migrations run automatically too: a one-off `migrate` service applies the schema before `backend`/`worker` are allowed to start, so there's no separate migration step to remember, on this run or any future one after pulling new code.

Once it finishes, check that everything is actually running:

```bash
docker compose ps
```

You should see `postgres`, `redis`, `backend`, `worker`, and `frontend` all showing `Up` (postgres/redis as `Up (healthy)`), plus a `migrate` container that ran once and shows `Exited (0)` — that's expected, it's not meant to keep running. If `backend`/`worker` never leave `Created`, check `docker compose logs migrate` — it means the migration itself failed.

## 5. Open the app

Go to **http://localhost** in your browser. Click **"Register"**, create your account, and log in.

## 6. Your first case, start to finish

Everything in this app is scoped to a **case**. Whoever creates a case automatically becomes its **admin**. Opening a case drops you into a guided, numbered set of steps — they stay visible and usable the whole time (nothing locks once you move on, so you can always go back and add another custodian or PST later).

1. **Create a case** — after logging in you land on the case list. Click **"New case"**, give it a name, submit.
2. **Step 1 — Custodians & import** — add every custodian whose mailbox you're reviewing (name + optional email), then import as many PSTs as you need against them. Each import shows a live progress bar through extracting → parsing → dedup → rendering, including a real per-document count once rendering starts (`Rendering documents: 45 / 120`). This all runs in the `worker` container, so you can navigate away and come back.
3. **Step 2 — De-duplication & rendering** — a read-only summary that fills in automatically as imports complete: total documents by type, how many are unique vs. duplicates (duplicates are excluded from review automatically), and how many have finished rendering to PDF for viewing.
4. **Step 3 — Add documents to review** — click **"Add all documents to a review set"** to put every unique document into a new or existing review set in one action, or **"Hand-pick documents instead"** to filter/search the full document list (by type, keyword — including OCR'd text from scanned attachments — custodian, thread) and add a specific subset.
5. **Step 4 — Review** — open a review set to tag documents, redact anything sensitive (drag rectangles on the rendered PDF — saves immediately, nothing is permanently altered until export), and set each document's review status (unreviewed / in review / reviewed / flagged).
6. **Export** — from step 4, click **"Export a review set →"**, pick the set, choose **Bates-numbered production set** (one PDF per document + a Bates log CSV, zipped) or **single combined PDF**, optionally set a Bates prefix/start number, and submit. Redactions are burned in (genuinely removed, not just covered) at this point. Download once the job shows **completed**.
7. **Audit log** — as an admin, click **"Audit log"** at the top of the case to see a record of every import, tag, redaction, review-set, and export action taken on it, with who did it.

To work with others, have them register their own account (step 5 above), then as the case admin click **"Members"** on the case page and add them by email address with a role (`admin` / `reviewer` / `viewer`).

## Everyday commands

| With `make` | Without `make` |
|---|---|
| `make logs` | `docker compose logs -f` |
| `make down` | `docker compose down` |
| `make up` | `docker compose up -d --build` |
| `make update` | `./update.sh` |

(all preserve your data, which lives in Docker volumes, not in the containers themselves). To watch just one service, e.g. while debugging an import: `docker compose logs -f worker`.

**To update a self-hosted install** (one you set up with `install.sh`, or any production-style deployment using `docker-compose.yml` on its own): run `update.sh` from the repo directory (`sudo ./update.sh`, or `make update`) — it pulls the latest code, rebuilds only what changed, and restarts, all without touching your `.env`/secrets or your existing data volumes. It also warns you if a new setting has shown up in `.env.example` that isn't in your `.env` yet. There's no separate migrate command to remember — new database migrations run automatically as part of the restart.

**If you're just trying it out locally** with `docker-compose.override.yml` in play (the default when you follow step 4 above), a plain update is simpler since there's no production build to preserve:

```bash
git pull
make up          # or: docker compose up -d --build
```

To wipe everything and start completely fresh (**this deletes all imported data**):

```bash
make down    # or: docker compose down
docker volume ls                      # find your volume names, prefix varies by folder name
docker volume rm <prefix>_pgdata <prefix>_redis_data <prefix>_case_storage
make up
```

## Troubleshooting

- **`docker compose ps` shows `backend`/`worker` stuck in `Created` and never starting** — the automatic `migrate` step failed. Check `docker compose logs migrate` for the actual Alembic error.
- **`make : The term 'make' is not recognized...`** (Windows PowerShell) — expected, `make` isn't installed by default on Windows. Use the plain `docker compose ...` command shown next to each `make` command in this guide instead (or install `make`, see step 1).
- **The build fails partway through an `apt-get install` step** (e.g. `Package '...' has no installation candidate`) — this means an upstream Debian package the Dockerfile depends on was renamed or removed since the image was last tested; `git pull` to get the latest `Dockerfile` fix, or open an issue if it's still failing on the current `main`.
- **Port already in use, or Docker reports `Bind for 0.0.0.0:80 failed: port is already allocated`** — most likely something else on your machine is genuinely using that port. Set `FRONTEND_PORT=<some other port>` (e.g. `8080`) in `.env` and re-run `docker compose up -d`. `install.sh` also retries automatically through `8080`/`8888`/`8081` if this happens. If you're running `docker compose up` directly rather than through `install.sh`, make sure you're not unintentionally loading `docker-compose.override.yml` in a production deployment (it's dev-only — it builds the Vite dev server instead of the production nginx image); run `docker compose -f docker-compose.yml up -d --build` to be explicit about excluding it.
- **Login says "Invalid email or password" right after registering** — double check you registered against `http://localhost:8000` (the backend, not the frontend on port 80), and that email/password match exactly.
- **PST import job stays "pending" forever** — the `worker` container may not be running; check `docker compose ps` and `docker compose logs worker`.
- **A warning about `JWT_SECRET` in the logs** — expected if you skipped changing it in step 3; harmless for local trying-out, but fix it before exposing this beyond your own machine.
- **On Windows**, make sure Docker Desktop is set to use the WSL2 backend. If you cloned the repo into a regular Windows folder (e.g. under `Downloads` or `OneDrive`) rather than the WSL filesystem, Docker Desktop's file sharing still works — builds will just be slower than cloning inside WSL (`\\wsl$\...`). OneDrive-synced folders in particular can occasionally cause file-lock errors during `docker compose build`; if you hit one, moving the folder outside OneDrive resolves it.

## Advanced

### Architecture

| Layer | Tech |
|---|---|
| Backend API | FastAPI (async), SQLAlchemy 2.0 + asyncpg, Alembic migrations |
| Background jobs | Celery + Redis (PST ingestion, rendering, export) |
| Database | PostgreSQL 16 |
| Auth | `fastapi-users`, cookie-based JWT sessions, per-case RBAC, optional OIDC/SSO login |
| PST parsing | `libpff-python`, with `readpst` (`pst-utils`) as a fallback/contacts exporter |
| PDF pipeline | PyMuPDF (`fitz`) for redaction burn-in, Bates stamping, and merging; WeasyPrint for email→PDF; LibreOffice headless for Office docs; Pillow/img2pdf for images |
| OCR | Tesseract via `pytesseract` |
| Frontend | React + TypeScript + Vite, Mantine UI, TanStack Query, React Router, `react-pdf` |

Case files (uploads, staged extraction, native attachments, rendered PDFs, exports) live on a Docker volume mounted only into the `backend` and `worker` containers — never served as static content. All document access goes through authenticated, case-membership-checked API endpoints.

Roles: `admin` (manage case/members/import/export), `reviewer` (tag/redact/review), `viewer` (read-only) — all per-case. Separately, a user can be a system-wide **superuser**, which grants access to `/admin` (user management and system settings) but no automatic access to any case's documents.

### Admin UI and OIDC login

Any superuser can reach `/admin` (linked from the top of the case list once signed in) for two things:

- **Users** — list every account, promote/demote superuser status, and activate/deactivate accounts (you can't lock yourself out — deactivating or demoting your own account is blocked).
- **System settings** — the `ENABLE_API_DOCS`/`COOKIE_SECURE` env vars' live values (see above), plus OIDC login configuration: issuer URL, client ID, client secret, and the button label shown on the login page. None of this requires editing `.env` or restarting the stack — the client secret is encrypted at rest with `SECRET_ENCRYPTION_KEY` and never sent back to the browser after saving.

To enable OIDC: set `SECRET_ENCRYPTION_KEY` in `.env` (see above) and restart once, then from `/admin` fill in your identity provider's issuer URL (its OpenID discovery document must be reachable at `<issuer>/.well-known/openid-configuration`), client ID, and client secret, and register `http://<your-host>/api/auth/oidc/callback` as the redirect URI with that provider (the Admin UI displays the exact value to copy). Turning on "Enable OIDC login" is blocked until all three fields are saved. First-time sign-in via OIDC auto-creates a local account from the provider's email — new accounts start as a regular (non-superuser) user on no cases, same as registering directly.

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

| With `make` | Without `make` |
|---|---|
| `make build` | `docker compose build` (build without starting) |
| `make test` | `docker compose exec backend pytest` |
| `make lint` | `docker compose exec backend ruff check app` |
| `make fmt` | `docker compose exec backend ruff format app` |
| `make migrate` | `docker compose run --rm migrate` (manually re-run migrations without restarting everything else — not needed in normal use, since `up` already does this automatically) |
| `make makemigration m="message"` | `docker compose exec backend alembic revision --autogenerate -m "message"` |
| `make shell-backend` | `docker compose exec backend bash` |

`docker-compose.override.yml` is applied automatically in dev — it bind-mounts source into the containers and runs `uvicorn --reload` / `vite dev` for live reload. For a production-style build, run with `docker compose -f docker-compose.yml up -d --build` to skip the override.

### All environment variables

See `.env.example` for the full list. Beyond `JWT_SECRET` and `POSTGRES_PASSWORD` (covered in step 3):

- `STORAGE_ROOT` — where case files live inside the `backend`/`worker` containers (defaults to the `case_storage` volume at `/data`); not something you need to change for a Docker setup.
- `COOKIE_SECURE` — set to `true` once served over HTTPS. This is only the *initial* value — a superuser can flip it from the Admin UI (`/admin`) afterward, but that change takes a backend restart to apply, same as this env var would.
- `BACKEND_CORS_ORIGINS` — origins allowed to call the API; adjust if you serve the frontend from somewhere other than `localhost`. Also doubles as the redirect target after OIDC login, if configured.
- `ENABLE_API_DOCS` — set to `true` to turn the Swagger UI (`/docs`) and OpenAPI schema back on; off by default everywhere except the dev override. Also the initial value for the same Admin UI toggle — that one applies live, no restart needed.
- `SECRET_ENCRYPTION_KEY` — only needed if you configure OIDC login (see below); encrypts the OIDC client secret at rest. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

### Deploying with Portainer

Requires Portainer 2.19+ (bundles Docker Compose v2, which understands the `service_completed_successfully`/`service_healthy` startup ordering this stack relies on for automatic migrations — an older Portainer bundling Compose v1 will deploy the stack but won't sequence `migrate` → `backend`/`worker` correctly).

`docker-compose.yml` is a self-contained stack definition — it doesn't require a `.env` file to exist (every variable has a working default baked in), and every long-running service has `restart: unless-stopped` so the stack comes back up on its own after a host reboot or Portainer restart. That makes it deployable as a Portainer stack with no extra setup beyond what's below.

1. In Portainer, go to **Stacks → Add stack**.
2. Choose **Repository** as the build method, point it at this repo's URL, and set **Compose path** to `docker-compose.yml` — leave `docker-compose.override.yml` out entirely; that file is dev-only (bind mounts, hot reload) and isn't meant for a deployed stack.
3. Under **Environment variables**, add at minimum:
   - `JWT_SECRET` — a long random string (see step 3 above for how to generate one). Portainer stacks don't get a `.env` file from the repo (it's gitignored on purpose, since it's usually where real secrets end up), so this **must** be set here or the stack falls back to the insecure placeholder.
   - `POSTGRES_PASSWORD` — likewise.
   - `BACKEND_CORS_ORIGINS` — set this to wherever the frontend will actually be reached from (e.g. `https://review.yourdomain.com`), not `localhost` — cookie-based login will fail with a CORS error otherwise.
   - `COOKIE_SECURE=true` — once you're serving this behind HTTPS (e.g. via a reverse proxy in front of Portainer's managed containers), so session cookies aren't sent over plain HTTP.
4. Deploy the stack. Postgres/Redis start and become healthy, the one-off `migrate` service applies the schema, then `backend`/`worker`/`frontend` start — the same automatic sequence described in step 4 above, no manual migration step needed here either.
5. The frontend container listens on port `80` internally, published to host port `80` by default (`ports: ["80:80"]` in `docker-compose.yml`); the backend's API is published on `8000`. Put a reverse proxy (Traefik, nginx, Portainer's own or a separate one) in front of both if you want a single public hostname/HTTPS termination — this repo doesn't include one, since that setup is specific to your infrastructure.
6. To pick up new code later: pull the latest image build in Portainer (or use its **GitOps updates** / webhook feature to redeploy automatically on push) — migrations still apply automatically on the next start, same as local Docker Compose.

### Using Dockge or another stack manager that wants a real `.env` file

Unlike Portainer's own UI-managed environment variables, tools like Dockge expect a literal `.env` file sitting next to the compose file, and manage that file directly. That already works here with no extra setup: `docker-compose.yml` doesn't hard-depend on `.env` existing (see above), but it *does* pick one up automatically the normal Docker Compose way if present, for every setting. Point the tool at this repo's `docker-compose.yml`, give it a `.env` based on `.env.example` (the [Quick install script](#quick-install-ubuntu-server) above generates exactly this, at `/opt/DockerPSTReview/.env`, if you'd rather not write one by hand), and manage it there from then on.

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

The interactive Swagger UI (`/docs`) and raw OpenAPI schema (`/openapi.json`) are **disabled by default** — once there's a real Register page, there's no reason to leave every endpoint publicly browsable and callable. The dev override (`docker-compose.override.yml`) re-enables it automatically for local work; for anything else, either set `ENABLE_API_DOCS=true` in `.env` or flip it live from `/admin` as a superuser (no restart needed either way). Endpoints are organized around a case (`/api/cases/{case_id}/...`): custodians, import-jobs, documents, threads, tags, review-sets, redactions, export-jobs, audit-logs, `stats`, plus case membership management, admin, and `fastapi-users`' auth routes.

### Known limitations

- Calendar item detailed fields (start/end/location/attendees) depend on PST-specific MAPI named-property resolution that isn't implemented yet — calendar items import and are reviewable, but only with reduced metadata fidelity.
- No S3-compatible object storage backend yet — case files live on a local Docker volume, which is fine for a single self-hosted server but doesn't horizontally scale. Swapping this out is isolated to `backend/app/services/storage.py`.
