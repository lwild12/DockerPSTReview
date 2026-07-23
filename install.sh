#!/usr/bin/env bash
# Installs Docker (if needed), clones/updates this repo, generates a real
# .env with random secrets, and brings the stack up -- ready to use.
#
# Usage (from an already-cloned checkout):
#   sudo ./install.sh
#
# Usage (one-liner on a fresh Ubuntu Server, no checkout yet):
#   curl -fsSL https://raw.githubusercontent.com/lwild12/DockerPSTReview/main/install.sh | sudo bash
#
# Safe to re-run: an existing .env is never overwritten (regenerating
# POSTGRES_PASSWORD after Postgres has already initialized its data
# directory with the old one would lock you out of your own database),
# and `docker compose up -d --build` is idempotent.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/lwild12/DockerPSTReview.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/DockerPSTReview}"
FRONTEND_PORT=80
BACKEND_PORT=8000

log()  { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31mXX\033[0m %s\n' "$1" >&2; }

if [ "$(id -u)" -ne 0 ]; then
  err "This script installs system packages and Docker, so it needs root."
  err "Re-run it as: sudo bash install.sh"
  exit 1
fi

if [ -r /etc/os-release ]; then
  . /etc/os-release
  if [ "${ID:-}" != "ubuntu" ] && [ "${ID_LIKE:-}" != "debian" ] && [ "${ID:-}" != "debian" ]; then
    warn "This script is written for Ubuntu/Debian; detected '${PRETTY_NAME:-unknown}'. Continuing anyway, but apt-based steps may fail."
  fi
fi

INVOKING_USER="${SUDO_USER:-root}"

log "Installing base packages (git, curl, openssl, ca-certificates)..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl git openssl >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found -- installing via Docker's official install script..."
  curl -fsSL https://get.docker.com | sh
else
  log "Docker already installed ($(docker --version))."
fi

if ! docker compose version >/dev/null 2>&1; then
  err "docker compose (v2 plugin) isn't available even after the Docker install step."
  err "Install it manually (docker-compose-plugin package) and re-run this script."
  exit 1
fi

if [ "$INVOKING_USER" != "root" ] && ! id -nG "$INVOKING_USER" | grep -qw docker; then
  log "Adding $INVOKING_USER to the docker group (takes effect after your next login)..."
  usermod -aG docker "$INVOKING_USER"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -d "$SCRIPT_DIR/backend" ]; then
  REPO_DIR="$SCRIPT_DIR"
  log "Running from an existing checkout at $REPO_DIR."
else
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Repo already present at $INSTALL_DIR -- pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
  else
    log "Cloning $REPO_URL into $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  REPO_DIR="$INSTALL_DIR"
fi
cd "$REPO_DIR"

# A prior run may have already fallen back to a non-80 port (see the
# port-retry logic below) -- honor that instead of retrying 80 forever.
if [ -f .env ] && grep -q '^FRONTEND_PORT=' .env; then
  FRONTEND_PORT="$(grep '^FRONTEND_PORT=' .env | tail -1 | cut -d= -f2)"
fi

set_env_var() {
  # set_env_var KEY VALUE -- updates KEY in .env in place, or appends it
  # if it isn't there yet (older .env files predate some settings).
  if grep -q "^$1=" .env; then
    sed -i "s#^$1=.*#$1=$2#" .env
  else
    echo "$1=$2" >>.env
  fi
}

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -z "$SERVER_IP" ]; then
  SERVER_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"
fi
SERVER_IP="${SERVER_IP:-localhost}"

# Browsers omit the port from the Origin header for the scheme's default
# port (80 for http), so an exact-match CORS allowlist has to match that.
origin_for() {
  if [ "$FRONTEND_PORT" = "80" ]; then
    echo "http://$1"
  else
    echo "http://$1:${FRONTEND_PORT}"
  fi
}
APP_URL="$(origin_for "$SERVER_IP")"

if [ -f .env ]; then
  log ".env already exists -- leaving it untouched (re-generating secrets after Postgres has already initialized would break access to your existing data)."
else
  log "Generating .env with fresh random secrets..."
  cp .env.example .env
  JWT_SECRET_VALUE="$(openssl rand -hex 32)"
  POSTGRES_PASSWORD_VALUE="$(openssl rand -hex 20)"
  set_env_var JWT_SECRET "${JWT_SECRET_VALUE}"
  set_env_var POSTGRES_PASSWORD "${POSTGRES_PASSWORD_VALUE}"
  set_env_var FRONTEND_PORT "${FRONTEND_PORT}"
  set_env_var BACKEND_CORS_ORIGINS "$(origin_for localhost),${APP_URL}"
  chmod 600 .env
  log "Wrote $REPO_DIR/.env -- back this up, it's the only copy of your generated secrets."
fi

UP_LOG="$(mktemp)"
trap 'rm -f "$UP_LOG"' EXIT

try_up() {
  docker compose up -d --build >"$UP_LOG" 2>&1
}

is_port_alloc_failure() {
  # Matches both "Bind for 0.0.0.0:<port>" and "Bind for :::<port>" (IPv6).
  grep -qE "Bind for (0\.0\.0\.0|:::)[0-9]+ failed: port is already allocated" "$UP_LOG"
}

# Docker's internal port allocator (separate from the OS socket layer) can
# briefly report a port as taken right after a failed attempt, before its
# own async container/endpoint cleanup has settled -- give it a moment and
# a clean container before trying again.
settle_frontend() {
  docker compose rm -sf frontend >/dev/null 2>&1 || true
  sleep 5
}

log "Building and starting the stack (this can take several minutes on first run)..."
if ! try_up; then
  cat "$UP_LOG"
  if is_port_alloc_failure; then
    warn "Port ${FRONTEND_PORT} was reported as already allocated. This is often Docker's port allocator getting out of sync rather than a real conflict -- retrying."
    STARTED=0
    for candidate in "$FRONTEND_PORT" 8080 8888 8081; do
      settle_frontend
      FRONTEND_PORT="$candidate"
      APP_URL="$(origin_for "$SERVER_IP")"
      set_env_var FRONTEND_PORT "${FRONTEND_PORT}"
      set_env_var BACKEND_CORS_ORIGINS "$(origin_for localhost),${APP_URL}"
      log "Trying port ${FRONTEND_PORT}..."
      if try_up; then
        log "Stack started successfully on port ${FRONTEND_PORT}."
        STARTED=1
        break
      fi
      cat "$UP_LOG"
    done
    if [ "$STARTED" -ne 1 ] && command -v systemctl >/dev/null 2>&1; then
      warn "Still failing -- restarting the Docker daemon to clear its port allocator state, then trying once more..."
      systemctl restart docker
      for _ in $(seq 1 15); do
        docker info >/dev/null 2>&1 && break
        sleep 1
      done
      settle_frontend
      if try_up; then
        log "Stack started successfully on port ${FRONTEND_PORT} after a Docker daemon restart."
        STARTED=1
      else
        cat "$UP_LOG"
      fi
    fi
    if [ "$STARTED" -ne 1 ]; then
      err "Could not start the frontend container even after retries and a Docker daemon restart."
      err "Free up one of the tried ports (80, 8080, 8888, 8081), or set FRONTEND_PORT in .env yourself, then re-run: docker compose up -d"
      exit 1
    fi
  else
    err "docker compose up failed -- see the output above for details."
    exit 1
  fi
fi

log "Waiting for the backend to become healthy..."
READY=0
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${BACKEND_PORT}/healthz" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

echo
if [ "$READY" -eq 1 ]; then
  log "Stack is up and healthy."
else
  warn "Backend didn't respond within two minutes -- it may still be starting (LibreOffice/Tesseract images are large)."
  warn "Check progress with: docker compose -f \"$REPO_DIR/docker-compose.yml\" ps  /  logs"
fi

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  warn "ufw is active. If you need to reach this from another machine, allow the ports:"
  warn "  sudo ufw allow ${FRONTEND_PORT}/tcp"
  warn "  sudo ufw allow ${BACKEND_PORT}/tcp"
fi

cat <<EOF

----------------------------------------------------------------------
  PST Document Review is running.

  App:        ${APP_URL}

  No account exists yet. Create the first one at ${APP_URL}/register,
  then log in. (Full walkthrough: README.md, steps 5-6.)

  Secrets live in: ${REPO_DIR}/.env  (back this up)
----------------------------------------------------------------------
EOF

if [ "$INVOKING_USER" != "root" ] && ! id -nG "$INVOKING_USER" 2>/dev/null | grep -qw docker; then
  warn "Log out and back in (or run 'newgrp docker') so $INVOKING_USER can run docker/docker compose without sudo."
fi
