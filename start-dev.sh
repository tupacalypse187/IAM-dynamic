#!/bin/bash
# Start script for IAM-Dynamic development environment

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Kill any existing processes on ports 8000 and 3000
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Wait for ports to be released
sleep 2

# Start Backend
echo "Starting FastAPI Backend on port 8000..."
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait a moment for backend to start
sleep 3

# Start Frontend
echo "Starting React Frontend on port 3000..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "IAM-Dynamic Development Environment"
echo "=========================================="
echo "Backend API:  http://localhost:8000"
echo "API Docs:    http://localhost:8000/docs"
echo "Frontend:     http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "=========================================="

# Handle shutdown
trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for any process to exit
wait
