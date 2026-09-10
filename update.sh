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
git fetch origin main

# The repo's GitHub-reported default branch has at times pointed at a
# feature branch instead of main, which a plain `git clone`/checkout with
# no explicit branch would have followed -- pin to main explicitly so an
# affected checkout self-heals here instead of quietly tracking the wrong
# branch on every update.
CURRENT_BRANCH="$(git symbolic-ref --short -q HEAD || echo "")"
if [ "$CURRENT_BRANCH" != "main" ]; then
  warn "This checkout is on branch '${CURRENT_BRANCH:-<detached HEAD>}', not 'main' -- switching to main."
  git checkout main 2>/dev/null || git checkout -B main origin/main
fi

git pull --ff-only origin main

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

detect_ram_mb() {
  if command -v free >/dev/null 2>&1; then
    free -m | awk '/^Mem:/{print $2}'
  elif [ -r /proc/meminfo ]; then
    awk '/^MemTotal:/{print int($2/1024)}' /proc/meminfo
  else
    echo 2048
  fi
}

# suggest_concurrency CPU_CORES RAM_MB CPU_CAP MB_PER_WORKER -- prints a
# suggested concurrency: bounded by CPU_CAP (never suggest more workers
# than makes sense for a single import job), and separately bounded by
# how many MB_PER_WORKER-sized workers fit in RAM after reserving 1GB for
# Postgres/Redis/the backend and frontend containers themselves. Whichever
# constraint is tighter wins, so a low-RAM box doesn't get a suggestion
# that risks OOM-killing the worker mid-import.
suggest_concurrency() {
  local cpu_cores="$1" ram_mb="$2" cpu_cap="$3" mb_per_worker="$4"
  local cpu_based=$(( cpu_cores < cpu_cap ? cpu_cores : cpu_cap ))
  local available_mb=$(( ram_mb - 1024 ))
  [ "$available_mb" -lt 512 ] && available_mb=512
  local ram_based=$(( available_mb / mb_per_worker ))
  local suggested=$(( cpu_based < ram_based ? cpu_based : ram_based ))
  [ "$suggested" -lt 1 ] && suggested=1
  echo "$suggested"
}

# ask_number PROMPT DEFAULT -- prints DEFAULT unchanged when there's no
# real terminal to read from (e.g. a remote command run without a pty),
# the prompt times out unanswered, or the answer isn't a positive integer.
# Reads from /dev/tty rather than stdin so this still works under
# `curl ... | sudo bash`.
#
# /dev/tty is usually world-readable even with no controlling terminal
# attached (`ssh host cmd` without -t, cloud-init, a CI runner), so `[ -r
# /dev/tty ]` alone can't tell interactive and non-interactive contexts
# apart -- this actually opens it and checks it's a real terminal instead.
# The prompt+default is also always printed on its own line up front,
# rather than relying on `read -p`'s inline, unterminated prompt, so a
# still-waiting read can't look identical to a hang behind a line-buffered
# terminal or log viewer.
#
# Under `sudo` (its default use_pty setting relays the previous prompt's
# Enter keypress back into the terminal asynchronously), a stray leftover
# newline -- or, it turns out, a whole duplicated answer -- can otherwise
# land right as the next read() starts and satisfy it instantly, silently
# feeding that prompt an answer the user never typed for it. _settle_tty
# waits for a real stretch of quiet (no draining resets the clock) rather
# than checking at one fixed point in time, but it's capped at MAX_WAIT --
# a resettable "wait for quiet" loop with no upper bound can itself hang
# indefinitely if anything keeps trickling in (a real report from an
# install that never got past this point), so this can never wait longer
# than that regardless of how busy the terminal looks.
_settle_tty() {
  local quiet_streak=0 junk="" start_s deadline_s
  start_s="$(date +%s)"
  deadline_s=$((start_s + 3))
  while [ "$quiet_streak" -lt 6 ] && [ "$(date +%s)" -lt "$deadline_s" ]; do
    if read -r -t 0.15 junk <&3 2>/dev/null; then
      quiet_streak=0
    else
      quiet_streak=$((quiet_streak + 1))
    fi
  done
}

ask_number() {
  local prompt="$1" default="$2" answer="" started_at="" elapsed_ms=""
  if { exec 3<>/dev/tty; } 2>/dev/null && [ -t 3 ]; then
    _settle_tty
    printf '%s [%s]: ' "$prompt" "$default" >&2
    started_at="$(date +%s%N)"
    read -r -t 60 answer <&3 2>/dev/null || answer=""
    echo >&2
    exec 3<&- 2>/dev/null || true
    elapsed_ms=$(( ($(date +%s%N) - started_at) / 1000000 ))
    [ "$elapsed_ms" -lt 150 ] && answer=""
  else
    printf '  (no interactive terminal detected -- using default %s for: %s)\n' \
      "$default" "$prompt" >&2
  fi
  if [[ "$answer" =~ ^[0-9]+$ ]] && [ "$answer" -ge 1 ]; then
    echo "$answer"
  else
    echo "$default"
  fi
}

# ask_two_numbers PROMPT DEFAULT1 DEFAULT2 -- like ask_number, but asks for
# both values with a single prompt/read instead of two back-to-back ones.
# That sidesteps the whole class of bug above at its root rather than
# continuing to patch around it: with only one read, there's no "next
# prompt" for stray relayed input to leak into. Prints "VALUE1 VALUE2".
ask_two_numbers() {
  local prompt="$1" default1="$2" default2="$3" line="" v1="" v2=""
  if { exec 3<>/dev/tty; } 2>/dev/null && [ -t 3 ]; then
    _settle_tty
    printf '%s [%s %s]: ' "$prompt" "$default1" "$default2" >&2
    read -r -t 60 line <&3 2>/dev/null || line=""
    echo >&2
    exec 3<&- 2>/dev/null || true
  else
    printf '  (no interactive terminal detected -- using defaults %s %s for: %s)\n' \
      "$default1" "$default2" "$prompt" >&2
  fi
  read -r v1 v2 <<<"$line"
  [[ "$v1" =~ ^[0-9]+$ ]] && [ "$v1" -ge 1 ] || v1="$default1"
  [[ "$v2" =~ ^[0-9]+$ ]] && [ "$v2" -ge 1 ] || v2="$default2"
  echo "$v1 $v2"
}

# RENDER_CONCURRENCY/PARSE_CONCURRENCY predate this update on older
# installs -- ask for them once here instead of silently applying a
# default, since they're worth sizing to the machine's CPU count.
if ! grep -q '^RENDER_CONCURRENCY=' .env || ! grep -q '^PARSE_CONCURRENCY=' .env; then
  CPU_CORES="$(detect_cpu_cores)"
  RAM_MB="$(detect_ram_mb)"
  RENDER_DEFAULT="$(suggest_concurrency "$CPU_CORES" "$RAM_MB" 4 400)"
  PARSE_DEFAULT="$(suggest_concurrency "$CPU_CORES" "$RAM_MB" 8 150)"
  echo
  log "This update adds parallel PST import processing, not yet configured in your .env (detected ${CPU_CORES} CPU core(s), ${RAM_MB}MB RAM). Press Enter to accept the suggested defaults, or adjust later in .env."
  if ! grep -q '^RENDER_CONCURRENCY=' .env && ! grep -q '^PARSE_CONCURRENCY=' .env; then
    # Common case: neither is set yet -- ask for both in one combined
    # prompt (see ask_two_numbers above for why that's preferred over two
    # back-to-back single-value prompts).
    read -r RENDER_CONCURRENCY PARSE_CONCURRENCY <<<"$(ask_two_numbers \
      "  Documents to render and parse at once per import (render parse)" \
      "$RENDER_DEFAULT" "$PARSE_DEFAULT")"
    set_env_var RENDER_CONCURRENCY "$RENDER_CONCURRENCY"
    set_env_var PARSE_CONCURRENCY "$PARSE_CONCURRENCY"
  else
    # Rare case: one already exists from a partial/older setup -- only one
    # prompt is needed here, so there's no back-to-back risk to combine away.
    if ! grep -q '^RENDER_CONCURRENCY=' .env; then
      set_env_var RENDER_CONCURRENCY "$(ask_number "  Documents to render (PDF/OCR) at once per import" "$RENDER_DEFAULT")"
    fi
    if ! grep -q '^PARSE_CONCURRENCY=' .env; then
      set_env_var PARSE_CONCURRENCY "$(ask_number "  Documents to parse at once per import" "$PARSE_DEFAULT")"
    fi
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

# docker-compose.yml bind-mounts this file into the backend/worker
# containers for Ollama request/response logging -- a bind mount of a
# path that doesn't exist yet on the host gets created as a directory
# instead of a file, so touch it into existence first (a no-op if it's
# already there from a previous run).
touch ollama.log

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
