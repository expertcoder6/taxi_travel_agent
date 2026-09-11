#!/bin/sh
set -e

echo "Starting FastAPI backend on 127.0.0.1:8000..."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend startup..."
sleep 2

echo "Starting Next.js frontend on port ${PORT:-3000}..."
cd frontend
export BACKEND_URL="http://127.0.0.1:8000"
export PORT="${PORT:-3000}"
npm run start -- -p "$PORT" &
FRONTEND_PID=$!

# Keep container alive and exit if either process exits
wait -n $BACKEND_PID $FRONTEND_PID
exit $?
