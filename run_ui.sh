#!/bin/bash
# Start the Job Agent UI at http://localhost:8000
#   ./run_ui.sh         build the UI (if needed) and serve it from the Python API
#   ./run_ui.sh dev     hot-reload: API on :8000 + Vite dev server on :5173
set -e
cd "$(dirname "$0")"

if [ ! -d ui/node_modules ]; then
  (cd ui && npm install)
fi

if [ "$1" = "dev" ]; then
  .venv/bin/python -m uvicorn api.server:app --port 8000 --reload --reload-dir api &
  API_PID=$!
  trap 'kill $API_PID' EXIT
  (cd ui && npm run dev)
else
  if [ ! -d ui/dist ] || [ -n "$(find ui/src ui/index.html -newer ui/dist/index.html 2>/dev/null)" ]; then
    (cd ui && npm run build)
  fi
  echo "Job Agent UI: http://localhost:8000"
  .venv/bin/python -m uvicorn api.server:app --port 8000
fi
