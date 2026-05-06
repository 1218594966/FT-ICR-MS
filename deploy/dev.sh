#!/bin/bash
set -e

echo "========================================"
echo "  FT-ICR MS - 本地开发环境启动"
echo "========================================"

BASEDIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/3] 安装后端依赖..."
cd "$BASEDIR/backend"
pip install -r requirements.txt

echo "[2/3] 安装前端依赖..."
cd "$BASEDIR/frontend"
npm install

echo "[3/3] 启动服务..."
echo ""
echo "  后端: http://localhost:8001"
echo "  前端: http://localhost:3000"
echo "  API 文档: http://localhost:8001/docs"
echo ""

# Start backend in background
cd "$BASEDIR/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# Start frontend
cd "$BASEDIR/frontend"
npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "All services started. Press Ctrl+C to stop."
wait
