#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"

if command -v docker compose >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "[ERROR] Docker Compose is required."
  exit 1
fi

echo "Building and starting FT-ICR MS Web Platform..."
"${COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build

echo ""
echo "Deployment finished."
echo "Frontend: http://localhost"
echo "API:      http://localhost/api/health"
echo ""
echo "Logs:     ${COMPOSE[*]} -f \"$COMPOSE_FILE\" logs -f"
echo "Stop:     ${COMPOSE[*]} -f \"$COMPOSE_FILE\" down"
