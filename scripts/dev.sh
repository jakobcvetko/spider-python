#!/usr/bin/env bash
# Run backend, frontend, and scraper concurrently with prefixed log output.
# Used by `make dev`. Ctrl+C (or SIGTERM) stops everything cleanly,
# including grandchildren (uvicorn's reload worker, vite, etc.).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

prefix() {
  local label="$1"
  awk -v lbl="$label" '{print "[" lbl "] " $0; fflush()}'
}

# Recursively kill a pid and all of its descendants with the given signal.
kill_tree() {
  local pid=$1
  local sig=$2
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child" "$sig"
  done
  kill -"$sig" "$pid" 2>/dev/null || true
}

PIDS=()

cleanup() {
  trap '' SIGINT SIGTERM EXIT  # prevent re-entry
  echo
  echo "==> Stopping all processes..."
  for pid in "${PIDS[@]}"; do
    kill_tree "$pid" TERM
  done
  # give them a moment to shut down gracefully
  sleep 1
  for pid in "${PIDS[@]}"; do
    kill_tree "$pid" KILL
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "==> Starting backend (:8000), frontend (:5173), and scraper..."
echo "==> Press Ctrl+C to stop all."
echo

(
  cd "$ROOT/backend"
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 2>&1 | prefix "be     "
) &
PIDS+=("$!")

(
  cd "$ROOT/frontend"
  npm run dev -- --host 127.0.0.1 --port 5173 2>&1 | prefix "fe     "
) &
PIDS+=("$!")

(
  cd "$ROOT/backend"
  uv run python -m scraper.worker 2>&1 | prefix "scraper"
) &
PIDS+=("$!")

wait
