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
FRONTEND_PORT=8080
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

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -z "$SERVER_IP" ]; then
  SERVER_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"
fi
SERVER_IP="${SERVER_IP:-localhost}"

if [ -f .env ]; then
  log ".env already exists -- leaving it untouched (re-generating secrets after Postgres has already initialized would break access to your existing data)."
else
  log "Generating .env with fresh random secrets..."
  cp .env.example .env
  JWT_SECRET_VALUE="$(openssl rand -hex 32)"
  POSTGRES_PASSWORD_VALUE="$(openssl rand -hex 20)"
  sed -i "s#^JWT_SECRET=.*#JWT_SECRET=${JWT_SECRET_VALUE}#" .env
  sed -i "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VALUE}#" .env
  sed -i "s#^BACKEND_CORS_ORIGINS=.*#BACKEND_CORS_ORIGINS=http://localhost:${FRONTEND_PORT},http://${SERVER_IP}:${FRONTEND_PORT}#" .env
  chmod 600 .env
  log "Wrote $REPO_DIR/.env -- back this up, it's the only copy of your generated secrets."
fi

log "Building and starting the stack (this can take several minutes on first run)..."
docker compose up -d --build

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

  App:        http://${SERVER_IP}:${FRONTEND_PORT}
  API docs:   http://${SERVER_IP}:${BACKEND_PORT}/docs

  No account exists yet. Create the first one by opening the API docs
  link above, expanding POST /api/auth/register, "Try it out", and
  submitting your email/password -- then log in at the App link.
  (Full walkthrough: README.md, steps 5-6.)

  Secrets live in: ${REPO_DIR}/.env  (back this up)
----------------------------------------------------------------------
EOF

if [ "$INVOKING_USER" != "root" ] && ! id -nG "$INVOKING_USER" 2>/dev/null | grep -qw docker; then
  warn "Log out and back in (or run 'newgrp docker') so $INVOKING_USER can run docker/docker compose without sudo."
fi
