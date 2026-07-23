#!/usr/bin/env bash
# Pulls the latest code and rebuilds/restarts only what changed -- no full
# reset, your .env/secrets are untouched, and existing data volumes
# (Postgres, case storage) are left alone.
#
# Usage (from an existing install.sh checkout):
#   sudo ./update.sh
#
# Usage (one-liner, matches install.sh):
#   curl -fsSL https://raw.githubusercontent.com/lwild12/DockerPSTReview/main/update.sh | sudo bash

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/DockerPSTReview}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

log()  { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31mXX\033[0m %s\n' "$1" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -d "$SCRIPT_DIR/backend" ]; then
  REPO_DIR="$SCRIPT_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
  REPO_DIR="$INSTALL_DIR"
else
  err "Couldn't find an existing checkout (looked in the script's own directory and $INSTALL_DIR)."
  err "Run this from inside the repo, or set INSTALL_DIR to point at your existing install."
  exit 1
fi
cd "$REPO_DIR"
log "Updating checkout at $REPO_DIR..."

if [ ! -f .env ]; then
  err "No .env found here -- this doesn't look like an existing install. Use install.sh for a first-time setup."
  exit 1
fi

# Production only, never the dev override (docker-compose.override.yml
# bind-mounts source and runs the Vite dev server instead of the built
# nginx image -- picking it up here would silently swap out the running
# production build).
export COMPOSE_FILE=docker-compose.yml

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  warn "You have uncommitted local changes to tracked files in $REPO_DIR."
  warn "git pull will fail below if they conflict with the update -- 'git stash' first if that happens."
fi

log "Fetching latest code..."
git fetch origin
git pull --ff-only

if [ -f .env.example ]; then
  NEW_KEYS="$(comm -23 \
    <(grep -oE '^[A-Z_]+' .env.example | sort -u) \
    <(grep -oE '^[A-Z_]+' .env | sort -u) || true)"
  if [ -n "$NEW_KEYS" ]; then
    warn "New settings are available in .env.example that aren't in your .env (safe defaults apply until you add them):"
    while IFS= read -r key; do warn "  - $key"; done <<<"$NEW_KEYS"
  fi
fi

log "Rebuilding changed images..."
docker compose build

log "Recreating changed containers (services that didn't change, and all your data, are left alone)..."
docker compose up -d

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
  log "Update complete -- backend is healthy."
else
  warn "Backend didn't respond within two minutes -- check: docker compose logs backend"
fi
