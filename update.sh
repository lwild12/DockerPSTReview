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

set_env_var() {
  # set_env_var KEY VALUE -- updates KEY in .env in place, or appends it
  # if it isn't there yet (older .env files predate some settings).
  if grep -q "^$1=" .env; then
    sed -i "s#^$1=.*#$1=$2#" .env
  else
    echo "$1=$2" >>.env
  fi
}

detect_cpu_cores() {
  nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2
}

# ask_number PROMPT DEFAULT -- prints DEFAULT unchanged when there's no
# real terminal to read from, the prompt times out unanswered, or the
# answer isn't a positive integer. Reads from /dev/tty rather than stdin
# so this still works under `curl ... | sudo bash`.
ask_number() {
  local prompt="$1" default="$2" answer=""
  if [ -r /dev/tty ]; then
    read -r -t 60 -p "$prompt [${default}]: " answer </dev/tty 2>/dev/null || answer=""
  fi
  if [[ "$answer" =~ ^[0-9]+$ ]] && [ "$answer" -ge 1 ]; then
    echo "$answer"
  else
    echo "$default"
  fi
}

# RENDER_CONCURRENCY/PARSE_CONCURRENCY predate this update on older
# installs -- ask for them once here instead of silently applying a
# default, since they're worth sizing to the machine's CPU count.
if ! grep -q '^RENDER_CONCURRENCY=' .env || ! grep -q '^PARSE_CONCURRENCY=' .env; then
  CPU_CORES="$(detect_cpu_cores)"
  RENDER_DEFAULT=$(( CPU_CORES < 4 ? CPU_CORES : 4 ))
  [ "$RENDER_DEFAULT" -lt 1 ] && RENDER_DEFAULT=1
  PARSE_DEFAULT=$(( CPU_CORES * 2 < 8 ? CPU_CORES * 2 : 8 ))
  [ "$PARSE_DEFAULT" -lt 1 ] && PARSE_DEFAULT=1
  echo
  log "This update adds parallel PST import processing, not yet configured in your .env (detected ${CPU_CORES} CPU core(s)). Press Enter to accept the suggested defaults, or adjust later in .env."
  if ! grep -q '^RENDER_CONCURRENCY=' .env; then
    set_env_var RENDER_CONCURRENCY "$(ask_number "  Documents to render (PDF/OCR) at once per import" "$RENDER_DEFAULT")"
  fi
  if ! grep -q '^PARSE_CONCURRENCY=' .env; then
    set_env_var PARSE_CONCURRENCY "$(ask_number "  Documents to parse at once per import" "$PARSE_DEFAULT")"
  fi
fi

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
