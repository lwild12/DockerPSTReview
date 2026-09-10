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
    git -C "$INSTALL_DIR" fetch origin main
    # The repo's GitHub-reported default branch has at times pointed at a
    # feature branch instead of main, which a plain clone/checkout with no
    # explicit branch would have followed -- pin to main explicitly so an
    # affected checkout self-heals here instead of quietly tracking the
    # wrong branch on every re-run.
    CURRENT_BRANCH="$(git -C "$INSTALL_DIR" symbolic-ref --short -q HEAD || echo "")"
    if [ "$CURRENT_BRANCH" != "main" ]; then
      warn "This checkout is on branch '${CURRENT_BRANCH:-<detached HEAD>}', not 'main' -- switching to main."
      git -C "$INSTALL_DIR" checkout main 2>/dev/null || git -C "$INSTALL_DIR" checkout -B main origin/main
    fi
    git -C "$INSTALL_DIR" pull --ff-only origin main
  else
    log "Cloning $REPO_URL into $INSTALL_DIR..."
    git clone --branch main "$REPO_URL" "$INSTALL_DIR"
  fi
  REPO_DIR="$INSTALL_DIR"
fi
cd "$REPO_DIR"

# docker-compose.override.yml is dev-only (bind-mounts source, runs the Vite
# dev server instead of the production nginx build) -- exclude it here so a
# production install never picks it up just because it happens to sit next
# to docker-compose.yml in the same directory.
export COMPOSE_FILE=docker-compose.yml

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
# real terminal to read from (e.g. unattended provisioning, or a remote
# command run without a pty), the prompt times out unanswered, or the
# answer isn't a positive integer. Reads from /dev/tty rather than stdin
# so this still works under `curl ... | sudo bash`, where stdin is the
# piped script itself.
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

  CPU_CORES="$(detect_cpu_cores)"
  RAM_MB="$(detect_ram_mb)"
  RENDER_DEFAULT="$(suggest_concurrency "$CPU_CORES" "$RAM_MB" 4 400)"
  PARSE_DEFAULT="$(suggest_concurrency "$CPU_CORES" "$RAM_MB" 8 150)"
  echo
  log "PST imports process multiple documents in parallel (detected ${CPU_CORES} CPU core(s), ${RAM_MB}MB RAM on this machine). Press Enter to accept the suggested defaults, or adjust later in .env."
  read -r RENDER_CONCURRENCY PARSE_CONCURRENCY <<<"$(ask_two_numbers \
    "  Documents to render and parse at once per import (render parse)" \
    "$RENDER_DEFAULT" "$PARSE_DEFAULT")"
  set_env_var RENDER_CONCURRENCY "$RENDER_CONCURRENCY"
  set_env_var PARSE_CONCURRENCY "$PARSE_CONCURRENCY"

  chmod 600 .env
  log "Wrote $REPO_DIR/.env -- back this up, it's the only copy of your generated secrets."
fi

# docker-compose.yml bind-mounts this file into the backend/worker
# containers for Ollama request/response logging -- a bind mount of a
# path that doesn't exist yet on the host gets created as a directory
# instead of a file, so touch it into existence first.
touch ollama.log

UP_LOG="$(mktemp)"
trap 'rm -f "$UP_LOG"' EXIT

try_up() {
  # Stream to the terminal live (a first build can run for several
  # minutes -- silent output here is indistinguishable from a hang) while
  # still capturing it to UP_LOG for the port-conflict pattern match below.
  docker compose up -d --build 2>&1 | tee "$UP_LOG"
}

is_port_alloc_failure() {
  # Deliberately a plain substring match, not an address-specific regex --
  # Docker prints this for IPv4 (0.0.0.0:<port>), IPv6 (:::<port>), and
  # possibly other host bindings, and getting the address format wrong here
  # once already meant this check silently never matched.
  grep -q "port is already allocated" "$UP_LOG"
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
      fi
    fi
    if [ "$STARTED" -ne 1 ]; then
      err "Could not start the frontend container even after retries and a Docker daemon restart."
      err "Free up one of the tried ports (80, 8080, 8888, 8081), or set FRONTEND_PORT in .env yourself, then re-run: docker compose -f docker-compose.yml up -d"
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

  To pick up future updates without a full reset, run:
    cd ${REPO_DIR} && sudo ./update.sh
----------------------------------------------------------------------
EOF

if [ "$INVOKING_USER" != "root" ] && ! id -nG "$INVOKING_USER" 2>/dev/null | grep -qw docker; then
  warn "Log out and back in (or run 'newgrp docker') so $INVOKING_USER can run docker/docker compose without sudo."
fi
