#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/.venv"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/fticrms.pid"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing command: $1"
    echo "Install it first, or use Docker deployment: bash deploy/deploy.sh"
    exit 1
  fi
}

need_cmd python3

mkdir -p "$LOG_DIR"

echo "[1/5] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

echo "[2/5] Installing Python packages..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

if command -v npm >/dev/null 2>&1; then
  echo "[3/5] Installing frontend packages..."
  cd "$FRONTEND_DIR"
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi

  echo "[4/5] Building frontend..."
  npm run build
else
  echo "[3/5] npm not found; using prebuilt frontend/dist."
  if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
    echo "[ERROR] frontend/dist/index.html not found."
    echo "Install Node.js/npm on the server, or commit the built frontend/dist directory before deploying."
    exit 1
  fi
  echo "[4/5] Frontend build skipped."
fi

echo "[5/5] Starting server on ${HOST}:${PORT}..."
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
  echo "Stopping previous process $(cat "$PID_FILE")..."
  kill "$(cat "$PID_FILE")" || true
  sleep 2
fi

cd "$BACKEND_DIR"
nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1 --timeout-keep-alive 7200 \
  > "$LOG_DIR/server.log" 2> "$LOG_DIR/server.err.log" &
echo $! > "$PID_FILE"

echo ""
echo "Deployment finished."
echo "URL:  http://<server-ip>:${PORT}"
echo "PID:  $(cat "$PID_FILE")"
echo "Logs: tail -f \"$LOG_DIR/server.log\" \"$LOG_DIR/server.err.log\""
echo "Stop: kill \$(cat \"$PID_FILE\")"
