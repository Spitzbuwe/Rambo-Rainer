#!/bin/sh
set -e
cd /app
# Bind-Mount ./frontend:/app ersetzt node_modules aus dem Image — bei leerem Host-Ordner nachinstallieren.
if [ ! -x node_modules/.bin/vite ]; then
  echo "[frontend] npm ci (fehlende node_modules)..."
  npm ci --prefer-offline --no-audit
fi
exec npm run dev -- --host 0.0.0.0 --port 5173
